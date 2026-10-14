"""Price table for the open league."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasyhelper.valuation.prices import (
    DRAFT,
    KEEPER,
    CategoryAverage,
    PriceRow,
    Sale,
    SideSummary,
    Suggestion,
)

# Plain z bands. A value on the edge takes the higher band.
_DEEP_GREEN = "background-color: #8FCB9B"
_GREEN = "background-color: #C6E6CE"
_LIGHT_GREEN = "background-color: #E7F6EB"
_LIGHT_RED = "background-color: #FDECEC"
_RED = "background-color: #F6C9C4"
_DEEP_RED = "background-color: #E89B96"
_YELLOW = "background-color: #F8E7A0"
# Punted cells keep the band, washed halfway toward the page background, with gray text.
_FADED_TEXT = "color: #8A8A8A"
_FADED_BANDS = {
    _DEEP_GREEN: "background-color: #BCDAC2; color: #8A8A8A",
    _GREEN: "background-color: #D7E7DB; color: #8A8A8A",
    _LIGHT_GREEN: "background-color: #E8EFEA; color: #8A8A8A",
    _LIGHT_RED: "background-color: #F2EAEA; color: #8A8A8A",
    _RED: "background-color: #EFD8D6; color: #8A8A8A",
    _DEEP_RED: "background-color: #E8C2BF; color: #8A8A8A",
}

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
_POS_WIDTH = 80
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
_SALE_WIDTH = 80
_SUMMARY_LABEL_WIDTH = 120
_MONEY_LEFT_WIDTH = 110
_SPENT_WIDTH = 80
_SPOTS_LEFT_WIDTH = 100
_TAKEN_WIDTH = 80
_SUMMARY_LABEL = " "
_SUGGESTION_CATEGORY_WIDTH = 180
_SUMMARY_MONEY = {"Money left": _MONEY_LEFT_WIDTH, "Spent": _SPENT_WIDTH}
_SUMMARY_SPOTS = {"Spots left": _SPOTS_LEFT_WIDTH, "Taken": _TAKEN_WIDTH}
_RANK_HEADERS = frozenset({"TZ Rank", "TC Rank", "PZ Rank", "PC Rank"})
_PRICE_HEADERS = frozenset({"TZ Price", "TC Price", "PZ Price", "PC Price", "Price"})
_SALE_LABELS = {DRAFT: "Draft", KEEPER: "Keeper"}
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


def show_roster_table(
    sales: tuple[Sale, ...],
    rows_by_id: dict[int, PriceRow],
    names: dict[int, str],
    active: frozenset[str],
    punted: frozenset[str],
    *,
    selection_key: str,
    on_select,
) -> None:
    """Your players or other teams: the paid price, the sale, and the colored projection."""
    columns = roster_columns(active, punted)
    records = []
    colors = []
    for sale in sales:
        row = rows_by_id.get(sale.player_id)
        name = row.name if row is not None else names.get(sale.player_id, "Unknown player")
        positions = row.positions if row is not None else ""
        records.append(
            [name, positions, sale.price, _SALE_LABELS[sale.sale_type], *_projection_values(row, active)]
        )
        if row is None:
            colors.append([""] * len(columns))
        else:
            colors.append(_row_colors(row, active, punted, columns))
    frame = pd.DataFrame(records, columns=columns)
    st.dataframe(
        _apply_style(frame, colors),
        hide_index=True,
        width="content",
        column_config={name: _column_config(name) for name in columns},
        placeholder="",
        key=selection_key,
        on_select=on_select,
        selection_mode="single-row",
    )


def show_summary_table(
    league: SideSummary,
    yours: SideSummary,
    active: frozenset[str],
) -> None:
    """Two rows: the whole league, then the user's team. A punt is not shown."""
    columns = summary_columns(active)
    records = [
        _summary_record("League", league, active),
        _summary_record("Your team", yours, active),
    ]
    frame = pd.DataFrame(records, columns=columns)
    colors = [
        _summary_colors(league, active, columns),
        _summary_colors(yours, active, columns),
    ]
    st.dataframe(
        _apply_style(frame, colors),
        hide_index=True,
        width="content",
        column_config={name: _summary_column_config(name) for name in columns},
        placeholder="",
    )


def _summary_record(label: str, side: SideSummary, active: frozenset[str]) -> dict[str, object]:
    record: dict[str, object] = {
        _SUMMARY_LABEL: label,
        "Money left": side.money_left,
        "Spent": side.money_spent,
        "Spots left": side.spots_left,
        "Taken": side.spots_taken,
    }
    for key, name in _STAT_COLUMNS:
        if key not in active:
            continue
        record[name] = _summary_value(key, side.categories[key])
    return record


def _summary_value(key: str, average: CategoryAverage) -> object:
    if key in ("fg_pct", "ft_pct"):
        if average.attempts is None:
            return ""
        return shot_text(average.percentage, average.attempts)
    return average.rate


def _summary_colors(
    side: SideSummary,
    active: frozenset[str],
    columns: list[str],
) -> list[str]:
    colors = {column: "" for column in columns}
    for key, label in _STAT_COLUMNS:
        if key not in active:
            continue
        score = side.categories[key].average_z
        if score is not None:
            colors[label] = strength_color(score)
    return [colors[column] for column in columns]


