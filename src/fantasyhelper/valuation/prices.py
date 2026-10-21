"""Ranks and prices from projection lines. Both results are calculated."""

import math
from dataclasses import dataclass, replace

from fantasyhelper.valuation.projection import ProjectionLine

_TURNOVERS = "to"
_PAID_PER_TEAM = 10
_PERCENTAGES = (
    ("fg_pct", "fga_per_game"),
    ("ft_pct", "fta_per_game"),
)


@dataclass(frozen=True)
class PriceRow:
    player_id: int
    name: str
    plain_rank: int
    plain_score: float
    plain_price: int
    curved_rank: int
    curved_score: float
    curved_price: int
    games: float
    minutes_per_game: float
    fga_per_game: float
    fta_per_game: float
    fg_pct: float | None
    ft_pct: float | None
    counting: dict[str, float]
    plain_categories: dict[str, float | None]
    curved_categories: dict[str, float | None]
    personal_plain_rank: int | None = None
    personal_plain_price: int | None = None
    personal_curved_rank: int | None = None
    personal_curved_price: int | None = None
    positions: str = ""


@dataclass(frozen=True)
class PriceTable:
    rows: tuple[PriceRow, ...]
    error: str | None


@dataclass(frozen=True)
class Sale:
    """One keeper or draft sale. The sale type does not change the price."""

    player_id: int
    side: str
    price: int
    sale_type: str


MINE = "mine"
OTHER = "other"
KEEPER = "keeper"
DRAFT = "draft"
_SIDES = frozenset({MINE, OTHER})
_SALE_TYPES = frozenset({KEEPER, DRAFT})


def build_price_table(
    lines: list[ProjectionLine],
    categories: frozenset[str],
    team_count: int,
    budget: int,
    roster_size: int,
) -> PriceTable:
    if budget < roster_size:
        return PriceTable(
            rows=(),
            error=(
                "This league's budget is smaller than its roster, "
                "so a $1 bid cannot fill every spot."
            ),
        )
    if not lines:
        return PriceTable(rows=(), error=None)

    plain_parts = _category_scores(lines, categories, curved=False)
    curved_parts = _category_scores(lines, categories, curved=True)
    plain_totals = [_total(parts) for parts in plain_parts]
    curved_totals = [_total(parts) for parts in curved_parts]
    plain_order = _order(lines, plain_totals)
    curved_order = _order(lines, curved_totals)
    pool_size = team_count * roster_size
    total_budget = team_count * budget
    plain_prices = _prices_for(
        lines, plain_order, plain_totals, pool_size, total_budget, team_count
    )
    curved_prices = _prices_for(
        lines, curved_order, curved_totals, pool_size, total_budget, team_count
    )
    plain_rank = _ranks(plain_order)
    curved_rank = _ranks(curved_order)
    rows = [
        _row(
            line,
            plain_rank[index],
            plain_totals[index],
            plain_prices[line.player_id],
            curved_rank[index],
            curved_totals[index],
            curved_prices[line.player_id],
            plain_parts[index],
            curved_parts[index],
        )
        for index, line in enumerate(lines)
    ]
    rows.sort(key=lambda item: item.plain_rank)
    return PriceTable(rows=tuple(rows), error=None)


def apply_punt(
    rows: tuple[PriceRow, ...],
    punted: frozenset[str],
    team_count: int,
    budget: int,
    roster_size: int,
) -> tuple[PriceRow, ...]:
    """Rank and price again with the punted categories left out of both totals.

    Category z-scores stay as they are. An empty punt returns the base rows.
    """
    if not punted:
        return rows
    plain_totals = [_kept_total(row.plain_categories, punted) for row in rows]
    curved_totals = [_kept_total(row.curved_categories, punted) for row in rows]
    plain_order = _order_named(rows, plain_totals)
    curved_order = _order_named(rows, curved_totals)
    pool_size = team_count * roster_size
    total_budget = team_count * budget
    plain_prices = _prices_named(
        rows, plain_order, plain_totals, pool_size, total_budget, team_count
    )
    curved_prices = _prices_named(
        rows, curved_order, curved_totals, pool_size, total_budget, team_count
    )
    plain_rank = _ranks(plain_order)
    curved_rank = _ranks(curved_order)
    updated = [
        replace(
            row,
            personal_plain_rank=plain_rank[index],
            personal_plain_price=plain_prices[row.player_id],
            personal_curved_rank=curved_rank[index],
            personal_curved_price=curved_prices[row.player_id],
        )
        for index, row in enumerate(rows)
    ]
    updated.sort(key=lambda item: item.personal_plain_rank or 0)
    return tuple(updated)


