"""SQLite storage for imported players, seasons, and projections."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fantasyhelper.db import connect, project_root

STATS_HEADER = (
    "name",
    "team",
    "positions",
    "games",
    "minutes",
    "points",
    "threes",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fg_pct",
    "fga",
    "ft_pct",
    "fta",
)

PROJECTION_HEADER = (
    "name",
    "team",
    "positions",
    "games",
    "minutes_per_game",
    "points_per_game",
    "threes_per_game",
    "rebounds_per_game",
    "assists_per_game",
    "steals_per_game",
    "blocks_per_game",
    "turnovers_per_game",
    "fg_pct",
    "fga_per_game",
    "ft_pct",
    "fta_per_game",
    "source_rank",
    "source_dollars",
)

STATS_OPTIONAL = frozenset({"fg_pct", "ft_pct"})
PROJECTION_OPTIONAL = frozenset({"fg_pct", "ft_pct"})

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY,
        name_key TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS season_stats (
        player_id INTEGER NOT NULL REFERENCES players(id),
        season TEXT NOT NULL,
        team TEXT NOT NULL,
        positions TEXT NOT NULL,
        games REAL NOT NULL,
        minutes REAL NOT NULL,
        points REAL NOT NULL,
        threes REAL NOT NULL,
        rebounds REAL NOT NULL,
        assists REAL NOT NULL,
        steals REAL NOT NULL,
        blocks REAL NOT NULL,
        turnovers REAL NOT NULL,
        fg_pct REAL,
        fga REAL NOT NULL,
        ft_pct REAL,
        fta REAL NOT NULL,
        PRIMARY KEY (player_id, season)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projections (
        player_id INTEGER NOT NULL REFERENCES players(id),
        season TEXT NOT NULL,
        source TEXT NOT NULL,
        team TEXT NOT NULL,
        positions TEXT NOT NULL,
        games REAL NOT NULL,
        minutes_per_game REAL NOT NULL,
        points_per_game REAL NOT NULL,
        threes_per_game REAL NOT NULL,
        rebounds_per_game REAL NOT NULL,
        assists_per_game REAL NOT NULL,
        steals_per_game REAL NOT NULL,
        blocks_per_game REAL NOT NULL,
        turnovers_per_game REAL NOT NULL,
        fg_pct REAL,
        fga_per_game REAL NOT NULL,
        ft_pct REAL,
        fta_per_game REAL NOT NULL,
        source_rank REAL NOT NULL,
        source_dollars REAL NOT NULL,
        PRIMARY KEY (player_id, season, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_log (
        file_name TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        season TEXT NOT NULL,
        source TEXT NOT NULL,
        imported_at TEXT NOT NULL
    )
    """,
)


@dataclass(frozen=True)
class Dataset:
    file_name: str
    kind: str
    season: str
    source: str


def inbox_directory() -> Path:
    return project_root() / "data" / "inbox"


def ensure_schema(conn: sqlite3.Connection) -> None:
    for statement in _SCHEMA:
        conn.execute(statement)


def file_imported(conn: sqlite3.Connection, file_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM import_log WHERE file_name = ?",
        (file_name,),
    ).fetchone()
    return row is not None


def stats_season_imported(conn: sqlite3.Connection, season: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM import_log WHERE kind = 'stats' AND season = ?",
        (season,),
    ).fetchone()
    return row is not None


def write_stats(
    conn: sqlite3.Connection,
    file_name: str,
    season: str,
    rows: list[dict[str, object]],
) -> None:
    _write_rows(
        conn,
        table="season_stats",
        header=STATS_HEADER,
        identity=("season",),
        identity_values=(season,),
        file_name=file_name,
        kind="stats",
        season=season,
        source="",
        rows=rows,
    )


def write_projection(
    conn: sqlite3.Connection,
    file_name: str,
    season: str,
    source: str,
    rows: list[dict[str, object]],
) -> None:
    _write_rows(
        conn,
        table="projections",
        header=PROJECTION_HEADER,
        identity=("season", "source"),
        identity_values=(season, source),
        file_name=file_name,
        kind="projection",
        season=season,
        source=source,
        rows=rows,
    )


def list_datasets() -> list[Dataset]:
    conn = connect()
    try:
        ensure_schema(conn)
        found = conn.execute(
            """
            SELECT file_name, kind, season, source
            FROM import_log
            ORDER BY CASE kind WHEN 'stats' THEN 0 ELSE 1 END,
                     season DESC,
                     source
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        Dataset(
            file_name=row["file_name"],
            kind=row["kind"],
            season=row["season"],
            source=row["source"],
        )
        for row in found
    ]


def load_player_rows(dataset: Dataset) -> list[dict[str, object]]:
    conn = connect()
    try:
        ensure_schema(conn)
        if dataset.kind == "stats":
            found = conn.execute(
                """
                SELECT p.name, s.team, s.positions, s.games, s.minutes, s.points,
                       s.threes, s.rebounds, s.assists, s.steals, s.blocks,
                       s.turnovers, s.fg_pct, s.fga, s.ft_pct, s.fta
                FROM season_stats AS s
                JOIN players AS p ON p.id = s.player_id
                WHERE s.season = ?
                ORDER BY p.name COLLATE NOCASE, p.name
                """,
                (dataset.season,),
            ).fetchall()
        else:
            found = conn.execute(
                """
                SELECT p.name, j.team, j.positions, j.games, j.minutes_per_game,
                       j.points_per_game, j.threes_per_game, j.rebounds_per_game,
                       j.assists_per_game, j.steals_per_game, j.blocks_per_game,
                       j.turnovers_per_game, j.fg_pct, j.fga_per_game, j.ft_pct,
                       j.fta_per_game, j.source_rank, j.source_dollars
                FROM projections AS j
                JOIN players AS p ON p.id = j.player_id
                WHERE j.season = ? AND j.source = ?
                ORDER BY p.name COLLATE NOCASE, p.name
                """,
                (dataset.season, dataset.source),
            ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in found]


def _write_rows(
    conn: sqlite3.Connection,
    table: str,
    header: tuple[str, ...],
    identity: tuple[str, ...],
    identity_values: tuple[str, ...],
    file_name: str,
    kind: str,
    season: str,
    source: str,
    rows: list[dict[str, object]],
) -> None:
    value_columns = tuple(column for column in header if column != "name")
    columns = ("player_id", *identity, *value_columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in rows:
            player_id = _ensure_player(conn, str(row["name_key"]), str(row["name"]))
            values = (player_id, *identity_values, *(row[column] for column in value_columns))
            conn.execute(insert_sql, values)
        conn.execute(
            """
            INSERT INTO import_log (file_name, kind, season, source, imported_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_name, kind, season, source, imported_at),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _ensure_player(conn: sqlite3.Connection, name_key: str, name: str) -> int:
    existing = conn.execute(
        "SELECT id FROM players WHERE name_key = ?",
        (name_key,),
    ).fetchone()
    if existing is not None:
        return int(existing["id"])
    cursor = conn.execute(
        "INSERT INTO players (name_key, name) VALUES (?, ?)",
        (name_key, name),
    )
    return int(cursor.lastrowid)