def _summary_column_config(name: str) -> dict:
    if name == _SUMMARY_LABEL:
        return st.column_config.Column(alignment="left", width=_SUMMARY_LABEL_WIDTH)
    if name in _SUMMARY_MONEY:
        return st.column_config.NumberColumn(
            alignment="center",
            format="$%d",
            width=_SUMMARY_MONEY[name],
        )
    if name in _SUMMARY_SPOTS:
        return st.column_config.NumberColumn(
            alignment="center",
            format="%d",
            width=_SUMMARY_SPOTS[name],
        )
    return st.column_config.Column(alignment="center", width=_column_width(name))


def show_suggestion_table(
    suggestions: tuple[Suggestion, ...],
    punted: frozenset[str],
    *,
    selection_key: str,
    on_select,
) -> None:
    """A short nomination or target list. A blank category means none was named."""
    columns = _suggestion_columns(punted)
    records = [_suggestion_record(item, columns) for item in suggestions]
    frame = pd.DataFrame(records, columns=columns)
    st.dataframe(
        frame,
        hide_index=True,
        width="content",
        column_config={name: _suggestion_column_config(name) for name in columns},
        placeholder="",
        key=selection_key,
        on_select=on_select,
        selection_mode="single-row",
    )


def _suggestion_columns(punted: frozenset[str]) -> list[str]:
    balance = "PC Price" if punted else "TC Price"
    return ["Name", "Pos", "TZ Price", balance, "Category"]


def _suggestion_record(item: Suggestion, columns: list[str]) -> dict[str, object]:
    return {
        "Name": item.name,
        "Pos": item.positions,
        "TZ Price": item.room_price,
        columns[3]: item.balance_price,
        "Category": ", ".join(_SWITCH_LABELS[key] for key in item.categories),
    }


def _suggestion_column_config(name: str) -> dict:
    if name == "Name":
        return st.column_config.Column(alignment="left", width=_NAME_WIDTH)
    if name == "Pos":
        return st.column_config.Column(alignment="center", width=_POS_WIDTH)
    if name == "Category":
        return st.column_config.Column(alignment="center", width=_SUGGESTION_CATEGORY_WIDTH)
    return st.column_config.NumberColumn(
        alignment="center",
        format="$%d",
        width=_PRICE_WIDTH,
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
    if base == "Pos":
        return _POS_WIDTH
    if base in _RANK_HEADERS:
        return _RANK_WIDTH
    if base in _PRICE_HEADERS:
        return _PRICE_WIDTH
    if base == "Games":
        return _GAMES_WIDTH
    if base == "Minutes":
        return _MINUTES_WIDTH
    if base == "Sale":
        return _SALE_WIDTH
    if base in ("FG% / FGA", "FT% / FTA"):
        return _SHOT_WIDTH
    return _CATEGORY_WIDTHS[base]


def table_columns(active: frozenset[str], punted: frozenset[str] = frozenset()) -> list[str]:
    lead = ["Name", "Pos", *_IDENTITY[1:], *_PERSONAL, *_USAGE]
    stats = [
        column_label(label, key in punted) for key, label in _STAT_COLUMNS if key in active
    ]
    return [*lead, *stats]


def roster_columns(active: frozenset[str], punted: frozenset[str] = frozenset()) -> list[str]:
    """Taken lists keep the paid price and the sale, then the same projection columns."""
    stats = [
        column_label(label, key in punted) for key, label in _STAT_COLUMNS if key in active
    ]
    return ["Name", "Pos", "Price", "Sale", *_USAGE, *stats]


def summary_columns(active: frozenset[str]) -> list[str]:
    """Money and spots, then each active category. A punt is not marked here."""
    stats = [label for key, label in _STAT_COLUMNS if key in active]
    return [_SUMMARY_LABEL, *_SUMMARY_MONEY, *_SUMMARY_SPOTS, *stats]


def category_keys(active: frozenset[str]) -> tuple[str, ...]:
    """Active categories in price-table order."""
    return tuple(key for key, _label in _STAT_COLUMNS if key in active)


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
        row.positions,
        row.plain_rank,
        row.plain_price,
        row.curved_rank,
        row.curved_price,
        _empty(row.personal_plain_rank),
        _empty(row.personal_plain_price),
        _empty(row.personal_curved_rank),
        _empty(row.personal_curved_price),
        *_projection_values(row, active),
    ]
    return values


def _projection_values(row: PriceRow | None, active: frozenset[str]) -> list[object]:
    """Games, minutes, and each active category. A missing projection stays blank."""
    if row is None:
        return [""] * (len(_USAGE) + sum(1 for key, _label in _STAT_COLUMNS if key in active))
    values: list[object] = [row.games, row.minutes_per_game]
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
    return _apply_style(frame, colors)


def _apply_style(
    frame: pd.DataFrame,
    colors: list[list[str]],
) -> pd.io.formats.style.Styler:
    columns = list(frame.columns)

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
        name = column_label(label, key in punted)
        z = row.plain_categories[key]
        if z is not None:
            colors[name] = strength_color(z)
        if key in punted:
            colors[name] = _FADED_BANDS.get(colors[name], _FADED_TEXT)
    return [colors[column] for column in columns]
