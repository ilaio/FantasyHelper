"""Draft tab: league and user money, spots, and the max bid."""

import html

import streamlit as st

from fantasyhelper.leagues.league import League
from fantasyhelper.leagues.sales import list_sales
from fantasyhelper.ui.prices import render_prices
from fantasyhelper.valuation.prices import AuctionSummary, auction_summary


def render_draft(league: League) -> None:
    settings = league.settings
    summary = auction_summary(
        settings.team_count,
        settings.budget,
        settings.roster_size,
        list_sales(league.id),
    )
    _figures(summary)
    render_prices(league)


def _figures(summary: AuctionSummary) -> None:
    _row(
        f"League money: ${summary.league_left} left (${summary.league_spent} spent)",
        f"League spots: {summary.league_open} left ({summary.league_taken} taken)",
    )
    _row(
        f"Your money: ${summary.yours_left} left (${summary.yours_spent} spent)",
        f"Your spots: {summary.yours_open} left ({summary.yours_taken} taken)",
        f"Max bid: {_bid(summary.max_bid)}",
    )


def _row(*parts: str) -> None:
    with st.container(horizontal=True, gap="large", width="content", vertical_alignment="center"):
        for part in parts:
            st.markdown(
                f"<p class='draft-figure'>{html.escape(part)}</p>",
                unsafe_allow_html=True,
            )


def _bid(amount: int | None) -> str:
    if amount is None:
        return "No spot left"
    return f"${amount}"


