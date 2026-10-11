"""Price table for the open league."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasyhelper.leagues.league import League
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.valuation.prices import PriceRow, build_price_table
from fantasyhelper.valuation.projection import lines_from_rows

# Plain z bands. A value on the edge takes the higher band.
_DEEP_GREEN = "background-color: #8FCB9B"
_GREEN = "background-color: #C6E6CE"
_LIGHT_GREEN = "background-color: #E7F6EB"
_LIGHT_RED = "background-color: #FDECEC"
_RED = "background-color: #F6C9C4"
_DEEP_RED = "background-color: #E89B96"
_YELLOW = "background-color: #F8E7A0"

# Display order. A category the league turned off is omitted.
_STAT_COLUMNS = (
    ("fg_pct", "FG% / FGA"),
    ("ft_pct", "FT% / FTA"),
    ("threes", "Threes"),
    ("pts", "Points"),
    ("reb", "Rebounds"),
    ("ast", "Assists"),
    ("stl", "Steals"),
    ("blk", "Blocks"),
    ("to", "Turnovers"),
)
_LEAD = ("Name", "Z Rank", "Z Price", "C Rank", "C Price", "Games", "Minutes")
_TOTALS = ("Z Score", "C Score")
_GAMES_MARK = 60
_MINUTES_MARK = 25


def render_prices(league: League) -> None:
    st.subheader("Prices")
    settings = league.settings
    players, seasons, projections = load_baseline_rows()
    table = build_price_table(
        lines_from_rows(players, seasons, projections),
        settings.categories,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    if table.error:
        st.error(table.error)
        return
    if not table.rows:
        st.write("No players are in the projection yet.")
        return
    st.caption(
        "Ranks and scores use every projected player. "
        "Extra money above $1 goes to the top 10 players per team. "
        "The rest of that rank's roster group stays at $1, and a player outside it costs $0. "
        "Green is above the average and red is below it. "
        "Games under 60 and minutes under 25 are yellow."
    )
    frame = _frame(table.rows, settings.categories)
    st.dataframe(_styled(frame, table.rows, settings.categories), hide_index=True)


def strength_color(z: float) -> str:
    """CSS background for one plain category z."""
    if z >= 2:
        return _DEEP_GREEN
    if z >= 1:
        return _GREEN
    if z >= 0:
        return _LIGHT_GREEN
    if z >= -0.75:
        return _LIGHT_RED
    if z >= -1.5:
        return _RED
    return _DEEP_RED


def shot_text(pct: float | None, attempts: float) -> str:
    """One cell for a percentage and its attempts. A blank percentage stays blank."""
    attempts_text = f"{attempts:.1f}"
    if pct is None:
        return f"— / {attempts_text}"
    return f"{pct * 100:.1f}% / {attempts_text}"


def table_columns(active: frozenset[str]) -> list[str]:
    stats = [label for key, label in _STAT_COLUMNS if key in active]
    return [*_LEAD, *stats, *_TOTALS]


def _frame(rows: tuple[PriceRow, ...], active: frozenset[str]) -> pd.DataFrame:
    return pd.DataFrame([_values(row, active) for row in rows], columns=table_columns(active))


def _values(row: PriceRow, active: frozenset[str]) -> list[object]:
    values: list[object] = [
        row.name,
        row.plain_rank,
        row.plain_price,
        row.curved_rank,
        row.curved_price,
        row.games,
        row.minutes_per_game,
    ]
    for key, _label in _STAT_COLUMNS:
        if key not in active:
            continue
        if key == "fg_pct":
            values.append(shot_text(row.fg_pct, row.fga_per_game))
        elif key == "ft_pct":
            values.append(shot_text(row.ft_pct, row.fta_per_game))
        else:
            values.append(row.counting[key])
    values.extend((row.plain_score, row.curved_score))
    return values


def _styled(
    frame: pd.DataFrame,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
) -> pd.io.formats.style.Styler:
    colors = [_row_colors(row, active, list(frame.columns)) for row in rows]

    def paint(_frame: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(colors, index=_frame.index, columns=_frame.columns)

    number_formats = {
        "Games": "{:.1f}",
        "Minutes": "{:.1f}",
        "Threes": "{:.1f}",
        "Points": "{:.1f}",
        "Rebounds": "{:.1f}",
        "Assists": "{:.1f}",
        "Steals": "{:.2f}",
        "Blocks": "{:.2f}",
        "Turnovers": "{:.1f}",
        "Z Score": "{:.2f}",
        "C Score": "{:.2f}",
    }
    present = {key: fmt for key, fmt in number_formats.items() if key in frame.columns}
    return frame.style.apply(paint, axis=None).format(present, na_rep="")


def _row_colors(row: PriceRow, active: frozenset[str], columns: list[str]) -> list[str]:
    colors = {column: "" for column in columns}
    if row.games < _GAMES_MARK:
        colors["Games"] = _YELLOW
    if row.minutes_per_game < _MINUTES_MARK:
        colors["Minutes"] = _YELLOW
    for key, label in _STAT_COLUMNS:
        if key not in active:
            continue
        z = row.plain_categories[key]
        if z is not None:
            colors[label] = strength_color(z)
    return [colors[column] for column in columns]
