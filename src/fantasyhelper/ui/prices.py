"""Price table for the open league."""

import streamlit as st

from fantasyhelper.leagues.league import CATEGORIES, League
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.valuation.prices import PriceRow, build_price_table
from fantasyhelper.valuation.projection import lines_from_rows

_COUNTING_LABELS = {
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "stl": "Steals",
    "blk": "Blocks",
    "threes": "Threes",
    "to": "Turnovers",
}


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
    active = [item for item in CATEGORIES if item[0] in settings.categories]
    st.caption(
        "Ranks and scores use every projected player. "
        "Extra money above $1 goes to the top 10 players per team. "
        "The rest of that rank's roster group stays at $1, and a player outside it costs $0."
    )
    st.dataframe(
        [_present(row, active) for row in table.rows],
        hide_index=True,
        column_config=_column_config(active),
    )


def _present(row: PriceRow, active: list[tuple[str, str]]) -> dict[str, object]:
    presented: dict[str, object] = {
        "Name": row.name,
        "Plain rank": row.plain_rank,
        "Plain score": row.plain_score,
        "Plain price": row.plain_price,
        "Curved rank": row.curved_rank,
        "Curved score": row.curved_score,
        "Curved price": row.curved_price,
        "Games": row.games,
        "Minutes": row.minutes_per_game,
        "FGA": row.fga_per_game,
        "FTA": row.fta_per_game,
        "FG%": row.fg_pct,
        "FT%": row.ft_pct,
    }
    for key, label in _COUNTING_LABELS.items():
        presented[label] = row.counting[key]
    for key, label in active:
        presented[f"{label}, plain"] = row.plain_categories[key]
    for key, label in active:
        presented[f"{label}, curved"] = row.curved_categories[key]
    return presented


def _column_config(active: list[tuple[str, str]]) -> dict[str, st.column_config.NumberColumn]:
    score = st.column_config.NumberColumn(format="%.2f")
    rate = st.column_config.NumberColumn(format="%.2f")
    config: dict[str, st.column_config.NumberColumn] = {
        "Plain score": score,
        "Curved score": score,
        "Games": st.column_config.NumberColumn(format="%.1f"),
        "Minutes": rate,
        "FGA": rate,
        "FTA": rate,
        "FG%": st.column_config.NumberColumn(format="%.3f"),
        "FT%": st.column_config.NumberColumn(format="%.3f"),
    }
    for label in _COUNTING_LABELS.values():
        config[label] = rate
    for _key, label in active:
        config[f"{label}, plain"] = score
        config[f"{label}, curved"] = score
    return config
