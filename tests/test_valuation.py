"""Hand checks for the projection line, the two scores, and the prices."""

import unittest

from fantasyhelper.valuation.prices import (
    MINE,
    OTHER,
    PriceRow,
    Sale,
    apply_punt,
    assign_prices,
    auction_summary,
    build_price_table,
    category_summary,
    max_bid,
    reprice_remaining,
    sale_errors,
)
from fantasyhelper.valuation.projection import (
    COUNTING,
    FileProjection,
    PlayerSources,
    ProjectionLine,
    SeasonTotals,
    project_player,
)


def _counting(**rates: float) -> dict[str, float]:
    values = {key: 0.0 for key, _total, _rate in COUNTING}
    values.update(rates)
    return values


def _totals(games: float, *, minutes: float | None = None, fg_pct: float | None = None) -> SeasonTotals:
    played = games if games else 1
    return SeasonTotals(
        games=games,
        minutes=30 * played if minutes is None else minutes,
        fga=10 * played,
        fta=2 * played,
        fg_pct=fg_pct,
        ft_pct=0.8,
        counting={key: rate * played for key, _total, rate in (
            ("pts", "points", 20.0),
            ("reb", "rebounds", 5.0),
            ("ast", "assists", 4.0),
            ("stl", "steals", 1.0),
            ("blk", "blocks", 0.5),
            ("threes", "threes", 2.0),
            ("to", "turnovers", 2.0),
        )},
    )


def _file(
    *,
    games: float = 70,
    minutes: float = 30,
    fg_pct: float | None = 0.45,
    points: float = 18,
    positions: str = "",
) -> FileProjection:
    return FileProjection(
        games=games,
        minutes_per_game=minutes,
        fga_per_game=12,
        fta_per_game=3,
        fg_pct=fg_pct,
        ft_pct=0.75,
        counting=_counting(pts=points),
        positions=positions,
    )


def _player(
    name: str,
    points: float,
    player_id: int,
) -> ProjectionLine:
    return ProjectionLine(
        player_id=player_id,
        name=name,
        games=70,
        minutes_per_game=30,
        fga_per_game=10,
        fta_per_game=2,
        fg_pct=0.5,
        ft_pct=0.8,
        counting=_counting(pts=points),
    )


class ProjectionTests(unittest.TestCase):
    def test_left_out_without_a_projection_or_last_season(self) -> None:
        player = PlayerSources(1, "Rookie", None, None, ())
        self.assertIsNone(project_player(player))

    def test_a_player_on_no_projection_file_is_left_out(self) -> None:
        for games in (10, 40, 41):
            player = PlayerSources(1, "Veteran", _totals(games, fg_pct=0.5), None, ())
            self.assertIsNone(project_player(player))

    def test_a_projection_keeps_a_player_who_barely_played(self) -> None:
        files = (_file(points=11),)
        player = PlayerSources(1, "Projected", _totals(10), None, files)
        line = project_player(player)
        assert line is not None
        self.assertEqual(line.counting["pts"], 11)

    def test_usage_averages_the_projection_files(self) -> None:
        files = (_file(games=70, minutes=28), _file(games=80, minutes=32))
        player = PlayerSources(1, "Usage", _totals(50), None, files)
        line = project_player(player)
        assert line is not None
        self.assertEqual(line.games, 75)
        self.assertEqual(line.minutes_per_game, 30)

    def test_positions_keep_every_code_from_any_projection_file(self) -> None:
        files = (_file(positions="PG"), _file(positions="PG/SG"), _file(positions="SF/PG"))
        line = project_player(PlayerSources(1, "Guard", None, None, files))
        assert line is not None
        self.assertEqual(line.positions, "PG/SG/SF")
        blank = project_player(PlayerSources(2, "Blank", None, None, (_file(),)))
        assert blank is not None
        self.assertEqual(blank.positions, "")

    def test_close_minutes_keep_last_season_counting_rates(self) -> None:
        last = _totals(50, minutes=30 * 50)
        files = (_file(minutes=34, points=10),)
        line = project_player(PlayerSources(1, "Close", last, None, files))
        assert line is not None
        self.assertEqual(line.counting["pts"], 20)
        self.assertEqual(line.fga_per_game, 12)

    def test_a_4_8_minute_gap_uses_the_projection_average(self) -> None:
        last = _totals(50, minutes=30 * 50)
        files = (_file(minutes=34.8, points=11),)
        line = project_player(PlayerSources(1, "Far", last, None, files))
        assert line is not None
        self.assertEqual(line.counting["pts"], 11)

    def test_forty_games_is_not_a_long_season(self) -> None:
        last = _totals(40, minutes=30 * 40, fg_pct=0.6)
        prior = _totals(50, fg_pct=0.42)
        files = (_file(minutes=30, points=9, fg_pct=0.33),)
        line = project_player(PlayerSources(1, "Border", last, prior, files))
        assert line is not None
        self.assertEqual(line.counting["pts"], 9)
        self.assertEqual(line.fg_pct, 0.42)

    def test_a_blank_projection_percentage_is_skipped(self) -> None:
        files = (_file(fg_pct=None), _file(fg_pct=0.4))
        line = project_player(PlayerSources(1, "Blank", _totals(10), None, files))
        assert line is not None
        self.assertEqual(line.fg_pct, 0.4)


