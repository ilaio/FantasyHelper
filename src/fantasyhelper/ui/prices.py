"""Price table for the open league."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasyhelper.valuation.prices import PriceRow

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
    ("threes", "3pt"),
    ("pts", "Pts"),
    ("reb", "Reb"),
    ("ast", "Ast"),
    ("stl", "Stl"),
    ("blk", "Blk"),
    ("to", "Tov"),
)
_IDENTITY = ("Name", "TZ Rank", "TZ Price", "TC Rank", "TC Price")
_PERSONAL = ("PZ Rank", "PZ Price", "PC Rank", "PC Price")
_USAGE = ("Games", "Minutes")
_PUNT_MARK = " (p)"
_NAME_WIDTH = 170
_RANK_WIDTH = 65
_PRICE_WIDTH = 65
_GAMES_WIDTH = 60
_MINUTES_WIDTH = 60
_SHOT_WIDTH = 100
_THREES_WIDTH = 100
_POINTS_WIDTH = 100
_REBOUNDS_WIDTH = 100
_ASSISTS_WIDTH = 100
_STEALS_WIDTH = 100
_BLOCKS_WIDTH = 100
_TURNOVERS_WIDTH = 100
_RANK_HEADERS = frozenset({"TZ Rank", "TC Rank", "PZ Rank", "PC Rank"})
_PRICE_HEADERS = frozenset({"TZ Price", "TC Price", "PZ Price", "PC Price"})
_CATEGORY_WIDTHS = {
    "3pt": _THREES_WIDTH,
    "Pts": _POINTS_WIDTH,
    "Reb": _REBOUNDS_WIDTH,
    "Ast": _ASSISTS_WIDTH,
    "Stl": _STEALS_WIDTH,
    "Blk": _BLOCKS_WIDTH,
    "Tov": _TURNOVERS_WIDTH,
}
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


def show_price_table(
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
    *,
    selection_key: str | None = None,
    on_select=None,
    height: int | str = "auto",
) -> None:
    """Draw the price table. No rows draws one blank row in the same columns."""
    columns = table_columns(active, punted)
    if rows:
        frame = _frame(rows, active, punted)
        data = _styled(frame, rows, active, punted)
    else:
        data = pd.DataFrame([{name: "" for name in columns}])
    kwargs = {}
    if selection_key is not None:
        kwargs["key"] = selection_key
        kwargs["on_select"] = on_select
        kwargs["selection_mode"] = "single-row"
    st.dataframe(
        data,
        hide_index=True,
        width="content",
        height=height,
        column_config={name: _column_config(name) for name in columns},
        placeholder="",
        **kwargs,
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
    if name in _PRICE_HEADERS:
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
    width = _column_width(name)
    number_format = price_format(name)
    if number_format is not None:
        return st.column_config.NumberColumn(
            alignment=column_alignment(name),
            format=number_format,
            width=width,
        )
    return st.column_config.Column(alignment=column_alignment(name), width=width)


def _column_width(name: str) -> int:
    """Each group has its own width so one column can change without the others."""
    base = name.removesuffix(_PUNT_MARK)
    if base == "Name":
        return _NAME_WIDTH
    if base in _RANK_HEADERS:
        return _RANK_WIDTH
    if base in _PRICE_HEADERS:
        return _PRICE_WIDTH
    if base == "Games":
        return _GAMES_WIDTH
    if base == "Minutes":
        return _MINUTES_WIDTH
    if base in ("FG% / FGA", "FT% / FTA"):
        return _SHOT_WIDTH
    return _CATEGORY_WIDTHS[base]


def table_columns(active: frozenset[str], punted: frozenset[str] = frozenset()) -> list[str]:
    lead = [*_IDENTITY, *_PERSONAL, *_USAGE]
    stats = [
        column_label(label, key in punted) for key, label in _STAT_COLUMNS if key in active
    ]
    return [*lead, *stats]


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


def current_punts(league_id: int, active: frozenset[str]) -> frozenset[str]:
    """Categories switched off. A missing switch counts as on."""
    keys = _active_switch_keys(active)
    if punt_limit(len(keys)) == 0:
        return frozenset()
    return frozenset(
        key for key in keys if st.session_state.get(_switch_key(league_id, key)) is False
    )


def punt_switches(league_id: int, active: frozenset[str]) -> frozenset[str]:
    """Draw the category switches and return the categories that are off."""
    options = [(key, _SWITCH_LABELS[key]) for key in _active_switch_keys(active)]
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
    return current_punts(league_id, active)


def _active_switch_keys(active: frozenset[str]) -> tuple[str, ...]:
    return tuple(key for key, _label in _STAT_COLUMNS if key in active)


def _frame(
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> pd.DataFrame:
    columns = table_columns(active, punted)
    return pd.DataFrame([_values(row, active) for row in rows], columns=columns)


def _values(row: PriceRow, active: frozenset[str]) -> list[object]:
    values: list[object] = [
        row.name,
        row.plain_rank,
        row.plain_price,
        row.curved_rank,
        row.curved_price,
        _empty(row.personal_plain_rank),
        _empty(row.personal_plain_price),
        _empty(row.personal_curved_rank),
        _empty(row.personal_curved_price),
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
    return values


def _empty(value: object) -> object:
    """A missing number stays blank. A real zero stays zero."""
    if value is None:
        return ""
    return value


_RATE_FORMATS = {
    "3pt": "{:.1f}",
    "Pts": "{:.1f}",
    "Reb": "{:.1f}",
    "Ast": "{:.1f}",
    "Stl": "{:.2f}",
    "Blk": "{:.2f}",
    "Tov": "{:.1f}",
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
