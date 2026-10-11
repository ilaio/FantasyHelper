"""The alias list joins spellings the name key would otherwise split."""

import unittest

from fantasyhelper.stats.names import canonical_name_key


class AliasTests(unittest.TestCase):
    def test_suffix_splits_share_one_key(self) -> None:
        pairs = (
            ("Robert Williams", "Robert Williams III"),
            ("Jimmy Butler", "Jimmy Butler III"),
            ("Derrick Jones", "Derrick Jones Jr."),
            ("Kelly Oubre", "Kelly Oubre Jr."),
        )
        for short, full in pairs:
            self.assertEqual(canonical_name_key(short), canonical_name_key(full))


if __name__ == "__main__":
    unittest.main()
