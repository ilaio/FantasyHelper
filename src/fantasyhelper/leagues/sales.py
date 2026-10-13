"""Sales for one league. A keeper is a sale entered before the draft."""

import sqlite3

from fantasyhelper.db import connect
from fantasyhelper.leagues.league import League
from fantasyhelper.valuation.prices import Sale, sale_errors

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    side TEXT NOT NULL CHECK (side IN ('mine', 'other')),
    price INTEGER NOT NULL CHECK (price >= 1),
    sale_type TEXT NOT NULL CHECK (sale_type IN ('keeper', 'draft')),
    UNIQUE (league_id, player_id)
)
"""


def list_sales(league_id: int) -> tuple[Sale, ...]:
    conn = _connect()
    try:
        return _load(conn, league_id)
    finally:
        conn.close()


def record_sale(
    league: League,
    player_id: int,
    side: str,
    price: int,
    sale_type: str,
) -> tuple[str, ...]:
    """Save a new sale. An empty tuple means it was saved."""
    return _write(league, player_id, side, price, sale_type, replacing=False)


def update_sale(
    league: League,
    player_id: int,
    side: str,
    price: int,
    sale_type: str,
) -> tuple[str, ...]:
    """Replace the side, price, and sale type for a player already sold."""
    return _write(league, player_id, side, price, sale_type, replacing=True)


def remove_sale(league_id: int, player_id: int) -> None:
    """Unmark a player. Nothing happens when that player is not sold."""
    conn = _connect()
    try:
        _transaction(
            conn,
            lambda: conn.execute(
                "DELETE FROM sales WHERE league_id = ? AND player_id = ?",
                (league_id, player_id),
            ),
        )
    finally:
        conn.close()


def _write(
    league: League,
    player_id: int,
    side: str,
    price: int,
    sale_type: str,
    *,
    replacing: bool,
) -> tuple[str, ...]:
    conn = _connect()
    try:
        if _league_is_missing(conn, league.id):
            return ("That league is no longer available.",)
        if _player_is_missing(conn, player_id):
            return ("That player is not in the imported players.",)
        current = _load(conn, league.id)
        settings = league.settings
        errors = sale_errors(
            current,
            player_id,
            side,
            price,
            sale_type,
            settings.team_count,
            settings.budget,
            settings.roster_size,
            replacing=replacing,
        )
        if errors:
            return errors
        if replacing and not any(sale.player_id == player_id for sale in current):
            return ("That player is not sold.",)

        def save() -> None:
            if replacing:
                conn.execute(
                    """
                    UPDATE sales
                    SET side = ?, price = ?, sale_type = ?
                    WHERE league_id = ? AND player_id = ?
                    """,
                    (side, price, sale_type, league.id, player_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO sales (league_id, player_id, side, price, sale_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (league.id, player_id, side, price, sale_type),
                )

        _transaction(conn, save)
    finally:
        conn.close()
    return ()


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(_SCHEMA)
    return conn


def _load(conn: sqlite3.Connection, league_id: int) -> tuple[Sale, ...]:
    rows = conn.execute(
        """
        SELECT player_id, side, price, sale_type
        FROM sales
        WHERE league_id = ?
        ORDER BY id
        """,
        (league_id,),
    ).fetchall()
    return tuple(
        Sale(
            player_id=row["player_id"],
            side=row["side"],
            price=row["price"],
            sale_type=row["sale_type"],
        )
        for row in rows
    )


def _league_is_missing(conn: sqlite3.Connection, league_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM leagues WHERE id = ? AND status = 'active'",
        (league_id,),
    ).fetchone()
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
