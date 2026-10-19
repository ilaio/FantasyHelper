"""Draft tab: the summary, nominations and targets, the three lists, and one player view."""

import html
from collections.abc import Callable, Sequence

import streamlit as st

from fantasyhelper.leagues.league import League
from fantasyhelper.leagues.sales import list_sales, record_sale, update_sale
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.ui.prices import (
    category_keys,
    punt_switches,
    show_price_table,
    show_roster_table,
    show_suggestion_table,
    show_summary_table,
)
from fantasyhelper.valuation.prices import (
    DRAFT,
    KEEPER,
    MINE,
    OTHER,
    PriceRow,
    Sale,
    Suggestion,
    build_price_table,
    category_summary,
    draft_suggestions,
    max_bid,
    reprice_remaining,
)
from fantasyhelper.valuation.projection import lines_from_rows

_TYPE_LABELS = {DRAFT: "Draft", KEEPER: "Keeper"}
_POSITIONS = ("PG", "SG", "SF", "PF", "C")
# One text line, matching the dataframe's default row and header, plus its border.
_ROW_PX = 35
_HEADER_PX = 35
_BORDER_PX = 1


def render_draft(league: League) -> None:
    _apply_check_reset(league.id)
    settings = league.settings
    sales = list_sales(league.id)
    players, seasons, projections = load_baseline_rows()
    table = build_price_table(
        lines_from_rows(players, seasons, projections),
        settings.categories,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    by_id = {row.player_id: row for row in table.rows}
    names = {int(player["id"]): str(player["name"]) for player in players}
    league_side, user_side = category_summary(
        by_id,
        sales,
        settings.categories,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    punted: frozenset[str] = frozenset()
    priced = None
    can_pick = table.error is None and bool(table.rows)
    with st.container(horizontal=True, vertical_alignment="top", gap="medium", wrap=False):
        _sold_lists(league.id, sales, names, by_id, settings.team_count, settings.roster_size)
        with st.container(gap="medium"):
            if can_pick:
                punted = punt_switches(league.id, settings.categories)
            show_summary_table(league_side, user_side, settings.categories)
            if can_pick:
                with st.container(gap="xsmall"):
                    chosen = st.session_state.get(_player_key(league.id))
                    if chosen is not None and chosen not in {row.player_id for row in table.rows}:
                        st.session_state.pop(_player_key(league.id), None)
                        chosen = None
                    player_id = chosen if isinstance(chosen, int) else None
                    sale = None
                    if player_id is not None:
                        sale = next(
                            (item for item in sales if item.player_id == player_id),
                            None,
                        )
                    priced = reprice_remaining(
                        table.rows,
                        sales,
                        settings.team_count,
                        settings.budget,
                        settings.roster_size,
                        punted,
                    )
                    st.session_state[_shown_key(league.id)] = player_id
                    _player_view(
                        league,
                        player_id,
                        by_id.get(player_id) if player_id is not None else None,
                        priced.rows,
                        sales,
                        punted,
                    )
                    with st.container(
                        horizontal=True,
                        vertical_alignment="center",
                        gap="medium",
                        wrap=False,
                        width="content",
                    ):
                        _search(league.id, table.rows)
                        errors = _sale_form(league, player_id, sale)
                    for message in errors:
                        st.error(message)
                _available(league.id, priced.error, priced.rows, settings.categories, punted)
                if priced.error is None:
                    nominations, targets = draft_suggestions(
                        priced.rows,
                        user_side,
                        league_side,
                        category_keys(settings.categories),
                        punted,
                        max_bid(settings.budget, settings.roster_size, sales),
                    )
                    with st.container(
                        horizontal=True, vertical_alignment="top", gap="medium", width="content"
                    ):
                        with st.container(width="content"):
                            _suggestions(
                                league.id,
                                "Nominations",
                                "draft-nominations",
                                nominations,
                                punted,
                                target=False,
                            )
                        with st.container(width="content"):
                            _suggestions(
                                league.id, "Targets", "draft-targets", targets, punted, target=True
                            )
    if table.error:
        st.error(table.error)
        return
    if not table.rows or priced is None:
        st.write("No players are in the projection yet.")
        return


def _figure(markup: str) -> None:
    st.markdown(
        f"<p class='draft-figure'>{markup}</p>",
        unsafe_allow_html=True,
    )


def _list_title(title: str) -> None:
    st.markdown(
        f"<p class='list-title'>{html.escape(title)}</p>",
        unsafe_allow_html=True,
    )


def _bid(amount: int | None) -> str:
    if amount is None:
        return "No spot left"
    return f"${amount}"


def _player_key(league_id: int) -> str:
    return f"draft-player-{league_id}"


def _shown_key(league_id: int) -> str:
    return f"draft-player-shown-{league_id}"


def roster_position_key(positions: str, name: str) -> tuple[int, int, str, str]:
    """PG through C, then fewer positions, then the name."""
    codes = tuple(part for part in positions.split("/") if part)
    indexes = [_POSITIONS.index(code) for code in codes if code in _POSITIONS]
    if not codes:
        earliest = len(_POSITIONS) + 1
    elif not indexes:
        earliest = len(_POSITIONS)
    else:
        earliest = min(indexes)
    return (earliest, len(codes), name.casefold(), name)


def taken_title(label: str, count: int, spots: int) -> str:
    """How many players are on that side, out of that side's spots."""
    return f"{label} ({count}/{spots})"


def roster_table_height(roster_size: int) -> int:
    """Pixel height for the header plus one row per roster spot."""
    return roster_size * _ROW_PX + _HEADER_PX + 2 * _BORDER_PX


def ordered_taken(
    sales: Sequence[Sale],
    side: str,
    positions: dict[int, str],
    names: dict[int, str],
    *,
    newest_first: bool,
) -> tuple[Sale, ...]:
    """Your players follow position. Other teams follow entry, newest first."""
    chosen = tuple(sale for sale in sales if sale.side == side)
    if newest_first:
        return tuple(reversed(chosen))
    return tuple(
        sorted(
            chosen,
            key=lambda sale: roster_position_key(
                positions.get(sale.player_id, ""),
                names.get(sale.player_id, ""),
            ),
        )
    )


def search_pick_stands(current: int | None, shown: int | None, *, shown_known: bool) -> bool:
    """A search choice in this interaction stays. A list click still replaces the open player."""
    return shown_known and current != shown


def open_player_after_check(
    current: int | None, ids: Sequence[int], picked: Sequence[int]
) -> int | None:
    """The player a list check leaves open. Clearing that player's row clears the search."""
    if not picked:
        if current in ids:
            return None
        return current
    index = picked[0]
    if index < 0 or index >= len(ids):
        return current
    return ids[index]


def checked_row(ids: Sequence[int], player_id: int | None) -> list[int]:
    """The row of the open player, or no row when that player is not in the list."""
    if player_id is None:
        return []
    try:
        return [ids.index(player_id)]
    except ValueError:
        return []


def _search(league_id: int, rows: tuple[PriceRow, ...]) -> None:
    ordered = tuple(sorted(rows, key=lambda row: (row.name.casefold(), row.name)))
    ids = [row.player_id for row in ordered]
    names = {row.player_id: row.name for row in ordered}
    key = _player_key(league_id)
    chosen = st.session_state.get(key)
    if chosen is not None and chosen not in names:
        st.session_state.pop(key, None)
    kwargs = {}
    if key not in st.session_state:
        kwargs["index"] = None
    with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content"):
        st.markdown(
            "<p class='draft-figure search-player'>Search player</p>",
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Search player",
            ids,
            format_func=lambda player_id: names[player_id],
            key=key,
            placeholder="Player name",
            label_visibility="collapsed",
            **kwargs,
        )


def player_price_line(row: PriceRow | None, bid: str) -> str:
    """TZ, TC, and PC under the open player, then the max bid. PZ stays off this line."""
    parts = (
        f"TZ Price: {_bold(_dollar(None if row is None else row.plain_price))}",
        f"TC Price: {_bold(_dollar(None if row is None else row.curved_price))}",
        f"PC Price: {_bold(_dollar(None if row is None else row.personal_curved_price))}",
        f"Max bid: {_bold(bid)}",
    )
    return "".join(f"<span class='price-param'>{part}</span>" for part in parts)


def team_buttons(sale: Sale | None) -> tuple[tuple[str, str, bool], tuple[str, str, bool]]:
    """The my-team button, then the other-team button.

    Each entry is the label, the side it writes, and whether it edits the current sale.
    An edit stays off until keeper or draft, or the price, changes.
    """
    if sale is None:
        return (("Add to my team", MINE, False), ("Add to another", OTHER, False))
    if sale.side == MINE:
        return (("Edit my team", MINE, True), ("Switch to another", OTHER, False))
    return (("Switch to my team", MINE, False), ("Edit in another", OTHER, True))


def form_changed(sale: Sale, sale_type: str | None, price: object) -> bool:
    """Keeper or draft, or the price, differs from the saved sale."""
    return not (sale_type == sale.sale_type and _whole_dollars(price) == sale.price)


def _dollar(amount: int | None) -> str:
    if amount is None:
        return ""
    return f"${amount}"


def _bold(value: str) -> str:
    return f"<strong>{html.escape(value)}</strong>"


def _player_view(
    league: League,
    player_id: int | None,
    base: PriceRow | None,
    available: tuple[PriceRow, ...],
    sales: tuple[Sale, ...],
    punted: frozenset[str],
) -> None:
    shown = None
    if player_id is not None:
        shown = next((row for row in available if row.player_id == player_id), None)
    line = (shown,) if shown is not None else ((base,) if base is not None else ())
    show_price_table(line, league.settings.categories, punted, ranks=False, prices=False)
    row = line[0] if line else None
    rest = tuple(item for item in sales if item.player_id != player_id)
    bid = _bid(max_bid(league.settings.budget, league.settings.roster_size, rest))
    st.markdown(
        f"<p class='draft-figure'>{player_price_line(row, bid)}</p>",
        unsafe_allow_html=True,
    )


def _sale_form(
    league: League,
    player_id: int | None,
    sale: Sale | None,
) -> tuple[str, ...]:
    suffix = str(player_id) if player_id is not None else "none"
    type_key = f"sale-type-{league.id}-{suffix}"
    price_key = f"sale-price-{league.id}-{suffix}"
    if type_key not in st.session_state:
        st.session_state[type_key] = sale.sale_type if sale is not None else DRAFT
    if price_key not in st.session_state:
        st.session_state[price_key] = sale.price if sale is not None else None
    open_player = player_id is not None
    with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content"):
        sale_type = st.segmented_control(
            "Keeper or draft",
            (DRAFT, KEEPER),
            format_func=lambda item: _TYPE_LABELS[item],
            key=type_key,
            required=True,
            label_visibility="collapsed",
            width="content",
            disabled=not open_player,
        )
        st.markdown("<p class='draft-figure sale-price'>Price</p>", unsafe_allow_html=True)
        price = st.number_input(
            "Price",
            min_value=1,
            step=1,
            key=price_key,
            width=120,
            label_visibility="collapsed",
            disabled=not open_player,
        )
        return _sale_actions(league, player_id, sale, sale_type, price)


def _sale_actions(
    league: League,
    player_id: int | None,
    sale: Sale | None,
    sale_type: str | None,
    price: object,
) -> tuple[str, ...]:
    errors: tuple[str, ...] = ()
    suffix = str(player_id) if player_id is not None else "none"
    changed = sale is not None and form_changed(sale, sale_type, price)
    with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content"):
        for label, side, edits in team_buttons(sale):
            if st.button(
                label,
                key=f"sale-{side}-{league.id}-{suffix}",
                disabled=player_id is None or (edits and not changed),
            ):
                errors = _save_sale(
                    league,
                    player_id,
                    side,
                    sale_type,
                    price,
                    replacing=sale is not None,
                )
    return errors


def _save_sale(
    league: League,
    player_id: int | None,
    side: str | None,
    sale_type: str | None,
    price: object,
    *,
    replacing: bool,
) -> tuple[str, ...]:
    if player_id is None or side is None or sale_type is None:
        return ("Choose a player.",)
    whole = _whole_dollars(price)
    if whole is None:
        return ("Enter a whole-dollar price.",)
    save = update_sale if replacing else record_sale
    errors = save(league, player_id, side, whole, sale_type)
    if errors:
        return errors
    # The sold lists already exist on this run, so their checks reset on the next one.
    st.session_state[_check_reset_key(league.id)] = True
    st.rerun()
    return ()


def _whole_dollars(price: object) -> int | None:
    if type(price) is int:
        return price
    if type(price) is float and price.is_integer():
        return int(price)
    return None


def _suggestions(
    league_id: int,
    title: str,
    key_name: str,
    suggestions: tuple[Suggestion, ...],
    punted: frozenset[str],
    *,
    target: bool,
) -> None:
    with st.container(gap="xxsmall"):
        _list_title(title)
        if not suggestions:
            _drop_list_check(f"{key_name}-{league_id}")
            st.write("No nominations." if not target else "No targets.")
            return
        ids = tuple(item.player_id for item in suggestions)
        st.session_state[f"{key_name}-ids-{league_id}"] = ids
        _sync_list_check(f"{key_name}-{league_id}", ids, st.session_state.get(_player_key(league_id)))
        show_suggestion_table(
            suggestions,
            punted,
            selection_key=f"{key_name}-{league_id}",
            on_select=_open_row(
                f"{key_name}-{league_id}",
                f"{key_name}-ids-{league_id}",
                _player_key(league_id),
                _shown_key(league_id),
            ),
        )


def _available(
    league_id: int,
    error: str | None,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> None:
    with st.container(gap="xxsmall"):
        _list_title("Still available")
        if error:
            _drop_list_check(f"draft-available-{league_id}")
            st.error(error)
            return
        if not rows:
            _drop_list_check(f"draft-available-{league_id}")
            st.write("No players are still available.")
            return
        _selectable_prices(
            league_id, "draft-available", rows, active, punted, prices=False, pz_rank=False
        )


def _sold_lists(
    league_id: int,
    sales: tuple[Sale, ...],
    names: dict[int, str],
    rows_by_id: dict[int, PriceRow],
    team_count: int,
    roster_size: int,
) -> None:
    """The left column: Your players, then Other teams."""
    positions = {
        player_id: row.positions for player_id, row in rows_by_id.items()
    }
    height = roster_table_height(roster_size)
    with st.container(width="content", gap="medium"):
        _taken(
            league_id,
            "Your players",
            "draft-yours",
            ordered_taken(sales, MINE, positions, names, newest_first=False),
            names,
            rows_by_id,
            roster_size,
            height,
        )
        _taken(
            league_id,
            "Other teams",
            "draft-others",
            ordered_taken(sales, OTHER, positions, names, newest_first=True),
            names,
            rows_by_id,
            (team_count - 1) * roster_size,
            height,
        )


def _taken(
    league_id: int,
    title: str,
    key_name: str,
    sales: tuple[Sale, ...],
    names: dict[int, str],
    rows_by_id: dict[int, PriceRow],
    spots: int,
    height: int,
) -> None:
    with st.container(gap="xxsmall"):
        _list_title(taken_title(title, len(sales), spots))
        table_key = f"{key_name}-{league_id}"
        if not sales:
            _drop_list_check(table_key)
        else:
            ids = tuple(sale.player_id for sale in sales)
            st.session_state[f"{key_name}-ids-{league_id}"] = ids
            _sync_list_check(table_key, ids, st.session_state.get(_player_key(league_id)))
        show_roster_table(
            sales,
            rows_by_id,
            names,
            selection_key=table_key,
            on_select=_open_row(
                table_key,
                f"{key_name}-ids-{league_id}",
                _player_key(league_id),
                _shown_key(league_id),
            ),
            height=height,
        )


def _selectable_prices(
    league_id: int,
    key_name: str,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
    *,
    prices: bool = True,
    pz_rank: bool = True,
) -> None:
    ids = tuple(row.player_id for row in rows)
    st.session_state[f"{key_name}-ids-{league_id}"] = ids
    _sync_list_check(f"{key_name}-{league_id}", ids, st.session_state.get(_player_key(league_id)))
    show_price_table(
        rows,
        active,
        punted,
        prices=prices,
        pz_rank=pz_rank,
        selection_key=f"{key_name}-{league_id}",
        on_select=_open_row(
            f"{key_name}-{league_id}",
            f"{key_name}-ids-{league_id}",
            _player_key(league_id),
            _shown_key(league_id),
        ),
    )


def _open_row(table_key: str, ids_key: str, player_key: str, shown_key: str) -> Callable[[], None]:
    def _open() -> None:
        if search_pick_stands(
            st.session_state.get(player_key),
            st.session_state.get(shown_key),
            shown_known=shown_key in st.session_state,
        ):
            return
        state = st.session_state.get(table_key)
        ids: Sequence[int] = st.session_state.get(ids_key) or ()
        if state is None or not ids:
            return
        picked = _selected_rows(state)
        if not picked:
            # An uncheck does not replace the stored selection on its own.
            st.session_state[table_key] = _selection_state(())
        current = st.session_state.get(player_key)
        current_id = current if isinstance(current, int) else None
        remembered = open_player_after_check(current_id, ids, picked)
        if remembered != current:
            # None is stored on purpose. Dropping the key lets the search keep the old player.
            st.session_state[player_key] = remembered

    return _open


def _sync_list_check(table_key: str, ids: Sequence[int], player_id: int | None) -> None:
    """Keep this list's check on the open player, and clear it otherwise."""
    wanted = checked_row(ids, player_id)
    if _selected_rows(st.session_state.get(table_key)) == wanted:
        return
    st.session_state[table_key] = _selection_state(wanted)


def _drop_list_check(table_key: str) -> None:
    st.session_state.pop(table_key, None)


def _selected_rows(state: object) -> list[int]:
    if state is None:
        return []
    selection = state["selection"] if isinstance(state, dict) else state.selection
    rows = selection["rows"] if isinstance(selection, dict) else selection.rows
    return list(rows)


def _selection_state(rows: Sequence[int]) -> dict[str, dict[str, list[int]]]:
    return {"selection": {"rows": list(rows), "columns": [], "cells": []}}


def _check_reset_key(league_id: int) -> str:
    return f"draft-reset-checks-{league_id}"


def _apply_check_reset(league_id: int) -> None:
    """Clear list checks before any of those tables are created."""
    if st.session_state.pop(_check_reset_key(league_id), False):
        _clear_list_selection(league_id)


def _clear_list_selection(league_id: int) -> None:
    """Drop every list check. An empty selection is sent so a removed row cannot stay checked."""
    empty = _selection_state(())
    for name in ("draft-nominations", "draft-targets", "draft-available", "draft-yours", "draft-others"):
        st.session_state[f"{name}-{league_id}"] = empty
