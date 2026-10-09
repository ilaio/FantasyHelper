"""Create, edit, and remove leagues. Players are not copied per league."""

import re
import sqlite3
from dataclasses import dataclass

from fantasyhelper.db import connect

CATEGORIES = (
    ("pts", "Points"),
    ("reb", "Rebounds"),
    ("ast", "Assists"),
    ("stl", "Steals"),
    ("blk", "Blocks"),
    ("threes", "Threes"),
    ("fg_pct", "FG%"),
    ("ft_pct", "FT%"),
    ("to", "Turnovers"),
)

DEFAULT_NAME = "My league"
DEFAULT_SEASON = "2026-27"
TEAM_MIN, TEAM_MAX = 2, 30
BUDGET_MIN, BUDGET_MAX = 1, 10000
ROSTER_MIN, ROSTER_MAX = 1, 30

_SEASON = re.compile(r"^\d{4}-\d{2}$")
_CATEGORY_KEYS = frozenset(key for key, _label in CATEGORIES)
ACTIVE = "active"
DELETED = "deleted"
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        season TEXT NOT NULL,
        team_count INTEGER NOT NULL,
        budget INTEGER NOT NULL,
        roster_size INTEGER NOT NULL,
        cat_pts INTEGER NOT NULL,
        cat_reb INTEGER NOT NULL,
        cat_ast INTEGER NOT NULL,
        cat_stl INTEGER NOT NULL,
        cat_blk INTEGER NOT NULL,
        cat_threes INTEGER NOT NULL,
        cat_fg_pct INTEGER NOT NULL,
        cat_ft_pct INTEGER NOT NULL,
        cat_to INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS leagues_active_name
    ON leagues(name) WHERE status = 'active'
    """,
)


@dataclass(frozen=True)
class LeagueSettings:
    name: str
    season: str
    team_count: int
    budget: int
    roster_size: int
    categories: frozenset[str]


@dataclass(frozen=True)
class League:
    id: int
    settings: LeagueSettings


def default_settings() -> LeagueSettings:
    return LeagueSettings(
        name=DEFAULT_NAME,
        season=DEFAULT_SEASON,
        team_count=12,
        budget=200,
        roster_size=13,
        categories=frozenset(_CATEGORY_KEYS),
    )


def validate(settings: LeagueSettings, taken_names: set[str]) -> tuple[str, ...]:
    """Return plain-language reasons a league cannot be saved."""
    errors: list[str] = []
    if settings.name == "":
        errors.append("Enter a league name.")
    elif settings.name.casefold() in {name.casefold() for name in taken_names}:
        errors.append(f"A league named {settings.name} already exists.")
    if _SEASON.fullmatch(settings.season) is None:
        errors.append("Season has to look like 2026-27.")
    if not _in_range(settings.team_count, TEAM_MIN, TEAM_MAX):
        errors.append(f"Teams has to be a whole number from {TEAM_MIN} to {TEAM_MAX}.")
    if not _in_range(settings.budget, BUDGET_MIN, BUDGET_MAX):
        errors.append(
            f"Budget has to be a whole number of dollars from {BUDGET_MIN} to {BUDGET_MAX}."
        )
    if not _in_range(settings.roster_size, ROSTER_MIN, ROSTER_MAX):
        errors.append(
            f"Roster spots has to be a whole number from {ROSTER_MIN} to {ROSTER_MAX}."
        )
    if not settings.categories or not settings.categories <= _CATEGORY_KEYS:
        errors.append("Leave at least one category on.")
    return tuple(errors)


def summary(league: League) -> str:
    settings = league.settings
    active = len(settings.categories)
    if active == len(CATEGORIES):
        categories = f"{active} categories"
    else:
        noun = "category" if active == 1 else "categories"
        off = [_phrase(label) for key, label in CATEGORIES if key not in settings.categories]
        categories = f"{active} {noun} ({_off_phrase(off)})"
    return (
        f"{settings.name}, {settings.season}, {settings.team_count} teams, "
        f"${settings.budget}, {settings.roster_size} spots, {categories}"
    )


def list_leagues() -> list[League]:
    conn = _connect()
    try:
        return _load_all(conn)
    finally:
        conn.close()


def create_league(settings: LeagueSettings) -> int | tuple[str, ...]:
    """Save a new league. Returns its id, or the reasons it was refused."""
    conn = _connect()
    try:
        taken = {league.settings.name for league in _load_all(conn)}
        errors = validate(settings, taken)
        if errors:
            return errors
        new_id: int | None = None

        def write() -> None:
            nonlocal new_id
            new_id = _insert(conn, settings)

        try:
            _transaction(conn, write)
        except sqlite3.IntegrityError:
            return (f"A league named {settings.name} already exists.",)
    finally:
        conn.close()
    assert new_id is not None
    return new_id


def update_league(league_id: int, settings: LeagueSettings) -> tuple[str, ...]:
    """Save settings for an existing league. Returns errors, or an empty tuple."""
    conn = _connect()
    try:
        current = _load_one(conn, league_id)
        if current is None:
            return ("That league is no longer available.",)
        taken = {
            league.settings.name
            for league in _load_all(conn)
            if league.id != league_id
        }
        errors = validate(settings, taken)
        if errors:
            return errors
        try:
            _transaction(conn, lambda: _update_row(conn, league_id, settings))
        except sqlite3.IntegrityError:
            return (f"A league named {settings.name} already exists.",)
    finally:
        conn.close()
    return ()


def remove_league(league_id: int) -> None:
    """Hide a league. Its draft rows stay."""
    conn = _connect()
    try:
        if _load_one(conn, league_id) is None:
            return
        _transaction(
            conn,
            lambda: conn.execute(
                "UPDATE leagues SET status = ? WHERE id = ?",
                (DELETED, league_id),
            ),
        )
    finally:
        conn.close()


def _connect() -> sqlite3.Connection:
    conn = connect()
    for statement in _SCHEMA:
        conn.execute(statement)
    return conn


def _transaction(conn: sqlite3.Connection, write) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        write()
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _load_all(conn: sqlite3.Connection) -> list[League]:
    rows = conn.execute(
        """
        SELECT * FROM leagues
        WHERE status = ?
        ORDER BY name COLLATE NOCASE, name, id
        """,
        (ACTIVE,),
    ).fetchall()
    return [_league_from_row(row) for row in rows]


def _load_one(conn: sqlite3.Connection, league_id: int) -> League | None:
    row = conn.execute(
        "SELECT * FROM leagues WHERE id = ? AND status = ?",
        (league_id, ACTIVE),
    ).fetchone()
    if row is None:
        return None
    return _league_from_row(row)


def _league_from_row(row: sqlite3.Row) -> League:
    categories = frozenset(key for key, _label in CATEGORIES if row[f"cat_{key}"])
    return League(
        id=int(row["id"]),
        settings=LeagueSettings(
            name=row["name"],
            season=row["season"],
            team_count=int(row["team_count"]),
            budget=int(row["budget"]),
            roster_size=int(row["roster_size"]),
            categories=categories,
        ),
    )


def _insert(conn: sqlite3.Connection, settings: LeagueSettings) -> int:
    columns = (
        "name",
        "season",
        "team_count",
        "budget",
        "roster_size",
        *(f"cat_{key}" for key, _label in CATEGORIES),
        "status",
    )
    values = (
        settings.name,
        settings.season,
        settings.team_count,
        settings.budget,
        settings.roster_size,
        *(1 if key in settings.categories else 0 for key, _label in CATEGORIES),
        ACTIVE,
    )
    marks = ", ".join("?" for _ in columns)
    cursor = conn.execute(
        f"INSERT INTO leagues ({', '.join(columns)}) VALUES ({marks})",
        values,
    )
    return int(cursor.lastrowid)


def _update_row(conn: sqlite3.Connection, league_id: int, settings: LeagueSettings) -> None:
    assignments = ", ".join(
        (
            "name = ?",
            "season = ?",
            "team_count = ?",
            "budget = ?",
            "roster_size = ?",
            *(f"cat_{key} = ?" for key, _label in CATEGORIES),
        )
    )
    values = (
        settings.name,
        settings.season,
        settings.team_count,
        settings.budget,
        settings.roster_size,
        *(1 if key in settings.categories else 0 for key, _label in CATEGORIES),
        league_id,
    )
    conn.execute(f"UPDATE leagues SET {assignments} WHERE id = ?", values)


def _in_range(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _phrase(label: str) -> str:
    if label.isupper() or "%" in label:
        return label
    return label.lower()


def _off_phrase(labels: list[str]) -> str:
    if len(labels) == 1:
        return f"{labels[0]} off"
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]} off"
    return f"{', '.join(labels[:-1])}, and {labels[-1]} off"
