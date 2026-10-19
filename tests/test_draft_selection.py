"""Which list row matches the open player."""

import unittest

from fantasyhelper.ui.draft import (
    checked_row,
    form_changed,
    open_player_after_check,
    ordered_taken,
    player_price_line,
    roster_table_height,
    search_pick_stands,
    taken_title,
    team_buttons,
)
from fantasyhelper.valuation.prices import DRAFT, KEEPER, MINE, OTHER, PriceRow, Sale


class CheckedRowTests(unittest.TestCase):
    def test_no_player_checks_nothing(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), None), [])

    def test_the_open_player_is_the_only_checked_row(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), 9), [1])
        self.assertEqual(checked_row((4, 9, 2), 2), [2])

    def test_a_player_outside_the_list_checks_nothing(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), 7), [])


class SearchPickTests(unittest.TestCase):
    def test_a_new_search_stands_over_a_list_check(self) -> None:
        self.assertTrue(search_pick_stands(8, 4, shown_known=True))

    def test_clearing_the_search_stands(self) -> None:
        self.assertTrue(search_pick_stands(None, 4, shown_known=True))

    def test_a_list_click_replaces_the_open_player(self) -> None:
        self.assertFalse(search_pick_stands(4, 4, shown_known=True))

    def test_the_first_list_click_is_kept_before_a_player_was_shown(self) -> None:
        self.assertFalse(search_pick_stands(8, None, shown_known=False))


class OpenPlayerAfterCheckTests(unittest.TestCase):
    def test_clearing_the_open_players_row_clears_the_search(self) -> None:
        self.assertIsNone(open_player_after_check(4, (4, 9), ()))

    def test_clearing_another_list_leaves_the_open_player(self) -> None:
        self.assertEqual(open_player_after_check(4, (9, 2), ()), 4)

    def test_a_checked_row_opens_that_player(self) -> None:
        self.assertEqual(open_player_after_check(4, (9, 2), (1,)), 2)

    def test_a_row_outside_the_list_leaves_the_open_player(self) -> None:
        self.assertEqual(open_player_after_check(4, (9, 2), (5,)), 4)


class TakenListTests(unittest.TestCase):
    def test_your_players_follow_position_then_fewer_positions(self) -> None:
        sales = (
            Sale(1, MINE, 10, "draft"),
            Sale(2, MINE, 8, "draft"),
            Sale(3, MINE, 12, "draft"),
            Sale(4, MINE, 9, "draft"),
            Sale(5, MINE, 7, "draft"),
        )
        positions = {1: "SG", 2: "PG/SG", 3: "PG", 4: "C", 5: "SF/PF"}
        names = {1: "Guard", 2: "Combo", 3: "Point", 4: "Center", 5: "Forward"}
        ordered = ordered_taken(sales, MINE, positions, names, newest_first=False)
        self.assertEqual([sale.player_id for sale in ordered], [3, 2, 1, 5, 4])

    def test_a_player_with_no_position_sorts_last(self) -> None:
        sales = (Sale(1, MINE, 4, "draft"), Sale(2, MINE, 4, "draft"))
        ordered = ordered_taken(
            sales,
            MINE,
            {1: "", 2: "C"},
            {1: "Unknown", 2: "Center"},
            newest_first=False,
        )
        self.assertEqual([sale.player_id for sale in ordered], [2, 1])

    def test_other_teams_are_newest_first(self) -> None:
        sales = (
            Sale(1, OTHER, 5, "draft"),
            Sale(2, MINE, 9, "draft"),
            Sale(3, OTHER, 6, "draft"),
        )
        ordered = ordered_taken(sales, OTHER, {}, {}, newest_first=True)
        self.assertEqual([sale.player_id for sale in ordered], [3, 1])

    def test_titles_count_each_side_against_its_spots(self) -> None:
        self.assertEqual(taken_title("Your players", 1, 10), "Your players (1/10)")
        self.assertEqual(taken_title("Other teams", 5, 90), "Other teams (5/90)")

    def test_the_table_height_fits_one_roster(self) -> None:
        self.assertEqual(roster_table_height(10), 10 * 35 + 35 + 2)


class PlayerPriceLineTests(unittest.TestCase):
    def test_the_line_shows_tz_tc_pc_and_the_max_bid(self) -> None:
        row = _price_row(plain_price=14, curved_price=9, personal_curved_price=6)
        self.assertEqual(
            player_price_line(row, "$40"),
            "<span class='price-param'>TZ Price: <strong>$14</strong></span>"
            "<span class='price-param'>TC Price: <strong>$9</strong></span>"
            "<span class='price-param'>PC Price: <strong>$6</strong></span>"
            "<span class='price-param'>Max bid: <strong>$40</strong></span>",
        )

    def test_a_missing_pc_price_stays_blank(self) -> None:
        row = _price_row(plain_price=1, curved_price=0, personal_curved_price=None)
        self.assertEqual(
            player_price_line(row, "No spot left"),
            "<span class='price-param'>TZ Price: <strong>$1</strong></span>"
            "<span class='price-param'>TC Price: <strong>$0</strong></span>"
            "<span class='price-param'>PC Price: <strong></strong></span>"
            "<span class='price-param'>Max bid: <strong>No spot left</strong></span>",
        )

    def test_no_player_leaves_the_three_prices_blank(self) -> None:
        self.assertEqual(
            player_price_line(None, "$200"),
            "<span class='price-param'>TZ Price: <strong></strong></span>"
            "<span class='price-param'>TC Price: <strong></strong></span>"
            "<span class='price-param'>PC Price: <strong></strong></span>"
            "<span class='price-param'>Max bid: <strong>$200</strong></span>",
        )


class TeamButtonTests(unittest.TestCase):
    def test_a_new_player_can_be_added_to_either_side(self) -> None:
        self.assertEqual(
            team_buttons(None),
            (("Add to my team", MINE, False), ("Add to another", OTHER, False)),
        )

    def test_a_player_on_my_team_edits_there_or_switches(self) -> None:
        sale = Sale(1, MINE, 8, DRAFT)
        self.assertEqual(
            team_buttons(sale),
            (("Edit my team", MINE, True), ("Switch to another", OTHER, False)),
        )
        self.assertFalse(form_changed(sale, DRAFT, 8))
        self.assertTrue(form_changed(sale, KEEPER, 8))
        self.assertTrue(form_changed(sale, DRAFT, 9))

    def test_a_player_on_another_team_switches_or_edits_there(self) -> None:
        sale = Sale(1, OTHER, 5, KEEPER)
        self.assertEqual(
            team_buttons(sale),
            (("Switch to my team", MINE, False), ("Edit in another", OTHER, True)),
        )
        self.assertFalse(form_changed(sale, KEEPER, 5))


def _price_row(
    *,
    plain_price: int,
    curved_price: int,
    personal_curved_price: int | None,
) -> PriceRow:
    return PriceRow(
        player_id=1,
        name="A",
        plain_rank=1,
        plain_score=0,
        plain_price=plain_price,
        curved_rank=1,
        curved_score=0,
        curved_price=curved_price,
        games=70,
        minutes_per_game=30,
        fga_per_game=10,
        fta_per_game=2,
        fg_pct=0.5,
        ft_pct=0.8,
        counting={},
        plain_categories={},
        curved_categories={},
        personal_curved_price=personal_curved_price,
    )


if __name__ == "__main__":
    unittest.main()