def with_personal_prices(
    rows: tuple[PriceRow, ...],
    punted: frozenset[str],
    team_count: int,
    budget: int,
    roster_size: int,
) -> tuple[PriceRow, ...]:
    """Keep this order. A punt fills the personal rank and price from the full pool."""
    if not punted:
        return rows
    personal = {
        row.player_id: row
        for row in apply_punt(rows, punted, team_count, budget, roster_size)
    }
    return tuple(
        replace(
            row,
            personal_plain_rank=personal[row.player_id].personal_plain_rank,
            personal_plain_price=personal[row.player_id].personal_plain_price,
            personal_curved_rank=personal[row.player_id].personal_curved_rank,
            personal_curved_price=personal[row.player_id].personal_curved_price,
        )
        for row in rows
    )


@dataclass(frozen=True)
class AuctionSummary:
    """League and user money and spots, plus the user's max bid."""

    league_spent: int
    league_left: int
    league_taken: int
    league_open: int
    yours_spent: int
    yours_left: int
    yours_taken: int
    yours_open: int
    max_bid: int | None


def auction_summary(
    team_count: int,
    budget: int,
    roster_size: int,
    sales: tuple[Sale, ...],
) -> AuctionSummary:
    """Spent and left for the league and for this user."""
    league_spent = sum(sale.price for sale in sales)
    yours_spent = sum(sale.price for sale in sales if sale.side == MINE)
    league_taken = len(sales)
    yours_taken = sum(1 for sale in sales if sale.side == MINE)
    return AuctionSummary(
        league_spent=league_spent,
        league_left=team_count * budget - league_spent,
        league_taken=league_taken,
        league_open=team_count * roster_size - league_taken,
        yours_spent=yours_spent,
        yours_left=budget - yours_spent,
        yours_taken=yours_taken,
        yours_open=roster_size - yours_taken,
        max_bid=max_bid(budget, roster_size, sales),
    )


@dataclass(frozen=True)
class CategoryAverage:
    """One category on one summary row. An empty group stays blank."""

    rate: float | None
    percentage: float | None
    attempts: float | None
    average_z: float | None


@dataclass(frozen=True)
class SideSummary:
    """Money, spots, and category averages for the league or the user."""

    money_left: int
    money_spent: int
    spots_left: int
    spots_taken: int
    categories: dict[str, CategoryAverage]


def category_summary(
    rows_by_id: dict[int, PriceRow],
    sales: tuple[Sale, ...],
    categories: frozenset[str],
    team_count: int,
    budget: int,
    roster_size: int,
) -> tuple[SideSummary, SideSummary]:
    """League first, then the user. Available players are on neither row."""
    money = auction_summary(team_count, budget, roster_size, sales)
    league_rows = _summary_rows(sales, rows_by_id)
    user_rows = _summary_rows(
        tuple(sale for sale in sales if sale.side == MINE),
        rows_by_id,
    )
    return (
        SideSummary(
            money.league_left,
            money.league_spent,
            money.league_open,
            money.league_taken,
            _category_averages(league_rows, categories),
        ),
        SideSummary(
            money.yours_left,
            money.yours_spent,
            money.yours_open,
            money.yours_taken,
            _category_averages(user_rows, categories),
        ),
    )


