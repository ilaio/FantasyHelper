"""Display rules for the price table."""

import unittest

from fantasyhelper.ui.prices import (
    _row_colors,
    column_alignment,
    column_label,
    price_format,
    punt_limit,
    punt_refusal,
    shot_text,
    strength_color,
    roster_columns,
    summary_columns,
    table_columns,
    _suggestion_columns,
)
from fantasyhelper.valuation.prices import PriceRow

_DEEP_GREEN = "background-color: #8FCB9B"
_GREEN = "background-color: #C6E6CE"
_LIGHT_GREEN = "background-color: #E7F6EB"
_LIGHT_RED = "background-color: #FDECEC"
_RED = "background-color: #F6C9C4"
_DEEP_RED = "background-color: #E89B96"


class ColorTests(unittest.TestCase):
    def test_edges_take_the_higher_band(self) -> None:
        self.assertEqual(strength_color(2), _DEEP_GREEN)
        self.assertEqual(strength_color(1), _GREEN)
        self.assertEqual(strength_color(0), _LIGHT_GREEN)
        self.assertEqual(strength_color(-0.75), _LIGHT_RED)
        self.assertEqual(strength_color(-1.5), _RED)
        self.assertEqual(strength_color(-1.51), _DEEP_RED)

    def test_shot_cell_keeps_a_blank_percentage(self) -> None:
        self.assertEqual(shot_text(0.553, 12.4), "55.3% / 12.4")
        self.assertEqual(shot_text(None, 12.4), "— / 12.4")

    def test_a_turned_off_category_is_omitted(self) -> None:
        active = frozenset({"pts", "reb", "ast", "stl", "blk", "threes", "ft_pct", "to"})
        columns = table_columns(active)
        self.assertNotIn("FG% / FGA", columns)
        self.assertEqual(columns[11], "FT% / FTA")
        self.assertEqual(
            columns[:9],
            ["Name", "TZ Rank", "TZ Price", "TC Rank", "TC Price", "PZ Rank", "PZ Price", "PC Rank", "PC Price"],
        )
        self.assertNotIn("TZ Score", columns)
        self.assertNotIn("TC Score", columns)
        self.assertEqual(columns[-1], "Tov")
        self.assertEqual(column_alignment("Name"), "left")
        self.assertTrue(all(column_alignment(name) == "center" for name in columns[1:]))
        self.assertEqual(price_format("TZ Price"), "$%d")
        self.assertEqual(price_format("TC Price"), "$%d")
        self.assertEqual(price_format("PZ Price"), "$%d")
        self.assertEqual(price_format("PC Price"), "$%d")
        self.assertIsNone(price_format("TZ Rank"))
        self.assertEqual(punt_limit(9), 2)
        self.assertEqual(punt_limit(2), 1)
        self.assertEqual(punt_limit(1), 0)
        self.assertEqual(punt_refusal(3, 9), "Only two categories can be off.")
        self.assertEqual(punt_refusal(2, 2), "Leave at least one category on.")
        self.assertIsNone(punt_refusal(2, 9))
        self.assertIsNone(punt_refusal(0, 9))

    def test_a_punt_adds_personal_columns_and_marks_the_header(self) -> None:
        active = frozenset({"pts", "reb", "blk"})
        columns = table_columns(active, frozenset({"blk"}))
        self.assertEqual(
            columns[:9],
            ["Name", "TZ Rank", "TZ Price", "TC Rank", "TC Price", "PZ Rank", "PZ Price", "PC Rank", "PC Price"],
        )
        self.assertEqual(columns[9:11], ["Games", "Minutes"])
        self.assertIn("Blk (p)", columns)
        self.assertNotIn("Blk", columns)
        self.assertEqual(column_label("Blk", False), "Blk")

    def test_a_taken_list_keeps_the_projection_and_drops_ranks(self) -> None:
        active = frozenset({"pts", "reb", "blk", "fg_pct"})
        columns = roster_columns(active, frozenset({"blk"}))
        self.assertEqual(columns[:5], ["Name", "Price", "Sale", "Games", "Minutes"])
        self.assertEqual(columns[5], "FG% / FGA")
        self.assertIn("Blk (p)", columns)
        self.assertNotIn("TZ Rank", columns)
        self.assertNotIn("PZ Price", columns)
        self.assertEqual(price_format("Price"), "$%d")

    def test_the_summary_has_money_then_categories_and_no_punt_mark(self) -> None:
        columns = summary_columns(frozenset({"pts", "blk", "fg_pct"}))
        self.assertEqual(columns[:5], [" ", "Money left", "Spent", "Spots left", "Taken"])
        self.assertEqual(columns[5:], ["FG% / FGA", "Pts", "Blk"])
        self.assertNotIn("Blk (p)", columns)

    def test_nominations_and_targets_share_columns(self) -> None:
        self.assertEqual(
            _suggestion_columns(frozenset()),
            ["Name", "TZ Price", "TC Price", "Category"],
        )
        self.assertEqual(
            _suggestion_columns(frozenset({"blk"})),
            ["Name", "TZ Price", "PC Price", "Category"],
        )

    def test_usage_and_category_colors(self) -> None:
        row = PriceRow(
            player_id=1,
            name="A",
            plain_rank=1,
            plain_score=1,
            plain_price=4,
            curved_rank=2,
            curved_score=0.5,
            curved_price=3,
            games=59,
            minutes_per_game=25,
            fga_per_game=12.4,
            fta_per_game=2,
            fg_pct=None,
            ft_pct=0.8,
            counting={"pts": 20, "reb": 5, "ast": 4, "stl": 1, "blk": 0.5, "threes": 2, "to": 2},
            plain_categories={
                "pts": 2,
                "reb": 0,
                "ast": -0.75,
                "stl": -1.5,
                "blk": -1.51,
                "threes": 1,
                "fg_pct": None,
                "ft_pct": -0.2,
                "to": 0.4,
            },
            curved_categories={},
        )
        active = frozenset(row.plain_categories)
        columns = table_columns(active)
        colors = dict(zip(columns, _row_colors(row, active, frozenset(), columns)))
        punt_columns = table_columns(active, frozenset({"blk"}))
        punt_colors = dict(zip(punt_columns, _row_colors(row, active, frozenset({"blk"}), punt_columns)))
        self.assertEqual(colors["Games"], "background-color: #F8E7A0")
        self.assertEqual(colors["Minutes"], "")
        self.assertEqual(colors["FG% / FGA"], "")
        self.assertEqual(colors["Pts"], _DEEP_GREEN)
        self.assertEqual(colors["Tov"], _LIGHT_GREEN)
        self.assertEqual(punt_colors["Pts"], _DEEP_GREEN)
        self.assertEqual(punt_colors["Blk (p)"], "background-color: #E8C2BF; color: #8A8A8A")
        blank_columns = table_columns(active, frozenset({"fg_pct"}))
        blank_colors = dict(
            zip(blank_columns, _row_colors(row, active, frozenset({"fg_pct"}), blank_columns))
        )
        self.assertEqual(blank_colors["FG% / FGA (p)"], "color: #8A8A8A")


if __name__ == "__main__":
    unittest.main()
