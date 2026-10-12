"""Sale rows for one league."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fantasyhelper.leagues.league import League, LeagueSettings
from fantasyhelper.leagues.sales import list_sales, record_sale, remove_sale, update_sale

_LEAGUE = """
CREATE TABLE leagues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
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
"""


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class SaleStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "sales.sqlite3"
        self._patch = patch("fantasyhelper.leagues.sales.connect", lambda: _connect(self.path))
        self._patch.start()
        conn = _connect(self.path)
        conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, name_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL)")
        conn.execute(_LEAGUE)
        conn.execute("INSERT INTO players (id, name_key, name) VALUES (1, 'a', 'A'), (2, 'b', 'B')")
        conn.execute(
            """
            INSERT INTO leagues (
                id, name, season, team_count, budget, roster_size,
                cat_pts, cat_reb, cat_ast, cat_stl, cat_blk, cat_threes, cat_fg_pct, cat_ft_pct, cat_to,
                status
            ) VALUES (1, 'My league', '2026-27', 12, 200, 13, 1, 1, 1, 1, 1, 1, 1, 1, 1, 'active')
            """
        )
        conn.close()
        self.league = League(
            id=1,
            settings=LeagueSettings(
                name="My league",
                season="2026-27",
                team_count=12,
                budget=200,
                roster_size=13,
                categories=frozenset({"pts"}),
            ),
        )

    def tearDown(self) -> None:
        self._patch.stop()
        self._directory.cleanup()

    def test_a_sale_is_saved_edited_and_removed(self) -> None:
        self.assertEqual(record_sale(self.league, 1, "mine", 40, "keeper"), ())
        saved = list_sales(1)
        self.assertEqual(saved[0].player_id, 1)
        self.assertEqual(saved[0].side, "mine")
        self.assertEqual(saved[0].price, 40)
        self.assertEqual(saved[0].sale_type, "keeper")
        self.assertEqual(update_sale(self.league, 1, "other", 55, "draft"), ())
        edited = list_sales(1)[0]
        self.assertEqual(edited.side, "other")
        self.assertEqual(edited.price, 55)
        self.assertEqual(edited.sale_type, "draft")
        remove_sale(1, 1)
        self.assertEqual(list_sales(1), ())

    def test_a_refused_sale_is_not_saved(self) -> None:
        self.assertEqual(record_sale(self.league, 1, "mine", 40, "keeper"), ())
        self.assertEqual(
            record_sale(self.league, 1, "mine", 40, "draft"),
            ("That player is already sold.",),
        )
        self.assertEqual(len(list_sales(1)), 1)
        self.assertEqual(
            record_sale(self.league, 9, "mine", 1, "draft"),
            ("That player is not in the imported players.",),
        )
        self.assertEqual(
            record_sale(self.league, 2, "mine", 189, "draft"),
            ("That price is above your max bid of $149.",),
        )


if __name__ == "__main__":
    unittest.main()
