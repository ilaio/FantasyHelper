"""Which list row matches the open player."""

import unittest

from fantasyhelper.ui.draft import checked_row


class CheckedRowTests(unittest.TestCase):
    def test_no_player_checks_nothing(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), None), [])

    def test_the_open_player_is_the_only_checked_row(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), 9), [1])
        self.assertEqual(checked_row((4, 9, 2), 2), [2])

    def test_a_player_outside_the_list_checks_nothing(self) -> None:
        self.assertEqual(checked_row((4, 9, 2), 7), [])


if __name__ == "__main__":
    unittest.main()
