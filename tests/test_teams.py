"""Teams, placements, and the full-pool order used on the Teams tab."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from fantasyhelper.leagues.league import League, LeagueSettings, remove_league
from fantasyhelper.leagues.sales import list_sales, record_sale
from fantasyhelper.leagues.teams import (
    add_team,
    clear_team_player,
    list_team_players,
    list_teams,
    place_team_player,
    rename_team,
)
from fantasyhelper.ui.prices import placement_columns, placement_frame
from fantasyhelper.valuation.prices import PriceRow, with_personal_prices

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


def _row(player_id: int, name: str, plain_rank: int, points: float, turnovers: float) -> PriceRow:
    categories = {"pts": points, "to": turnovers}
    return PriceRow(
        player_id=player_id,
        name=name,
        plain_rank=plain_rank,
        plain_score=points,
        plain_price=plain_rank,
        curved_rank=plain_rank,
        curved_score=points,
        curved_price=plain_rank,
        games=70,
        minutes_per_game=30,
        fga_per_game=10,
        fta_per_game=4,
        fg_pct=0.5,
        ft_pct=0.8,
        counting={"pts": 20, "to": 2},
        plain_categories=categories,
        curved_categories=categories,
    )


class TeamStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "teams.sqlite3"
        self._teams = patch("fantasyhelper.leagues.teams.connect", lambda: _connect(self.path))
        self._sales = patch("fantasyhelper.leagues.sales.connect", lambda: _connect(self.path))
        self._league = patch("fantasyhelper.leagues.league.connect", lambda: _connect(self.path))
        self._teams.start()
        self._sales.start()
        self._league.start()
        conn = _connect(self.path)
        conn.execute(
            "CREATE TABLE players (id INTEGER PRIMARY KEY, name_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL)"
        )
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
        self._teams.stop()
        self._sales.stop()
        self._league.stop()
        self._directory.cleanup()

    def test_teams_are_added_in_order_and_renamed(self) -> None:
        self.assertEqual(add_team(1, "  Celtics  "), ())
        self.assertEqual(add_team(1, "Lakers"), ())
        saved = list_teams(1)
        self.assertEqual([team.name for team in saved], ["Celtics", "Lakers"])
        self.assertEqual(rename_team(1, saved[0].id, "celtics"), ())
        self.assertEqual(list_teams(1)[0].name, "celtics")
        self.assertEqual(rename_team(1, saved[0].id, "Lakers"), ("A team named Lakers already exists.",))
        self.assertEqual(list_teams(1)[0].name, "celtics")

    def test_a_blank_duplicate_or_reserved_name_is_refused(self) -> None:
        self.assertEqual(add_team(1, "   "), ("Enter a team name.",))
        self.assertEqual(add_team(1, "Players"), ("Players is the unassigned list. Choose another name.",))
        self.assertEqual(add_team(1, "players"), ("Players is the unassigned list. Choose another name.",))
        self.assertEqual(add_team(1, "Celtics"), ())
        self.assertEqual(add_team(1, "celtics"), ("A team named celtics already exists.",))
        self.assertEqual(len(list_teams(1)), 1)

    def test_a_player_is_on_one_team_and_can_return_to_the_list(self) -> None:
        add_team(1, "Celtics")
        add_team(1, "Lakers")
        celtics, lakers = list_teams(1)
        self.assertEqual(place_team_player(1, 1, celtics.id), ())
        self.assertEqual(place_team_player(1, 1, lakers.id), ())
        placed = list_team_players(1)
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].team_id, lakers.id)
        clear_team_player(1, 1)
        self.assertEqual(list_team_players(1), ())
        clear_team_player(1, 1)
        self.assertEqual(place_team_player(1, 9, celtics.id), ("That player is not in the imported players.",))
        self.assertEqual(place_team_player(1, 1, 99), ("That team is no longer available.",))

    def test_count_is_not_a_column_and_a_sale_is_separate(self) -> None:
        add_team(1, "Celtics")
        team_id = list_teams(1)[0].id
        self.assertEqual(place_team_player(1, 1, team_id), ())
        conn = _connect(self.path)
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(team_players)")]
        conn.close()
        self.assertEqual(columns, ["league_id", "player_id", "team_id"])
        self.assertEqual(record_sale(self.league, 2, "mine", 40, "keeper"), ())
        self.assertEqual([item.player_id for item in list_team_players(1)], [1])
        self.assertEqual([sale.player_id for sale in list_sales(1)], [2])

    def test_hiding_a_league_leaves_the_rows(self) -> None:
        add_team(1, "Celtics")
        team_id = list_teams(1)[0].id
        place_team_player(1, 1, team_id)
        remove_league(1)
        self.assertEqual([team.name for team in list_teams(1)], ["Celtics"])
        self.assertEqual(list_team_players(1)[0].player_id, 1)


class PlacementTableTests(unittest.TestCase):
    def test_team_follows_name_and_a_punt_is_not_marked(self) -> None:
        active = frozenset({"pts", "to"})
        columns = placement_columns(active)
        self.assertEqual(columns[:6], ["Name", "Team", "Pos", "TZ Rank", "TZ Price", "TC Rank"])
        self.assertNotIn("Pts (p)", columns)
        self.assertIn("Pts", columns)
        frame = placement_frame(
            (_row(1, "A", 1, 1.0, 0.0),),
            ("Players",),
            active,
            blanks=(("Veteran", "Celtics"),),
        )
        self.assertEqual(list(frame["Name"]), ["A", "Veteran"])
        self.assertEqual(list(frame["Team"]), ["Players", "Celtics"])
        self.assertTrue(pd.isna(frame.loc[1, "TZ Rank"]))

    def test_a_punt_keeps_the_original_order(self) -> None:
        rows = (
            _row(1, "A", 1, 1.0, 5.0),
            _row(2, "B", 2, 3.0, 0.0),
        )
        priced = with_personal_prices(rows, frozenset({"to"}), 2, 10, 2)
        self.assertEqual([row.name for row in priced], ["A", "B"])
        self.assertEqual(priced[0].plain_rank, 1)
        self.assertEqual(priced[1].personal_plain_rank, 1)
        self.assertEqual(priced[0].personal_plain_rank, 2)
        untouched = with_personal_prices(rows, frozenset(), 2, 10, 2)
        self.assertIsNone(untouched[0].personal_plain_rank)


if __name__ == "__main__":
    unittest.main()