class ScoreTests(unittest.TestCase):
    def test_plain_points_z_and_prices(self) -> None:
        lines = [
            _player("A", 15, 1),
            _player("B", 15, 2),
            _player("C", 25, 3),
            _player("D", 25, 4),
        ]
        table = build_price_table(lines, frozenset({"pts"}), 2, 5, 2)
        by_name = {row.name: row for row in table.rows}
        self.assertAlmostEqual(by_name["C"].plain_score, 1)
        self.assertAlmostEqual(by_name["A"].plain_score, -1)
        self.assertEqual(by_name["C"].plain_rank, 1)
        self.assertEqual(by_name["D"].plain_rank, 2)
        self.assertEqual(by_name["A"].plain_rank, 3)
        self.assertEqual([by_name[name].plain_price for name in "CDAB"], [4, 4, 1, 1])
        self.assertEqual(sum(row.plain_price for row in table.rows), 10)

    def test_prices_follow_the_all_player_rank(self) -> None:
        lines = [
            ProjectionLine(1, "Star", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=30, reb=4)),
            ProjectionLine(2, "Board", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=18, reb=10)),
            ProjectionLine(3, "Weak", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=6, reb=4)),
        ]
        table = build_price_table(lines, frozenset({"pts", "reb"}), 1, 4, 2)
        by_name = {row.name: row for row in table.rows}
        self.assertEqual(by_name["Board"].plain_rank, 1)
        self.assertEqual(by_name["Star"].plain_rank, 2)
        self.assertGreater(by_name["Board"].plain_score, by_name["Star"].plain_score)
        self.assertEqual(
            [by_name[name].plain_price for name in ("Board", "Star", "Weak")],
            [3, 1, 0],
        )

    def test_a_player_outside_the_group_costs_zero(self) -> None:
        lines = [_player("Star", 25, 1), _player("End", 15, 2)]
        table = build_price_table(lines, frozenset({"pts"}), 1, 3, 1)
        by_name = {row.name: row for row in table.rows}
        self.assertEqual(by_name["Star"].plain_price, 3)
        self.assertEqual(by_name["End"].plain_price, 0)
        self.assertEqual(sum(row.plain_price for row in table.rows), 3)

    def test_percentage_impact_uses_games_times_attempts(self) -> None:
        lines = [
            ProjectionLine(1, "High", 10, 30, 10, 2, 0.50, 0.8, _counting()),
            ProjectionLine(2, "Low", 10, 30, 10, 2, 0.40, 0.8, _counting()),
        ]
        table = build_price_table(lines, frozenset({"fg_pct"}), 1, 2, 2)
        by_name = {row.name: row for row in table.rows}
        self.assertAlmostEqual(by_name["High"].plain_categories["fg_pct"], 1)
        self.assertAlmostEqual(by_name["Low"].plain_categories["fg_pct"], -1)

    def test_hand_priced_gaps(self) -> None:
        self.assertEqual(assign_prices([5, 3, 1, 0], 10), [5, 3, 1, 1])

    def test_extra_money_stops_at_the_player_behind_the_paid_group(self) -> None:
        self.assertEqual(assign_prices([8, 7, 6, 5, 0], 15, paid_count=3), [7, 4, 2, 1, 1])

    def test_equal_scores_hand_the_remainder_down_from_rank_one(self) -> None:
        self.assertEqual(assign_prices([0, 0, 0], 5), [2, 2, 1])

    def test_ten_players_per_team_keep_the_extra_money(self) -> None:
        lines = [_player(f"P{index:02d}", float(30 - index), index + 1) for index in range(13)]
        table = build_price_table(lines, frozenset({"pts"}), 1, 20, 12)
        prices = [row.plain_price for row in table.rows]
        self.assertEqual(prices[10:12], [1, 1])
        self.assertEqual(prices[12], 0)
        self.assertEqual(sum(prices), 20)
        roster_scores = [row.plain_score for row in table.rows[:12]]
        self.assertEqual(prices[:12], assign_prices(roster_scores, 20, paid_count=10))

    def test_a_punt_drops_a_category_without_rescoring_it(self) -> None:
        lines = [
            ProjectionLine(1, "Star", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=30, reb=4)),
            ProjectionLine(2, "Board", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=18, reb=10)),
            ProjectionLine(3, "Weak", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=6, reb=4)),
        ]
        base = build_price_table(lines, frozenset({"pts", "reb"}), 1, 4, 2)
        untouched = apply_punt(base.rows, frozenset(), 1, 4, 2)
        self.assertIsNone(untouched[0].personal_plain_rank)
        self.assertEqual([row.name for row in untouched], [row.name for row in base.rows])

        punted = apply_punt(base.rows, frozenset({"reb"}), 1, 4, 2)
        by_base = {row.name: row for row in base.rows}
        by_name = {row.name: row for row in punted}
        self.assertEqual([row.name for row in punted], ["Star", "Board", "Weak"])
        star = by_name["Star"]
        self.assertEqual(star.plain_categories, by_base["Star"].plain_categories)
        self.assertEqual(star.plain_score, by_base["Star"].plain_score)
        self.assertEqual(star.plain_rank, by_base["Star"].plain_rank)
        self.assertEqual(star.plain_price, by_base["Star"].plain_price)
        self.assertEqual(star.personal_plain_rank, 1)
        self.assertEqual(star.personal_plain_price, 3)
        self.assertEqual(by_name["Board"].personal_plain_rank, 2)
        self.assertEqual(by_name["Board"].personal_plain_price, 1)
        self.assertEqual(by_name["Weak"].personal_plain_price, 0)
        self.assertEqual(sum(row.personal_plain_price or 0 for row in punted), 4)

    def test_no_sales_keep_the_base_prices(self) -> None:
        lines = [_player(name, points, index) for index, (name, points) in enumerate(
            (("A", 40), ("B", 30), ("C", 20), ("D", 10)), start=1
        )]
        base = build_price_table(lines, frozenset({"pts"}), 1, 10, 2)
        again = reprice_remaining(base.rows, (), 1, 10, 2)
        self.assertIsNone(again.error)
        self.assertEqual(
            [(row.name, row.plain_price) for row in again.rows],
            [(row.name, row.plain_price) for row in base.rows],
        )

    def test_a_sale_reprices_the_players_still_available(self) -> None:
        lines = [_player(name, points, index) for index, (name, points) in enumerate(
            (("A", 40), ("B", 30), ("C", 20), ("D", 10)), start=1
        )]
        base = build_price_table(lines, frozenset({"pts"}), 1, 10, 2)
        sold = (Sale(1, "mine", 4, "keeper"),)
        auction = reprice_remaining(base.rows, sold, 1, 10, 2)
        self.assertIsNone(auction.error)
        by_name = {row.name: row for row in auction.rows}
        self.assertNotIn("A", by_name)
        self.assertEqual(by_name["B"].plain_price, 6)
        self.assertEqual(by_name["C"].plain_price, 0)
        self.assertEqual(by_name["D"].plain_price, 0)
        self.assertEqual(sum(row.plain_price for row in auction.rows), 6)
        self.assertEqual(by_name["B"].plain_categories, {row.name: row for row in base.rows}["B"].plain_categories)

    def test_a_punt_uses_the_money_left_after_sales(self) -> None:
        lines = [
            ProjectionLine(1, "Star", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=30, reb=4)),
            ProjectionLine(2, "Board", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=18, reb=10)),
            ProjectionLine(3, "Weak", 70, 30, 10, 2, 0.5, 0.8, _counting(pts=6, reb=4)),
        ]
        base = build_price_table(lines, frozenset({"pts", "reb"}), 1, 4, 2)
        sold = (Sale(2, "other", 1, "draft"),)
        auction = reprice_remaining(base.rows, sold, 1, 4, 2, frozenset({"reb"}))
        self.assertIsNone(auction.error)
        self.assertEqual([row.name for row in auction.rows], ["Star", "Weak"])
        self.assertEqual(sum(row.personal_plain_price or 0 for row in auction.rows), 3)
        self.assertEqual(auction.rows[0].plain_categories["reb"], {row.name: row for row in base.rows}["Star"].plain_categories["reb"])

    def test_max_bid_leaves_a_dollar_for_later_spots(self) -> None:
        self.assertEqual(max_bid(200, 13, ()), 188)
        kept = (Sale(1, "mine", 160, "keeper"),)
        self.assertEqual(max_bid(200, 13, kept), 29)
        filled = tuple(Sale(index, "mine", 1, "draft") for index in range(1, 14))
        self.assertIsNone(max_bid(200, 13, filled))
        almost = tuple(Sale(index, "mine", 10, "keeper") for index in range(1, 13))
        self.assertEqual(max_bid(200, 13, almost), 80)

    def test_auction_summary_splits_the_league_and_the_user(self) -> None:
        sales = (
            Sale(1, "mine", 40, "keeper"),
            Sale(2, "other", 15, "draft"),
        )
        summary = auction_summary(12, 200, 13, sales)
        self.assertEqual(summary.league_spent, 55)
        self.assertEqual(summary.league_left, 12 * 200 - 55)
        self.assertEqual(summary.league_taken, 2)
        self.assertEqual(summary.league_open, 12 * 13 - 2)
        self.assertEqual(summary.yours_spent, 40)
        self.assertEqual(summary.yours_left, 160)
        self.assertEqual(summary.yours_taken, 1)
        self.assertEqual(summary.yours_open, 12)
        self.assertEqual(summary.max_bid, 149)

    def test_a_price_above_the_max_bid_is_refused(self) -> None:
        errors = sale_errors((), 1, "mine", 189, "keeper", 12, 200, 13)
        self.assertEqual(errors, ("That price is above your max bid of $188.",))
        self.assertEqual(sale_errors((), 1, "mine", 188, "keeper", 12, 200, 13), ())
        self.assertEqual(
            sale_errors((), 1, "other", 201, "draft", 12, 200, 13),
            ("That price is above this league's budget of $200.",),
        )
        self.assertEqual(sale_errors((), 1, "mine", 0, "keeper", 12, 200, 13), ("Enter a price of at least $1.",))
        sold = (Sale(1, "mine", 50, "keeper"),)
        self.assertEqual(
            sale_errors(sold, 1, "mine", 50, "keeper", 12, 200, 13),
            ("That player is already sold.",),
        )
        self.assertEqual(sale_errors(sold, 1, "mine", 40, "draft", 12, 200, 13, replacing=True), ())


