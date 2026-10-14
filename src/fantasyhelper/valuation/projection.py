"""One projection line per player, from the imported files."""

import math
from dataclasses import dataclass

DRAFT_SEASON = "2026-27"
LAST_SEASON = "2025-26"
PRIOR_SEASON = "2024-25"
GAMES_LONG = 40
MINUTES_GAP = 4.8

COUNTING = (
    ("pts", "points", "points_per_game"),
    ("reb", "rebounds", "rebounds_per_game"),
    ("ast", "assists", "assists_per_game"),
    ("stl", "steals", "steals_per_game"),
    ("blk", "blocks", "blocks_per_game"),
    ("threes", "threes", "threes_per_game"),
    ("to", "turnovers", "turnovers_per_game"),
)


@dataclass(frozen=True)
class SeasonTotals:
    games: float
    minutes: float
    fga: float
    fta: float
    fg_pct: float | None
    ft_pct: float | None
    counting: dict[str, float]


@dataclass(frozen=True)
class FileProjection:
    games: float
    minutes_per_game: float
    fga_per_game: float
    fta_per_game: float
    fg_pct: float | None
    ft_pct: float | None
    counting: dict[str, float]
    positions: str = ""


@dataclass(frozen=True)
class PlayerSources:
    player_id: int
    name: str
    last_season: SeasonTotals | None
    prior_season: SeasonTotals | None
    projections: tuple[FileProjection, ...]


@dataclass(frozen=True)
class ProjectionLine:
    player_id: int
    name: str
    games: float
    minutes_per_game: float
    fga_per_game: float
    fta_per_game: float
    fg_pct: float | None
    ft_pct: float | None
    counting: dict[str, float]
    positions: str = ""


def lines_from_rows(
    players: list[dict[str, object]],
    seasons: list[dict[str, object]],
    projections: list[dict[str, object]],
) -> list[ProjectionLine]:
    seasons_by: dict[int, dict[str, SeasonTotals]] = {}
    for row in seasons:
        player_id = int(row["player_id"])
        seasons_by.setdefault(player_id, {})[str(row["season"])] = _season_from_row(row)
    files_by: dict[int, list[FileProjection]] = {}
    for row in projections:
        player_id = int(row["player_id"])
        files_by.setdefault(player_id, []).append(_file_from_row(row))
    sources = []
    for player in players:
        player_id = int(player["id"])
        by_season = seasons_by.get(player_id, {})
        sources.append(
            PlayerSources(
                player_id=player_id,
                name=str(player["name"]),
                last_season=by_season.get(LAST_SEASON),
                prior_season=by_season.get(PRIOR_SEASON),
                projections=tuple(files_by.get(player_id, ())),
            )
        )
    return build_lines(sources)


def build_lines(players: list[PlayerSources]) -> list[ProjectionLine]:
    lines = []
    for player in players:
        line = project_player(player)
        if line is not None:
            lines.append(line)
    return lines


def project_player(player: PlayerSources) -> ProjectionLine | None:
    files = player.projections
    if not files:
        return None
    last = player.last_season if _played(player.last_season) else None
    games = _mean([item.games for item in files])
    minutes = _mean([item.minutes_per_game for item in files])
    fga = _mean([item.fga_per_game for item in files])
    fta = _mean([item.fta_per_game for item in files])
    return ProjectionLine(
        player_id=player.player_id,
        name=player.name,
        games=games,
        minutes_per_game=minutes,
        fga_per_game=fga,
        fta_per_game=fta,
        fg_pct=_percentage("fg_pct", last, player.prior_season, files),
        ft_pct=_percentage("ft_pct", last, player.prior_season, files),
        counting=_counting_rates(last, files, minutes),
        positions=merged_positions(tuple(item.positions for item in files)),
    )


def _counting_rates(
    last: SeasonTotals | None,
    files: tuple[FileProjection, ...],
    projected_minutes: float,
) -> dict[str, float]:
    close_to_last = (
        last is not None
        and last.games > GAMES_LONG
        and _minutes_are_close(projected_minutes, last.minutes / last.games)
    )
    rates = {}
    for key, _total, _rate in COUNTING:
        if close_to_last:
            assert last is not None
            rates[key] = last.counting[key] / last.games
        else:
            rates[key] = _mean([item.counting[key] for item in files])
    return rates


def _percentage(
    field: str,
    last: SeasonTotals | None,
    prior: SeasonTotals | None,
    files: tuple[FileProjection, ...],
) -> float | None:
    for season in (last, prior):
        if season is not None and season.games > GAMES_LONG:
            stored = getattr(season, field)
            if stored is not None:
                return float(stored)
    values = [getattr(item, field) for item in files]
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return _mean(present)


def _minutes_are_close(projected_minutes: float, last_minutes_per_game: float) -> bool:
    gap = abs(projected_minutes - last_minutes_per_game)
    # 34.8 − 30 is stored a hair under 4.8. That gap is 4.8, so it is not close.
    return gap < MINUTES_GAP and not math.isclose(gap, MINUTES_GAP)


_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def merged_positions(texts: tuple[str, ...]) -> str:
    """Positions listed on at least one projection, in PG/SG/SF/PF/C order."""
    found: set[str] = set()
    for text in texts:
        for part in text.split("/"):
            code = part.strip()
            if code:
                found.add(code)
    ordered = [code for code in _POSITIONS if code in found]
    rest = sorted(found.difference(_POSITIONS))
    return "/".join([*ordered, *rest])


def _played(season: SeasonTotals | None) -> bool:
    return season is not None and season.games > 0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _season_from_row(row: dict[str, object]) -> SeasonTotals:
    return SeasonTotals(
        games=float(row["games"]),
        minutes=float(row["minutes"]),
        fga=float(row["fga"]),
        fta=float(row["fta"]),
        fg_pct=_optional_float(row["fg_pct"]),
        ft_pct=_optional_float(row["ft_pct"]),
        counting={key: float(row[column]) for key, column, _rate in COUNTING},
    )


def _file_from_row(row: dict[str, object]) -> FileProjection:
    return FileProjection(
        games=float(row["games"]),
        minutes_per_game=float(row["minutes_per_game"]),
        fga_per_game=float(row["fga_per_game"]),
        fta_per_game=float(row["fta_per_game"]),
        fg_pct=_optional_float(row["fg_pct"]),
        ft_pct=_optional_float(row["ft_pct"]),
        counting={key: float(row[rate]) for key, _column, rate in COUNTING},
        positions=str(row["positions"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
