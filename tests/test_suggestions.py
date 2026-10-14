"""Nominations and targets from the price gap and the summary."""

import unittest

from fantasyhelper.valuation.prices import (
    CategoryAverage,
    PriceRow,
    SideSummary,
    draft_suggestions,
)


def _row(
    player_id: int,
    name: str,
    tz: int,
    tc: int,
    *,
    pz: int | None = None,
    pc: int | None = None,
    tz_rank: int = 1,
    tc_rank: int = 1,
    pc_rank: int | None = None,
    **scores: float,
) -> PriceRow:
    return PriceRow(
        player_id=player_id,
        name=name,
        plain_rank=tz_rank,
        plain_score=0,
        plain_price=tz,
        curved_rank=tc_rank,
        curved_score=0,
        curved_price=tc,
        games=70,
        minutes_per_game=30,
        fga_per_game=10,
        fta_per_game=2,
        fg_pct=0.5,
        ft_pct=0.8,
        counting={},
        plain_categories=scores,
        curved_categories={},
        personal_plain_price=pz,
        personal_curved_price=pc,
        personal_curved_rank=pc_rank,
    )


def _side(**scores: float | None) -> SideSummary:
    categories = {
        key: CategoryAverage(None, None, None, score) for key, score in scores.items()
    }
    return SideSummary(0, 0, 0, 0, categories)


