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
    columns = st.columns(5)
    figures = (
        ("League money", (f"${summary.league_spent} spent", f"${summary.league_left} left")),
        ("League spots", (f"{summary.league_taken} taken", f"{summary.league_open} left")),
        ("Your money", (f"${summary.yours_spent} spent", f"${summary.yours_left} left")),
        ("Your spots", (f"{summary.yours_taken} taken", f"{summary.yours_open} left")),
        ("Max bid", (_bid(summary.max_bid),)),
    )
    for column, (title, lines) in zip(columns, figures):
        with column:
            _figure(title, lines)


def _bid(amount: int | None) -> str:
    if amount is None:
        return "No spot left"
    return f"${amount}"


def _figure(title: str, lines: tuple[str, ...]) -> None:
    body = "".join(f"<p class='draft-figure-line'>{html.escape(line)}</p>" for line in lines)
    st.markdown(
        f"<p class='draft-figure-title'>{html.escape(title)}</p>{body}",
        unsafe_allow_html=True,
    )