def _summary_rows(
    sales: tuple[Sale, ...],
    rows_by_id: dict[int, PriceRow],
) -> list[PriceRow]:
    """Projected players on this side. A sale with no projection is left out."""
    rows: list[PriceRow] = []
    seen: set[int] = set()
    for sale in sales:
        if sale.player_id in seen:
            continue
        seen.add(sale.player_id)
        row = rows_by_id.get(sale.player_id)
        if row is not None:
            rows.append(row)
    return rows


def _category_averages(
    rows: list[PriceRow],
    categories: frozenset[str],
) -> dict[str, CategoryAverage]:
    return {key: _category_average(rows, key) for key in categories}


def _category_average(rows: list[PriceRow], key: str) -> CategoryAverage:
    if not rows:
        return CategoryAverage(None, None, None, None)
    scores = [
        row.plain_categories[key]
        for row in rows
        if key in row.plain_categories and row.plain_categories[key] is not None
    ]
    average_z = _mean(scores)
    for pct_key, attempt_key in _PERCENTAGES:
        if key == pct_key:
            attempts = _mean([float(getattr(row, attempt_key)) for row in rows])
            return CategoryAverage(
                None,
                _weighted_percentage(rows, pct_key, attempt_key),
                attempts,
                average_z,
            )
    rates = [float(row.counting[key]) for row in rows if key in row.counting]
    return CategoryAverage(_mean(rates), None, None, average_z)


def _weighted_percentage(
    rows: list[PriceRow],
    pct_key: str,
    attempt_key: str,
) -> float | None:
    weighted: list[tuple[float, float]] = []
    for row in rows:
        pct = getattr(row, pct_key)
        if pct is None:
            continue
        attempts = row.games * float(getattr(row, attempt_key))
        if attempts > 0:
            weighted.append((float(pct), attempts))
    if not weighted:
        return None
    return sum(pct * attempts for pct, attempts in weighted) / sum(
        attempts for _pct, attempts in weighted
    )


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


_HANDFUL = 5
_DEEP_GREEN = 2
_GREEN = 1


@dataclass(frozen=True)
class Suggestion:
    """One nomination or target. Categories are empty when none can be named."""

    player_id: int
    name: str
    room_price: int
    balance_price: int
    pay_price: int
    categories: tuple[str, ...]
    positions: str = ""


def draft_suggestions(
    available: tuple[PriceRow, ...],
    user: SideSummary,
    league: SideSummary,
    categories: tuple[str, ...],
    punted: frozenset[str],
    bid: int | None,
) -> tuple[tuple[Suggestion, ...], tuple[Suggestion, ...]]:
    """Up to five nominations, then up to five targets.

    A nomination is ordered by how far the room's plain price sits above the
    curved price. The same gap uses how far the plain rank sits above that
    curved rank. With a punt, the curved price and rank are the personal ones.
    When the user is deep green in a category, players who are green there come
    first. A target never repeats a nomination. The same curved price uses that
    curved rank.
    """
    nominations = _nominations(available, user, categories, punted)
    nominated = {item.player_id for item in nominations}
    targets = _targets(available, user, league, categories, punted, bid, nominated)
    return nominations, targets


def _nominations(
    available: tuple[PriceRow, ...],
    user: SideSummary,
    categories: tuple[str, ...],
    punted: frozenset[str],
) -> tuple[Suggestion, ...]:
    deep = _deep_categories(user, categories)
    ranked: list[tuple[bool, int, int, str, Suggestion]] = []
    for row in available:
        balance = _balance_price(row, punted)
        if balance is None:
            continue
        gap = row.plain_price - balance
        if gap <= 0:
            continue
        shared = _shared_categories(row, deep)
        pay = _pay_price(row, punted)
        ranked.append(
            (
                not shared,
                -gap,
                -_rank_gap(row, punted),
                row.name.casefold(),
                Suggestion(
                    row.player_id,
                    row.name,
                    row.plain_price,
                    balance,
                    row.plain_price if pay is None else pay,
                    shared,
                    row.positions,
                ),
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4].name))
    return tuple(item[4] for item in ranked[:_HANDFUL])


