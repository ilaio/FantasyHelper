"""Named teams and the player on each team. Count is not stored."""

import sqlite3
from dataclasses import dataclass

from fantasyhelper.db import connect

UNASSIGNED = "Players"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    name TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (league_id, name)
);

CREATE TABLE IF NOT EXISTS team_players (
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    team_id INTEGER NOT NULL REFERENCES teams(id),
    PRIMARY KEY (league_id, player_id)
)
"""


@dataclass(frozen=True)
class Team:
    id: int
    name: str


@dataclass(frozen=True)
class TeamPlayer:
    player_id: int
    team_id: int


def list_teams(league_id: int) -> tuple[Team, ...]:
    """Teams in the order they were added."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, name
            FROM teams
            WHERE league_id = ?
            ORDER BY id
            """,
            (league_id,),
        ).fetchall()
    finally:
        conn.close()
    return tuple(Team(id=row["id"], name=row["name"]) for row in rows)


def list_team_players(league_id: int) -> tuple[TeamPlayer, ...]:
    """Players who have been placed. A missing player is still on the Players list."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT player_id, team_id
            FROM team_players
            WHERE league_id = ?
            ORDER BY player_id
            """,
            (league_id,),
        ).fetchall()
    finally:
        conn.close()
    return tuple(
        TeamPlayer(player_id=row["player_id"], team_id=row["team_id"]) for row in rows
    )


def add_team(league_id: int, name: str) -> tuple[str, ...]:
    """Save a team. An empty tuple means it was saved."""
    conn = _connect()
    try:
        if _league_is_missing(conn, league_id):
            return ("That league is no longer available.",)
        cleaned = name.strip()
        taken = {team.name for team in _load_teams(conn, league_id)}
        error = _name_error(cleaned, taken)
        if error is not None:
            return (error,)

        def save() -> None:
            conn.execute(
                "INSERT INTO teams (league_id, name) VALUES (?, ?)",
                (league_id, cleaned),
            )

        try:
            _transaction(conn, save)
        except sqlite3.IntegrityError:
            return (f"A team named {cleaned} already exists.",)
    finally:
        conn.close()
    return ()


def rename_team(league_id: int, team_id: int, name: str) -> tuple[str, ...]:
    """Rename a team in place. An empty tuple means it was saved."""
    conn = _connect()
    try:
        current = _load_team(conn, league_id, team_id)
        if current is None:
            return ("That team is no longer available.",)
        cleaned = name.strip()
        if cleaned == current.name:
            return ()
        taken = {
            team.name
            for team in _load_teams(conn, league_id)
            if team.id != team_id
        }
        error = _name_error(cleaned, taken)
        if error is not None:
            return (error,)

        def save() -> None:
            conn.execute(
                "UPDATE teams SET name = ? WHERE id = ? AND league_id = ?",
                (cleaned, team_id, league_id),
            )

        try:
            _transaction(conn, save)
        except sqlite3.IntegrityError:
            return (f"A team named {cleaned} already exists.",)
    finally:
        conn.close()
    return ()


def place_team_player(league_id: int, player_id: int, team_id: int) -> tuple[str, ...]:
    """Put a player on a team. A player already placed moves to that team."""
    conn = _connect()
    try:
        if _league_is_missing(conn, league_id):
            return ("That league is no longer available.",)
        if _player_is_missing(conn, player_id):
            return ("That player is not in the imported players.",)
        if _load_team(conn, league_id, team_id) is None:
            return ("That team is no longer available.",)

        def save() -> None:
            conn.execute(
                """
                INSERT INTO team_players (league_id, player_id, team_id)
                VALUES (?, ?, ?)
                ON CONFLICT (league_id, player_id) DO UPDATE SET team_id = excluded.team_id
                """,
                (league_id, player_id, team_id),
            )

        _transaction(conn, save)
    finally:
        conn.close()
    return ()


def clear_team_player(league_id: int, player_id: int) -> None:
    """Send a player back to the Players list. Nothing happens when they are already there."""
    conn = _connect()
    try:
        _transaction(
            conn,
            lambda: conn.execute(
                "DELETE FROM team_players WHERE league_id = ? AND player_id = ?",
                (league_id, player_id),
            ),
        )
    finally:
        conn.close()


def _name_error(name: str, taken: set[str]) -> str | None:
    if name == "":
        return "Enter a team name."
    if name.casefold() == UNASSIGNED.casefold():
        return "Players is the unassigned list. Choose another name."
    if name.casefold() in {item.casefold() for item in taken}:
        return f"A team named {name} already exists."
    return None


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.executescript(_SCHEMA)
    return conn


def _load_teams(conn: sqlite3.Connection, league_id: int) -> tuple[Team, ...]:
    rows = conn.execute(
        "SELECT id, name FROM teams WHERE league_id = ? ORDER BY id",
        (league_id,),
    ).fetchall()
    return tuple(Team(id=row["id"], name=row["name"]) for row in rows)


def _load_team(conn: sqlite3.Connection, league_id: int, team_id: int) -> Team | None:
    row = conn.execute(
        "SELECT id, name FROM teams WHERE id = ? AND league_id = ?",
        (team_id, league_id),
    ).fetchone()
    if row is None:
        return None
    return Team(id=row["id"], name=row["name"])


def _league_is_missing(conn: sqlite3.Connection, league_id: int) -> bool:
    row = conn.execute("SELECT id FROM leagues WHERE id = ?", (league_id,)).fetchone()
    return row is None


def _player_is_missing(conn: sqlite3.Connection, player_id: int) -> bool:
    row = conn.execute("SELECT id FROM players WHERE id = ?", (player_id,)).fetchone()
    return row is None


def _transaction(conn: sqlite3.Connection, write) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        write()
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
