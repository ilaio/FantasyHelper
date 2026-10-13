"""Draft tab: money, the three lists, and one player view."""

import html
from collections.abc import Callable, Sequence

import streamlit as st

from fantasyhelper.leagues.league import League, LeagueSettings
from fantasyhelper.leagues.sales import list_sales, record_sale, remove_sale, update_sale
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.ui.prices import current_punts, punt_switches, show_price_table
from fantasyhelper.valuation.prices import (
    DRAFT,
    KEEPER,
    MINE,
    OTHER,
    AuctionSummary,
    PriceRow,
    Sale,
    auction_summary,
    build_price_table,
    max_bid,
    reprice_remaining,
)
from fantasyhelper.valuation.projection import lines_from_rows

_SIDE_LABELS = {MINE: "My team", OTHER: "Another team"}
_TYPE_LABELS = {DRAFT: "Draft", KEEPER: "Keeper"}


def render_draft(league: League) -> None:
    settings = league.settings
    sales = list_sales(league.id)
    summary = auction_summary(
        settings.team_count,
        settings.budget,
        settings.roster_size,
        sales,
    )
    _figures(summary)
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

    names = {int(player["id"]): str(player["name"]) for player in players}
    by_id = {row.player_id: row for row in table.rows}
    with st.container(gap="xsmall"):
        _search(league.id, table.rows)
        chosen = st.session_state.get(_player_key(league.id))
        punted = current_punts(league.id, settings.categories)
        priced = reprice_remaining(
            table.rows,
            sales,
            settings.team_count,
            settings.budget,
            settings.roster_size,
            punted,
        )
        player_id = chosen if isinstance(chosen, int) else None
        _player_view(
            league,
            player_id,
            by_id.get(player_id) if player_id is not None else None,
            priced.rows,
            sales,
            punted,
        )
    punt_switches(league.id, settings.categories)
    _available(league.id, priced.error, priced.rows, settings.categories, punted)
    _taken(league.id, "Your players", "draft-yours", sales, MINE, names)
    _taken(league.id, "Other teams", "draft-others", sales, OTHER, names)


def _figures(summary: AuctionSummary) -> None:
    with st.container(horizontal=True, gap="large", width="content", vertical_alignment="center"):
        _figure(_money("Your money", summary.yours_left, summary.yours_spent))
        _figure(_spots("Your spots", summary.yours_open, summary.yours_taken))
        _figure(_money("League money", summary.league_left, summary.league_spent))
        _figure(_spots("League spots", summary.league_open, summary.league_taken))


def _money(label: str, left: int, spent: int) -> str:
    return f"{html.escape(label)}: <strong>${left}</strong> left (${spent} spent)"


def _spots(label: str, left: int, taken: int) -> str:
    return f"{html.escape(label)}: <strong>{left}</strong> left ({taken} taken)"


def _figure(markup: str) -> None:
    st.markdown(
        f"<p class='draft-figure'>{markup}</p>",
        unsafe_allow_html=True,
    )


def _bid(amount: int | None) -> str:
    if amount is None:
        return "No spot left"
    return f"${amount}"


def _player_key(league_id: int) -> str:
    return f"draft-player-{league_id}"


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


def _player_view(
    league: League,
    player_id: int | None,
    base: PriceRow | None,
    available: tuple[PriceRow, ...],
    sales: tuple[Sale, ...],
    punted: frozenset[str],
) -> None:
    sale = None
    if player_id is not None:
        sale = next((item for item in sales if item.player_id == player_id), None)
    shown = None
    if player_id is not None:
        shown = next((row for row in available if row.player_id == player_id), None)
    line = (shown,) if shown is not None else ((base,) if base is not None else ())
    show_price_table(line, league.settings.categories, punted)
    _sale_form(league, player_id, sale, sales)


def _sale_form(
    league: League,
    player_id: int | None,
    sale: Sale | None,
    sales: tuple[Sale, ...],
) -> None:
    suffix = str(player_id) if player_id is not None else "none"
    side_key = f"sale-side-{league.id}-{suffix}"
    type_key = f"sale-type-{league.id}-{suffix}"
    price_key = f"sale-price-{league.id}-{suffix}"
    if side_key not in st.session_state:
        st.session_state[side_key] = sale.side if sale is not None else MINE
    if type_key not in st.session_state:
        st.session_state[type_key] = sale.sale_type if sale is not None else DRAFT
    if price_key not in st.session_state:
        st.session_state[price_key] = sale.price if sale is not None else None
    open_player = player_id is not None
    with st.container(horizontal=True, vertical_alignment="center", gap="small", width="stretch"):
        side = st.segmented_control(
            "Team",
            (MINE, OTHER),
            format_func=lambda item: _SIDE_LABELS[item],
            key=side_key,
            required=True,
            label_visibility="collapsed",
            width="content",
            disabled=not open_player,
        )
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
        st.markdown(
            f"<p class='draft-figure'>{html.escape(_cap_text(league.settings, sales, player_id, side))}</p>",
            unsafe_allow_html=True,
        )
        errors = _sale_actions(league, player_id, sale, side, sale_type, price)
    for message in errors:
        st.error(message)


