"""Ranks and prices from projection lines. Both results are calculated."""

import math
from dataclasses import dataclass

from fantasyhelper.valuation.projection import ProjectionLine

_TURNOVERS = "to"
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


@dataclass(frozen=True)
class PriceTable:
    rows: tuple[PriceRow, ...]
    error: str | None


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
        lines, plain_order, categories, pool_size, total_budget, curved=False
    )
    curved_prices = _prices_for(
        lines, curved_order, categories, pool_size, total_budget, curved=True
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


def assign_prices(scores_in_rank_order: list[float], total_budget: int) -> list[int]:
    """Price one group. Scores are best first. The result sums to `total_budget`."""
    count = len(scores_in_rank_order)
    if count == 0:
        return []
    money_left = total_budget - count
    lowest = min(scores_in_rank_order)
    gaps = [score - lowest for score in scores_in_rank_order]
    gap_sum = sum(gaps)
    if money_left <= 0 or gap_sum == 0:
        extras = [0] * count
        leftover = max(money_left, 0)
    else:
        extras = [math.floor(gap * money_left / gap_sum) for gap in gaps]
        leftover = money_left - sum(extras)
    prices = [1 + extra for extra in extras]
    index = 0
    while leftover > 0:
        prices[index % count] += 1
        leftover -= 1
        index += 1
    return prices


def _prices_for(
    lines: list[ProjectionLine],
    order: list[int],
    categories: frozenset[str],
    pool_size: int,
    total_budget: int,
    *,
    curved: bool,
) -> dict[int, int]:
    chosen = order[:pool_size]
    group = [lines[index] for index in chosen]
    parts = _category_scores(group, categories, curved=curved)
    scores = [_total(item) for item in parts]
    # $1 is reserved for each player in the group. The rest of the league budget
    # is the gap money. A full group leaves teams × budget − teams × roster spots.
    priced = assign_prices(scores, total_budget)
    prices = {line.player_id: 0 for line in lines}
    for line, price in zip(group, priced):
        prices[line.player_id] = price
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
            key: [None if value is None else math.tanh(value / 2) for value in values]
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
    )