class SuggestionTests(unittest.TestCase):
    def test_without_a_punt_the_gap_is_tz_above_tc(self) -> None:
        available = (
            _row(1, "Wide", 30, 10, blk=0),
            _row(2, "Flat", 20, 20, blk=3),
            _row(3, "Close", 12, 9, blk=0),
        )
        nominations, _targets = draft_suggestions(
            available,
            _side(blk=None),
            _side(blk=None),
            ("blk",),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in nominations], ["Wide", "Close"])
        self.assertEqual(nominations[0].categories, ())
        self.assertEqual(nominations[0].room_price, 30)
        self.assertEqual(nominations[0].balance_price, 10)

    def test_a_punt_measures_the_gap_from_the_personal_curved_price(self) -> None:
        available = (_row(1, "Spike", 40, 35, pz=12, pc=10, blk=3),)
        nominations, _targets = draft_suggestions(
            available,
            _side(blk=None),
            _side(blk=None),
            ("blk",),
            frozenset({"blk"}),
            100,
        )
        self.assertEqual(nominations[0].balance_price, 10)
        self.assertEqual(nominations[0].room_price - nominations[0].balance_price, 30)

    def test_deep_green_categories_are_searched_first_for_green_players(self) -> None:
        available = (
            _row(1, "Bigger gap", 30, 10, blk=0.9),
            _row(2, "Green", 10, 7, blk=1),
            _row(3, "Deep", 8, 6, blk=2.4, ft_pct=1.2),
        )
        nominations, _targets = draft_suggestions(
            available,
            _side(blk=2, ft_pct=2.5),
            _side(blk=0, ft_pct=0),
            ("ft_pct", "blk"),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in nominations], ["Green", "Deep", "Bigger gap"])
        self.assertEqual(nominations[0].categories, ("blk",))
        self.assertEqual(nominations[1].categories, ("ft_pct", "blk"))
        self.assertEqual(nominations[2].categories, ())

    def test_a_nomination_is_left_off_the_targets(self) -> None:
        available = (
            _row(1, "Both", 40, 20, ft_pct=2),
            _row(2, "Fit", 15, 15, ft_pct=1.4),
        )
        _nominations, targets = draft_suggestions(
            available,
            _side(ft_pct=-1),
            _side(ft_pct=0),
            ("ft_pct",),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in targets], ["Fit"])
        self.assertEqual(targets[0].categories, ("ft_pct",))

    def test_with_no_roster_targets_follow_the_curved_price(self) -> None:
        available = (
            _row(1, "Plain", 30, 10, ft_pct=0),
            _row(2, "Curved", 11, 12, ft_pct=0),
        )
        nominations, targets = draft_suggestions(
            available,
            _side(ft_pct=None),
            _side(ft_pct=None),
            ("ft_pct",),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in nominations], ["Plain"])
        self.assertEqual([item.name for item in targets], ["Curved"])
        self.assertEqual(targets[0].categories, ())

    def test_the_smallest_lead_is_the_target_when_the_user_is_ahead(self) -> None:
        available = (
            _row(1, "Blocks", 10, 10, blk=2, ft_pct=0),
            _row(2, "Free throws", 8, 8, blk=0, ft_pct=1),
        )
        _nominations, targets = draft_suggestions(
            available,
            _side(blk=1.0, ft_pct=0.2),
            _side(blk=0.5, ft_pct=0.0),
            ("blk", "ft_pct"),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in targets], ["Free throws"])

    def test_a_punted_category_is_not_the_target_category(self) -> None:
        available = (_row(1, "Scorer", 14, 18, pz=16, pc=15, ft_pct=3, pts=1.5),)
        _nominations, targets = draft_suggestions(
            available,
            _side(ft_pct=-2, pts=-0.2),
            _side(ft_pct=0, pts=0),
            ("ft_pct", "pts"),
            frozenset({"ft_pct"}),
            100,
        )
        self.assertEqual(targets[0].categories, ("pts",))
        self.assertEqual(targets[0].balance_price, 15)
        self.assertEqual(targets[0].pay_price, 16)

    def test_the_same_gap_follows_how_far_tz_rank_sits_above_tc_rank(self) -> None:
        available = (
            _row(1, "Even", 5, 4, tz_rank=10, tc_rank=12),
            _row(2, "Ahead", 5, 4, tz_rank=20, tc_rank=50),
            _row(3, "Flat", 8, 8, tz_rank=1, tc_rank=40),
        )
        nominations, _targets = draft_suggestions(
            available,
            _side(blk=None),
            _side(blk=None),
            ("blk",),
            frozenset(),
            100,
        )
        self.assertEqual([item.name for item in nominations], ["Ahead", "Even"])

    def test_a_punt_breaks_a_tied_gap_with_pc_rank(self) -> None:
        available = (
            _row(1, "Room", 5, 1, pz=5, pc=4, tz_rank=3, tc_rank=40, pc_rank=4),
            _row(2, "Personal", 5, 1, pz=5, pc=4, tz_rank=30, tc_rank=2, pc_rank=40),
        )
        nominations, _targets = draft_suggestions(
            available,
            _side(blk=None),
            _side(blk=None),
            ("blk",),
            frozenset({"blk"}),
            100,
        )
        self.assertEqual([item.name for item in nominations], ["Personal", "Room"])

    def test_the_same_curved_price_follows_the_curved_rank(self) -> None:
        available = (
            _row(1, "Later", 4, 8, tz_rank=2, tc_rank=15),
            _row(2, "Sooner", 3, 8, tz_rank=20, tc_rank=4),
            _row(3, "Pricier", 2, 9, tz_rank=1, tc_rank=40),
        )
        nominations, targets = draft_suggestions(
            available,
            _side(ft_pct=None),
            _side(ft_pct=None),
            ("ft_pct",),
            frozenset(),
            100,
        )
        self.assertEqual(nominations, ())
        self.assertEqual([item.name for item in targets], ["Pricier", "Sooner", "Later"])

    def test_a_punt_breaks_a_tied_curved_price_with_pc_rank(self) -> None:
        available = (
            _row(1, "Room rank", 4, 9, pz=4, pc=6, tc_rank=2, pc_rank=12, pts=1.2),
            _row(2, "Personal rank", 4, 3, pz=4, pc=6, tc_rank=30, pc_rank=5, pts=1.2),
        )
        nominations, targets = draft_suggestions(
            available,
            _side(pts=None),
            _side(pts=None),
            ("pts",),
            frozenset({"pts"}),
            100,
        )
        self.assertEqual(nominations, ())
        self.assertEqual([item.name for item in targets], ["Personal rank", "Room rank"])

    def test_a_price_above_the_max_bid_is_not_a_target(self) -> None:
        available = (_row(1, "Too much", 50, 50, ft_pct=2),)
        _nominations, targets = draft_suggestions(
            available,
            _side(ft_pct=-1),
            _side(ft_pct=0),
            ("ft_pct",),
            frozenset(),
            40,
        )
        self.assertEqual(targets, ())


if __name__ == "__main__":
    unittest.main()