def _sale_actions(
    league: League,
    player_id: int | None,
    sale: Sale | None,
    side: str | None,
    sale_type: str | None,
    price: object,
) -> tuple[str, ...]:
    errors: tuple[str, ...] = ()
    suffix = str(player_id) if player_id is not None else "none"
    with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content"):
        if sale is None:
            if st.button(
                "Mark sold",
                key=f"sale-mark-{league.id}-{suffix}",
                disabled=player_id is None,
            ):
                errors = _save_sale(league, player_id, side, sale_type, price, replacing=False)
            return errors
        if st.button(
            "Save",
            key=f"sale-save-{league.id}-{suffix}",
            disabled=not _sale_changed(sale, side, sale_type, price),
        ):
            errors = _save_sale(league, player_id, side, sale_type, price, replacing=True)
        if st.button("Unmark", key=f"sale-clear-{league.id}-{suffix}"):
            _unmark(league.id, player_id)
    return errors


def _sale_changed(sale: Sale, side: str | None, sale_type: str | None, price: object) -> bool:
    return not (
        side == sale.side
        and sale_type == sale.sale_type
        and _whole_dollars(price) == sale.price
    )


def _cap_text(
    settings: LeagueSettings,
    sales: tuple[Sale, ...],
    player_id: int | None,
    side: str | None,
) -> str:
    if side == OTHER:
        return f"Team budget: ${settings.budget}"
    rest = tuple(sale for sale in sales if sale.player_id != player_id)
    return f"Max bid: {_bid(max_bid(settings.budget, settings.roster_size, rest))}"


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
    _clear_list_selection(league.id)
    st.rerun()
    return ()


def _unmark(league_id: int, player_id: int | None) -> None:
    if player_id is None:
        return
    remove_sale(league_id, player_id)
    for name in ("side", "type", "price"):
        st.session_state.pop(f"sale-{name}-{league_id}-{player_id}", None)
    _clear_list_selection(league_id)
    st.rerun()


def _whole_dollars(price: object) -> int | None:
    if type(price) is int:
        return price
    if type(price) is float and price.is_integer():
        return int(price)
    return None


def _available(
    league_id: int,
    error: str | None,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> None:
    st.subheader("Still available")
    if error:
        st.error(error)
        return
    if not rows:
        st.write("No players are still available.")
        return
    _selectable_prices(league_id, "draft-available", rows, active, punted)


def _taken(
    league_id: int,
    title: str,
    key_name: str,
    sales: tuple[Sale, ...],
    side: str,
    names: dict[int, str],
) -> None:
    st.subheader(title)
    chosen = tuple(sale for sale in sales if sale.side == side)
    if not chosen:
        st.write("No players yet.")
        return
    ids = tuple(sale.player_id for sale in chosen)
    st.session_state[f"{key_name}-ids-{league_id}"] = ids
    st.dataframe(
        [
            {
                "Name": names.get(sale.player_id, "Unknown player"),
                "Price": sale.price,
                "Sale": _TYPE_LABELS[sale.sale_type],
            }
            for sale in chosen
        ],
        hide_index=True,
        width="content",
        column_config={
            "Name": st.column_config.Column(alignment="left"),
            "Price": st.column_config.NumberColumn(alignment="center", format="$%d"),
            "Sale": st.column_config.Column(alignment="center"),
        },
        key=f"{key_name}-{league_id}",
        on_select=_open_row(f"{key_name}-{league_id}", f"{key_name}-ids-{league_id}", _player_key(league_id)),
        selection_mode="single-row",
    )


def _selectable_prices(
    league_id: int,
    key_name: str,
    rows: tuple[PriceRow, ...],
    active: frozenset[str],
    punted: frozenset[str],
) -> None:
    ids = tuple(row.player_id for row in rows)
    st.session_state[f"{key_name}-ids-{league_id}"] = ids
    show_price_table(
        rows,
        active,
        punted,
        selection_key=f"{key_name}-{league_id}",
        on_select=_open_row(
            f"{key_name}-{league_id}",
            f"{key_name}-ids-{league_id}",
            _player_key(league_id),
        ),
    )


def _open_row(table_key: str, ids_key: str, player_key: str) -> Callable[[], None]:
    def _open() -> None:
        state = st.session_state.get(table_key)
        ids: Sequence[int] = st.session_state.get(ids_key) or ()
        if state is None or not ids:
            return
        picked = state.selection.rows
        if not picked:
            return
        index = picked[0]
        if index < 0 or index >= len(ids):
            return
        st.session_state[player_key] = ids[index]

    return _open


def _clear_list_selection(league_id: int) -> None:
    for name in ("draft-available", "draft-yours", "draft-others"):
        st.session_state.pop(f"{name}-{league_id}", None)