def _summary_row(
    player_id: int,
    *,
    points: float,
    points_z: float,
    fg_pct: float | None,
    fg_z: float | None,
    games: float,
    fga: float,
) -> PriceRow:
    return PriceRow(
        player_id=player_id,
        name=str(player_id),
        plain_rank=1,
        plain_score=0,
        plain_price=1,
        curved_rank=1,
        curved_score=0,
        curved_price=1,
        games=games,
        minutes_per_game=30,
        fga_per_game=fga,
        fta_per_game=2,
        fg_pct=fg_pct,
        ft_pct=0.8,
        counting={"pts": points},
        plain_categories={"pts": points_z, "fg_pct": fg_z},
        curved_categories={},
    )


class SummaryTests(unittest.TestCase):
    def test_the_league_row_includes_the_user_and_averages_each_player(self) -> None:
        rows = {
            1: _summary_row(1, points=10, points_z=1, fg_pct=0.50, fg_z=0, games=60, fga=10),
            2: _summary_row(2, points=20, points_z=3, fg_pct=0.40, fg_z=2, games=80, fga=20),
            3: _summary_row(3, points=100, points_z=9, fg_pct=0.70, fg_z=4, games=70, fga=15),
        }
        sales = (
            Sale(1, MINE, 30, "keeper"),
            Sale(2, OTHER, 10, "draft"),
        )
        league, user = category_summary(rows, sales, frozenset({"pts", "fg_pct"}), 12, 200, 13)
        self.assertEqual(league.money_left, 2400 - 40)
        self.assertEqual(league.money_spent, 40)
        self.assertEqual(league.spots_left, 156 - 2)
        self.assertEqual(league.spots_taken, 2)
        self.assertEqual(league.categories["pts"].rate, 15)
        self.assertEqual(league.categories["pts"].average_z, 2)
        self.assertAlmostEqual(league.categories["fg_pct"].percentage or 0, 940 / 2200)
        self.assertEqual(league.categories["fg_pct"].attempts, 15)
        self.assertEqual(user.money_left, 170)
        self.assertEqual(user.money_spent, 30)
        self.assertEqual(user.spots_left, 12)
        self.assertEqual(user.spots_taken, 1)
        self.assertEqual(user.categories["pts"].rate, 10)
        self.assertEqual(user.categories["pts"].average_z, 1)
        self.assertEqual(user.categories["fg_pct"].percentage, 0.50)
        self.assertEqual(user.categories["fg_pct"].attempts, 10)

    def test_a_missing_projection_counts_in_the_money_only(self) -> None:
        rows = {
            1: _summary_row(1, points=10, points_z=1, fg_pct=0.50, fg_z=0, games=60, fga=10),
        }
        sales = (
            Sale(1, MINE, 30, "keeper"),
            Sale(9, MINE, 5, "draft"),
        )
        _league, user = category_summary(rows, sales, frozenset({"pts"}), 12, 200, 13)
        self.assertEqual(user.money_spent, 35)
        self.assertEqual(user.spots_taken, 2)
        self.assertEqual(user.categories["pts"].rate, 10)

    def test_a_missing_percentage_is_left_out_of_the_average(self) -> None:
        rows = {
            1: _summary_row(1, points=10, points_z=1, fg_pct=None, fg_z=None, games=60, fga=10),
            2: _summary_row(2, points=20, points_z=3, fg_pct=0.40, fg_z=2, games=80, fga=20),
        }
        sales = (Sale(1, MINE, 30, "keeper"), Sale(2, OTHER, 10, "draft"))
        league, _user = category_summary(rows, sales, frozenset({"fg_pct"}), 12, 200, 13)
        self.assertEqual(league.categories["fg_pct"].percentage, 0.40)
        self.assertEqual(league.categories["fg_pct"].attempts, 15)
        self.assertEqual(league.categories["fg_pct"].average_z, 2)

    def test_an_empty_side_keeps_the_money_and_blanks_the_categories(self) -> None:
        league, user = category_summary({}, (), frozenset({"pts", "blk"}), 12, 200, 13)
        self.assertEqual(league.money_left, 2400)
        self.assertEqual(league.money_spent, 0)
        self.assertEqual(league.spots_left, 156)
        self.assertEqual(league.spots_taken, 0)
        self.assertEqual(user.money_left, 200)
        self.assertEqual(user.spots_left, 13)
        self.assertIsNone(league.categories["pts"].rate)
        self.assertIsNone(league.categories["pts"].average_z)
        self.assertIsNone(user.categories["blk"].rate)


if __name__ == "__main__":
    unittest.main()
