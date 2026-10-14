"""Which list row matches the open player."""

import unittest

from fantasyhelper.ui.draft import checked_row, open_player_after_check, search_pick_stands


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


if __name__ == "__main__":
    unittest.main()
