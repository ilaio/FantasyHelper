"""Price table for the open league."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasyhelper.leagues.league import League
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.valuation.prices import PriceRow, apply_punt, build_price_table
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
_IDENTITY = ("Name", "Z Rank", "Z Price", "C Rank", "C Price")
_PERSONAL = ("My Z Rank", "My Z Price", "My C Rank", "My C Price")
_USAGE = ("Games", "Minutes")
_TOTALS = ("Z Score", "C Score")
_PUNT_MARK = " (punt)"
_GAMES_MARK = 60
_MINUTES_MARK = 25
_PUNT_LIMIT = 2
_SWITCH_LABELS = {
    "fg_pct": "FG%",
    "ft_pct": "FT%",
    "threes": "Threes",
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "stl": "Steals",
    "blk": "Blocks",
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
    punted = _selected_punts(league.id, settings.categories)
    rows = apply_punt(
        table.rows,
        punted,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    frame = _frame(rows, settings.categories, punted)
    st.dataframe(
        _styled(frame, rows, settings.categories, punted),
        hide_index=True,
        width="content",
        column_config={name: _column_config(name) for name in frame.columns},
    )


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


def column_alignment(name: str) -> str:
    """Name stays on the left. Every other value is centered."""
    if name == "Name":
        return "left"
    return "center"


def price_format(name: str) -> str | None:
    """Price columns show a dollar sign. The value stays a whole number."""
    if name in ("Z Price", "C Price", "My Z Price", "My C Price"):
        return "$%d"
    return None


def punt_limit(active_count: int) -> int:
    """At most two categories, and at least one category stays on."""
    if active_count <= 1:
        return 0
    return min(_PUNT_LIMIT, active_count - 1)


def punt_refusal(off_count: int, active_count: int) -> str | None:
    """Why a switch must stay on. None means the choice is allowed."""
    if off_count > _PUNT_LIMIT:
        return "Only two categories can be off."
    if active_count > 0 and off_count >= active_count:
        return "Leave at least one category on."
    return None


def column_label(label: str, punted: bool) -> str:
    """A punted category keeps its column, and the header says so."""
    if punted:
        return f"{label}{_PUNT_MARK}"
    return label


def _column_config(name: str) -> dict:
    number_format = price_format(name)
    if number_format is not None:
        return st.column_config.NumberColumn(
            alignment=column_alignment(name),
            format=number_format,
        )
    return st.column_config.Column(alignment=column_alignment(name))


def table_columns(active: frozenset[str], punted: frozenset[str] = frozenset()) -> list[str]:
    lead = list(_IDENTITY)
    if punted:
        lead.extend(_PERSONAL)
    lead.extend(_USAGE)
    stats = [
        column_label(label, key in punted) for key, label in _STAT_COLUMNS if key in active
    ]
    return [*lead, *stats, *_TOTALS]


def _switch_key(league_id: int, category: str) -> str:
    return f"cat-on-{league_id}-{category}"


def _guard_category_switch(
    state_key: str,
    message_key: str,
    league_id: int,
    active_keys: tuple[str, ...],
) -> None:
    off_count = sum(
        1
        for key in active_keys
        if st.session_state.get(_switch_key(league_id, key)) is False
    )
    message = punt_refusal(off_count, len(active_keys))
    if message is None:
        st.session_state[message_key] = ""
        return
    st.session_state[state_key] = True
    st.session_state[message_key] = message


def _selected_punts(league_id: int, active: frozenset[str]) -> frozenset[str]:
    options = [(key, _SWITCH_LABELS[key]) for key, _label in _STAT_COLUMNS if key in active]
    if punt_limit(len(options)) == 0:
        return frozenset()
    active_keys = tuple(key for key, _label in options)
    message_key = f"punt-note-{league_id}"
    with st.container(horizontal=True, wrap=False, gap="medium"):
        for key, label in options:
            state_key = _switch_key(league_id, key)
            if state_key not in st.session_state:
                st.session_state[state_key] = True
            st.toggle(
                label,
                key=state_key,
                width="content",
                on_change=_guard_category_switch,
                args=(state_key, message_key, league_id, active_keys),
            )
    message = st.session_state.get(message_key, "")
    if message:
        st.caption(message)
    return frozenset(
        key for key in active_keys if st.session_state.get(_switch_key(league_id, key)) is False
    )


def _frame(
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> pd.DataFrame:
    columns = table_columns(active, punted)
    return pd.DataFrame([_values(row, active, punted) for row in rows], columns=columns)


def _values(row: PriceRow, active: frozenset[str], punted: frozenset[str]) -> list[object]:
    values: list[object] = [
        row.name,
        row.plain_rank,
        row.plain_price,
        row.curved_rank,
        row.curved_price,
    ]
    if punted:
        values.extend(
            (
                row.personal_plain_rank,
                row.personal_plain_price,
                row.personal_curved_rank,
                row.personal_curved_price,
            )
        )
    values.extend((row.games, row.minutes_per_game))
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


_RATE_FORMATS = {
    "Threes": "{:.1f}",
    "Points": "{:.1f}",
    "Rebounds": "{:.1f}",
    "Assists": "{:.1f}",
    "Steals": "{:.2f}",
    "Blocks": "{:.2f}",
    "Turnovers": "{:.1f}",
}


def _styled(
    frame: pd.DataFrame,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> pd.io.formats.style.Styler:
    columns = list(frame.columns)
    colors = [_row_colors(row, active, punted, columns) for row in rows]

    def paint(_frame: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(colors, index=_frame.index, columns=_frame.columns)

    number_formats = {
        "Games": "{:.1f}",
        "Minutes": "{:.1f}",
        "Z Score": "{:.2f}",
        "C Score": "{:.2f}",
    }
    for column in columns:
        base = column.removesuffix(_PUNT_MARK)
        if base in _RATE_FORMATS:
            number_formats[column] = _RATE_FORMATS[base]
    present = {key: fmt for key, fmt in number_formats.items() if key in frame.columns}
    return frame.style.apply(paint, axis=None).format(present, na_rep="")


def _row_colors(
    row: PriceRow,
    active: frozenset[str],
    punted: frozenset[str],
    columns: list[str],
) -> list[str]:
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
            colors[column_label(label, key in punted)] = strength_color(z)
    return [colors[column] for column in columns]