def _targets(
    available: tuple[PriceRow, ...],
    user: SideSummary,
    league: SideSummary,
    categories: tuple[str, ...],
    punted: frozenset[str],
    bid: int | None,
    nominated: set[int],
) -> tuple[Suggestion, ...]:
    if bid is None:
        return ()
    need = _need_category(user, league, categories, punted)
    ranked: list[tuple[int, int, str, Suggestion]] = []
    for row in available:
        if row.player_id in nominated:
            continue
        balance = _balance_price(row, punted)
        pay = _pay_price(row, punted)
        if balance is None or pay is None or pay < 1 or pay > bid:
            continue
        if need is not None:
            score = row.plain_categories.get(need)
            if score is None or score < _GREEN:
                continue
        ranked.append(
            (
                -balance,
                _curved_rank(row, punted),
                row.name.casefold(),
                Suggestion(
                    row.player_id,
                    row.name,
                    row.plain_price,
                    balance,
                    pay,
                    (need,) if need is not None else (),
                    row.positions,
                ),
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3].name))
    return tuple(item[3] for item in ranked[:_HANDFUL])


def _deep_categories(user: SideSummary, categories: tuple[str, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for key in categories:
        average = user.categories.get(key)
        if average is not None and average.average_z is not None and average.average_z >= _DEEP_GREEN:
            found.append(key)
    return tuple(found)


def _shared_categories(row: PriceRow, deep: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        key
        for key in deep
        if row.plain_categories.get(key) is not None and row.plain_categories[key] >= _GREEN
    )


def _need_category(
    user: SideSummary,
    league: SideSummary,
    categories: tuple[str, ...],
    punted: frozenset[str],
) -> str | None:
    """The kept category where the user is furthest behind, or the smallest lead."""
    ranked: list[tuple[float, int, str]] = []
    for index, key in enumerate(categories):
        if key in punted:
            continue
        user_average = user.categories.get(key)
        league_average = league.categories.get(key)
        if (
            user_average is None
            or league_average is None
            or user_average.average_z is None
            or league_average.average_z is None
        ):
            continue
        ranked.append((league_average.average_z - user_average.average_z, -index, key))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][2]


def _rank_gap(row: PriceRow, punted: frozenset[str]) -> int:
    """How far TZ Rank sits above the curved rank. A lower rank number is better."""
    return _curved_rank(row, punted) - row.plain_rank


def _curved_rank(row: PriceRow, punted: frozenset[str]) -> int:
    if punted and row.personal_curved_rank is not None:
        return row.personal_curved_rank
    return row.curved_rank


def _balance_price(row: PriceRow, punted: frozenset[str]) -> int | None:
    if punted:
        return row.personal_curved_price
    return row.curved_price


def _pay_price(row: PriceRow, punted: frozenset[str]) -> int | None:
    if punted:
        return row.personal_plain_price
    return row.plain_price


def max_bid(budget: int, roster_size: int, sales: tuple[Sale, ...]) -> int | None:
    """The most this user can bid and still fill every later spot at $1.

    None means the user has no spot left. The number does not depend on which
    player is up.
    """
    spots_left = roster_size - sum(1 for sale in sales if sale.side == MINE)
    if spots_left <= 0:
        return None
    money_left = budget - sum(sale.price for sale in sales if sale.side == MINE)
    if spots_left == 1:
        return money_left
    return money_left - (spots_left - 1)


def avoid_bid(budget: int, roster_size: int, sales: tuple[Sale, ...]) -> int | None:
    """A bid to stay under so the spots after this one keep a rising reserve.

    Those spots keep $2 for each of the last four, then $4, $8, $16, and so on
    for each earlier pair. The result stays between $1 and the max bid. None
    means the user has no spot left. The number does not depend on which
    player is up.
    """
    ceiling = max_bid(budget, roster_size, sales)
    if ceiling is None:
        return None
    spots_left = roster_size - sum(1 for sale in sales if sale.side == MINE)
    money_left = budget - sum(sale.price for sale in sales if sale.side == MINE)
    bid = money_left - _later_reserve(spots_left - 1)
    if bid < 1:
        bid = 1
    if bid > ceiling:
        bid = ceiling
    return bid


def _later_reserve(spots: int) -> int:
    """Dollars to leave for the spots after the current bid.

    Counting from the last spot backward, the last four are $2 each. Each
    earlier pair doubles: $4, then $8, then $16.
    """
    return sum(_reserve_dollar(place) for place in range(1, spots + 1))


def _reserve_dollar(place_from_end: int) -> int:
    if place_from_end <= 4:
        return 2
    pair = (place_from_end - 5) // 2
    return 4 * (2**pair)


def sale_errors(
    sales: tuple[Sale, ...],
    player_id: int,
    side: str,
    price: int,
    sale_type: str,
    team_count: int,
    budget: int,
    roster_size: int,
    *,
    replacing: bool = False,
) -> tuple[str, ...]:
    """Why this sale cannot be saved. An empty tuple means it can."""
    errors: list[str] = []
    if side not in _SIDES:
        errors.append("Choose your team or another team.")
    if sale_type not in _SALE_TYPES:
        errors.append("Choose keeper or draft.")
    if type(price) is not int:
        errors.append("Enter a whole-dollar price.")
        return tuple(errors)
    if price < 1:
        errors.append("Enter a price of at least $1.")
    already = any(sale.player_id == player_id for sale in sales)
    if already and not replacing:
        errors.append("That player is already sold.")
    if errors:
        return tuple(errors)

    baseline = tuple(sale for sale in sales if sale.player_id != player_id)
    league_spots = team_count * roster_size
    if len(baseline) >= league_spots:
        return ("Every roster spot in the league is already filled.",)
    if side == MINE and sum(1 for sale in baseline if sale.side == MINE) >= roster_size:
        return ("Your roster is already full.",)
    if side == MINE:
        bid = max_bid(budget, roster_size, baseline)
        if bid is None or price > bid:
            return (f"That price is above your max bid of ${0 if bid is None else bid}.",)
    elif price > budget:
        return (f"That price is above this league's budget of ${budget}.",)
    money_left = team_count * budget - sum(sale.price for sale in baseline) - price
    spots_left = league_spots - len(baseline) - 1
    if money_left < spots_left:
        return ("That sale leaves the league short of $1 for every open spot.",)
    return ()


def reprice_remaining(
    rows: tuple[PriceRow, ...],
    sales: tuple[Sale, ...],
    team_count: int,
    budget: int,
    roster_size: int,
    punted: frozenset[str] = frozenset(),
) -> PriceTable:
    """Price the players still available from the spots and money still left.

    Category z-scores stay as they are. Sold players are left off the list.
    """
    sold = {sale.player_id for sale in sales}
    if len(sold) != len(sales):
        return PriceTable(rows=(), error="A player is on the sale list twice.")
    spots = team_count * roster_size - len(sales)
    money = team_count * budget - sum(sale.price for sale in sales)
    if spots < 0 or money < 0:
        return PriceTable(rows=(), error="The sale list does not fit this league.")
    if spots == 0:
        return PriceTable(rows=(), error=None)
    if money < spots:
        return PriceTable(
            rows=(),
            error=(
                "The league's remaining budget is smaller than the open spots, "
                "so a $1 bid cannot fill every spot."
            ),
        )
    available = tuple(row for row in rows if row.player_id not in sold)
    plain_prices = _auction_prices(
        available, [row.plain_score for row in available], spots, money, team_count
    )
    curved_prices = _auction_prices(
        available, [row.curved_score for row in available], spots, money, team_count
    )
    personal_plain: dict[int, int] = {}
    personal_curved: dict[int, int] = {}
    personal_plain_rank: list[int] = []
    personal_curved_rank: list[int] = []
    if punted:
        plain_totals = [_kept_total(row.plain_categories, punted) for row in available]
        curved_totals = [_kept_total(row.curved_categories, punted) for row in available]
        plain_order = _order_named(available, plain_totals)
        curved_order = _order_named(available, curved_totals)
        personal_plain = _prices_named(
            available, plain_order, plain_totals, spots, money, team_count
        )
        personal_curved = _prices_named(
            available, curved_order, curved_totals, spots, money, team_count
        )
        personal_plain_rank = _ranks(plain_order)
        personal_curved_rank = _ranks(curved_order)
    updated = []
    for index, row in enumerate(available):
        if punted:
            updated.append(
                replace(
                    row,
                    plain_price=plain_prices[row.player_id],
                    curved_price=curved_prices[row.player_id],
                    personal_plain_rank=personal_plain_rank[index],
                    personal_plain_price=personal_plain[row.player_id],
                    personal_curved_rank=personal_curved_rank[index],
                    personal_curved_price=personal_curved[row.player_id],
                )
            )
        else:
            updated.append(
                replace(
                    row,
                    plain_price=plain_prices[row.player_id],
                    curved_price=curved_prices[row.player_id],
                    personal_plain_rank=None,
                    personal_plain_price=None,
                    personal_curved_rank=None,
                    personal_curved_price=None,
                )
            )
    if punted:
        updated.sort(key=lambda item: item.personal_plain_rank or 0)
    else:
        updated.sort(key=lambda item: item.plain_rank)
    return PriceTable(rows=tuple(updated), error=None)


def _auction_prices(
    rows: tuple[PriceRow, ...],
    totals: list[float],
    spots: int,
    money: int,
    team_count: int,
) -> dict[int, int]:
    order = _order_named(rows, totals)
    return _prices_named(rows, order, totals, spots, money, team_count)


def assign_prices(
    scores_in_rank_order: list[float],
    total_budget: int,
    paid_count: int | None = None,
) -> list[int]:
    """Price one roster group. Scores are best first. The result sums to `total_budget`.

    Everyone in the group starts at $1. Extra money goes to the first `paid_count`
    players, measured from the score of the player just behind them. When that
    count covers the whole group, the last player is the baseline and stays at $1.
    """
    count = len(scores_in_rank_order)
    if count == 0:
        return []
    paid = count if paid_count is None else min(paid_count, count)
    prices = [1] * count
    money_left = total_budget - count
    if money_left <= 0 or paid == 0:
        return prices
    baseline = scores_in_rank_order[paid] if paid < count else scores_in_rank_order[-1]
    gaps = [score - baseline for score in scores_in_rank_order[:paid]]
    gap_sum = sum(gaps)
    if gap_sum == 0:
        extras = [0] * paid
        leftover = money_left
    else:
        extras = [math.floor(gap * money_left / gap_sum) for gap in gaps]
        leftover = money_left - sum(extras)
    for index, extra in enumerate(extras):
        prices[index] += extra
    index = 0
    while leftover > 0:
        prices[index % paid] += 1
        leftover -= 1
        index += 1
    return prices


def _prices_for(
    lines: list[ProjectionLine],
    order: list[int],
    totals: list[float],
    pool_size: int,
    total_budget: int,
    team_count: int,
) -> dict[int, int]:
    chosen = order[:pool_size]
    # The group keeps the scores that set the rank. It is not scored again.
    scores = [totals[index] for index in chosen]
    priced = assign_prices(scores, total_budget, paid_count=_PAID_PER_TEAM * team_count)
    prices = {line.player_id: 0 for line in lines}
    for index, price in zip(chosen, priced):
        prices[lines[index].player_id] = price
    return prices


def _category_scores(
    lines: list[ProjectionLine],
    categories: frozenset[str],
    *,
    curved: bool,
) -> list[dict[str, float | None]]:
    by_key = {key: _one_category(lines, key) for key in categories}
    if curved:
        by_key = {
            key: [None if value is None else math.tanh(value / 3.5) for value in values]
            for key, values in by_key.items()
        }
    return [
        {key: by_key[key][index] for key in categories}
        for index in range(len(lines))
    ]


def _one_category(lines: list[ProjectionLine], key: str) -> list[float | None]:
    for pct_key, attempt_key in _PERCENTAGES:
        if key == pct_key:
            values = _percentage_impacts(lines, pct_key, attempt_key)
            return _z_scores(values)
    values = [line.counting[key] for line in lines]
    scored = _z_scores(values)
    if key == _TURNOVERS:
        return [None if value is None else -value for value in scored]
    return scored


def _percentage_impacts(
    lines: list[ProjectionLine],
    pct_key: str,
    attempt_key: str,
) -> list[float | None]:
    rows: list[tuple[float, float] | None] = []
    for line in lines:
        pct = getattr(line, pct_key)
        if pct is None:
            rows.append(None)
            continue
        attempts = line.games * getattr(line, attempt_key)
        rows.append((float(pct), float(attempts)))
    weighted = [row for row in rows if row is not None and row[1] > 0]
    if not weighted:
        return [None if row is None else 0.0 for row in rows]
    league_pct = sum(pct * attempts for pct, attempts in weighted) / sum(
        attempts for _pct, attempts in weighted
    )
    impacts: list[float | None] = []
    for row in rows:
        if row is None:
            impacts.append(None)
        else:
            pct, attempts = row
            impacts.append((pct - league_pct) * attempts)
    return impacts


def _z_scores(values: list[float | None]) -> list[float | None]:
    present = [value for value in values if value is not None]
    if not present:
        return list(values)
    mean = sum(present) / len(present)
    variance = sum((value - mean) ** 2 for value in present) / len(present)
    spread = math.sqrt(variance)
    scored: list[float | None] = []
    for value in values:
        if value is None:
            scored.append(None)
        elif spread == 0:
            scored.append(0.0)
        else:
            scored.append((value - mean) / spread)
    return scored


def _total(parts: dict[str, float | None]) -> float:
    return sum(value for value in parts.values() if value is not None)


def _kept_total(parts: dict[str, float | None], punted: frozenset[str]) -> float:
    return sum(value for key, value in parts.items() if key not in punted and value is not None)


def _order_named(rows: tuple[PriceRow, ...], totals: list[float]) -> list[int]:
    indexes = list(range(len(rows)))
    indexes.sort(key=lambda index: (-totals[index], rows[index].name.casefold(), rows[index].name))
    return indexes


def _prices_named(
    rows: tuple[PriceRow, ...],
    order: list[int],
    totals: list[float],
    pool_size: int,
    total_budget: int,
    team_count: int,
) -> dict[int, int]:
    chosen = order[:pool_size]
    scores = [totals[index] for index in chosen]
    priced = assign_prices(scores, total_budget, paid_count=_PAID_PER_TEAM * team_count)
    prices = {row.player_id: 0 for row in rows}
    for index, price in zip(chosen, priced):
        prices[rows[index].player_id] = price
    return prices


def _order(lines: list[ProjectionLine], totals: list[float]) -> list[int]:
    indexes = list(range(len(lines)))
    indexes.sort(key=lambda index: (-totals[index], lines[index].name.casefold(), lines[index].name))
    return indexes


def _ranks(order: list[int]) -> list[int]:
    ranks = [0] * len(order)
    for place, index in enumerate(order, start=1):
        ranks[index] = place
    return ranks


def _row(
    line: ProjectionLine,
    plain_rank: int,
    plain_score: float,
    plain_price: int,
    curved_rank: int,
    curved_score: float,
    curved_price: int,
    plain_categories: dict[str, float | None],
    curved_categories: dict[str, float | None],
) -> PriceRow:
    return PriceRow(
        player_id=line.player_id,
        name=line.name,
        plain_rank=plain_rank,
        plain_score=plain_score,
        plain_price=plain_price,
        curved_rank=curved_rank,
        curved_score=curved_score,
        curved_price=curved_price,
        games=line.games,
        minutes_per_game=line.minutes_per_game,
        fga_per_game=line.fga_per_game,
        fta_per_game=line.fta_per_game,
        fg_pct=line.fg_pct,
        ft_pct=line.ft_pct,
        counting=line.counting,
        plain_categories=plain_categories,
        curved_categories=curved_categories,
        positions=line.positions,
    )
