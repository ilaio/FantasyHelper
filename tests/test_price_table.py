"""Display rules for the price table."""

import unittest

from fantasyhelper.ui.prices import (
    _row_colors,
    column_alignment,
    price_format,
    shot_text,
    strength_color,
    table_columns,
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
        self.assertEqual(columns[7], "FT% / FTA")
        self.assertEqual(columns[:5], ["Name", "Z Rank", "Z Price", "C Rank", "C Price"])
        self.assertEqual(columns[-2:], ["Z Score", "C Score"])
        self.assertEqual(column_alignment("Name"), "left")
        self.assertTrue(all(column_alignment(name) == "center" for name in columns[1:]))
        self.assertEqual(price_format("Z Price"), "$%d")
        self.assertEqual(price_format("C Price"), "$%d")
        self.assertIsNone(price_format("Z Rank"))

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
        colors = dict(zip(columns, _row_colors(row, active, columns)))
        self.assertEqual(colors["Games"], "background-color: #F8E7A0")
        self.assertEqual(colors["Minutes"], "")
        self.assertEqual(colors["FG% / FGA"], "")
        self.assertEqual(colors["Points"], _DEEP_GREEN)
        self.assertEqual(colors["Turnovers"], _LIGHT_GREEN)


if __name__ == "__main__":
    unittest.main()
