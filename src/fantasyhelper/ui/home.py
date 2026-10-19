"""Home screen: the open league, then Players and Draft."""

import streamlit as st

from fantasyhelper.stats.inbox import ImportReport, import_inbox
from fantasyhelper.stats.store import Dataset, list_datasets, load_player_rows
from fantasyhelper.ui.draft import render_draft
from fantasyhelper.ui.league import render_league

_SOURCE_LABELS = {
    "bonus": "Bonus",
    "josh": "Josh",
    "fantasyedge": "Fantasy Edge",
}

_STAT_LABELS = {
    "name": "Name",
    "team": "Team",
    "positions": "Positions",
    "games": "Games",
    "minutes": "Minutes",
    "points": "Points",
    "threes": "Threes",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "steals": "Steals",
    "blocks": "Blocks",
    "turnovers": "Turnovers",
    "fg_pct": "FG%",
    "fga": "FGA",
    "ft_pct": "FT%",
    "fta": "FTA",
}

_PROJECTION_LABELS = {
    "name": "Name",
    "team": "Team",
    "positions": "Positions",
    "games": "Games",
    "minutes_per_game": "Minutes",
    "points_per_game": "Points",
    "threes_per_game": "Threes",
    "rebounds_per_game": "Rebounds",
    "assists_per_game": "Assists",
    "steals_per_game": "Steals",
    "blocks_per_game": "Blocks",
    "turnovers_per_game": "Turnovers",
    "fg_pct": "FG%",
    "fga_per_game": "FGA",
    "ft_pct": "FT%",
    "fta_per_game": "FTA",
    "source_rank": "File rank",
    "source_dollars": "File dollars",
}

_RATE_LABELS = (
    "Minutes",
    "Points",
    "Threes",
    "Rebounds",
    "Assists",
    "Steals",
    "Blocks",
    "Turnovers",
    "FGA",
    "FTA",
)


_LAYOUT = """
<style>
header[data-testid="stHeader"] {
    display: none;
}
[data-testid="stMainBlockContainer"],
.block-container {
    max-width: 100%;
    padding-top: 1.25rem;
    padding-left: 1.25rem;
    padding-right: 1.25rem;
}
[data-testid="stMarkdownContainer"]:has(.league-name) {
    font-size: 2.5rem;
    margin-bottom: 0;
    width: auto;
}
[data-testid="stMarkdownContainer"] .league-name {
    font-size: 1em;
    font-weight: 600;
    line-height: 1.15;
    margin: 0;
    color: #000000;
}
[data-testid="stMarkdownContainer"]:has(.league-details),
[data-testid="stMarkdownContainer"]:has(.draft-figure),
[data-testid="stMarkdownContainer"]:has(.list-title) {
    margin-bottom: 0;
    width: auto;
}
[data-testid="stMarkdownContainer"] .league-details {
    font-size: 0.95rem;
    line-height: 1.4;
    margin: 0;
    padding-bottom: 3px;
    width: fit-content;
    color: #8A8A8A;
}
[data-testid="stHorizontalBlock"]:has(.league-name) {
    width: 100%;
    align-items: center;
}
[data-testid="stHorizontalBlock"]:has(.league-name) > div {
    width: auto;
    flex: 0 0 auto;
}
[data-testid="stHorizontalBlock"]:has(.league-name) > div:last-child {
    margin-left: auto;
}
[data-testid="stHorizontalBlock"]:has(.league-name):has(.league-details) > div:nth-child(2) {
    align-self: flex-end;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stElementContainer"] .draft-figure) {
    width: fit-content;
    align-items: center;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stElementContainer"] .sale-price) > div:last-child {
    margin-left: 0.75rem;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stElementContainer"] .draft-figure) > div {
    width: auto;
    flex: 0 0 auto;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stElementContainer"] .search-player) > div:has([data-testid="stSelectbox"]) {
    width: 50ch;
    flex: 0 0 50ch;
}
button[data-testid="stPopoverButton"] {
    width: 2.5rem;
    height: 2.5rem;
    min-width: 2.5rem;
    min-height: 2.5rem;
    padding: 0;
    border-radius: 50%;
    border: 1px solid #D4D4D4;
    background-color: #F7F7F7;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06), 0 4px 10px rgba(0, 0, 0, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
}
button[data-testid="stPopoverButton"]:hover {
    background-color: #D9D9D9;
}
button[data-testid="stPopoverButton"] > div {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
}
[data-testid="stPopoverButton"] [data-testid="stIconMaterial"] {
    font-size: 1.35rem;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    transform: translateX(-2px);
}
[data-testid="stPopoverButton"] > div > div:last-child {
    display: none;
}
div[data-testid="stCaptionContainer"] p {
    font-size: 0.8rem;
    color: #767676;
}
[data-testid="stMarkdownContainer"] .draft-figure {
    font-size: 1rem;
    line-height: 1.15;
    margin: 0;
    color: #000000;
    white-space: nowrap;
}
[data-testid="stMarkdownContainer"] .draft-figure strong {
    font-weight: 700;
}
[data-testid="stMarkdownContainer"] .draft-figure .price-param:not(:last-child) {
    margin-right: 2rem;
}
[data-testid="stMarkdownContainer"] .list-title {
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.15;
    margin: 0;
    color: #000000;
}
div[data-testid="stTabs"] [data-testid="stTab"] {
    flex: 1 1 0;
    justify-content: center;
    border-radius: 0.6rem 0.6rem 0 0;
    background-color: transparent;
    color: #000000;
}
div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    background-color: #F4F4F4;
    color: #000000;
    border: 1px solid #D4D4D4;
    z-index: 1;
}
div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p {
    font-weight: 600;
    color: #000000;
}
div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] .react-aria-SelectionIndicator {
    display: none;
}
</style>
"""


def render() -> None:
    st.set_page_config(page_title="FantasyHelper", layout="wide")
    st.markdown(_LAYOUT, unsafe_allow_html=True)
    league = render_league()
    report = import_inbox()
    players, draft = st.tabs(["Players", "Draft"], key="main-tab")
    with players:
        _render_datasets(report)
    with draft:
        if league is None:
            st.write("No league is loaded yet.")
        else:
            render_draft(league)


def _render_datasets(report: ImportReport) -> None:
    if report.imported:
        st.success("  \n".join(report.imported))
    for message in report.refused:
        st.error(message)

    datasets = list_datasets()
    if not datasets:
        if not report.refused:
            st.write("No dataset is imported yet. Add prepared CSV files to data/inbox/.")
        return

    labels = {dataset.file_name: _dataset_label(dataset) for dataset in datasets}
    names = [dataset.file_name for dataset in datasets]
    if st.session_state.get("dataset") not in names:
        st.session_state.pop("dataset", None)
    selected = st.selectbox(
        "Dataset",
        names,
        format_func=labels.get,
        key="dataset",
    )
    dataset = next(item for item in datasets if item.file_name == selected)
    rows = [_present_row(dataset.kind, row) for row in load_player_rows(dataset)]
    st.caption(_table_caption(dataset, len(rows)))
    st.dataframe(rows, hide_index=True, column_config=_column_config(dataset.kind))


def _dataset_label(dataset: Dataset) -> str:
    if dataset.kind == "stats":
        return f"{dataset.season} stats"
    source = _SOURCE_LABELS.get(dataset.source, dataset.source)
    return f"{dataset.season} projection, {source}"


def _table_caption(dataset: Dataset, count: int) -> str:
    lead = f"{count} players from {dataset.file_name}."
    if dataset.kind == "stats":
        return f"{lead} Counting stats are season totals."
    return (
        f"{lead} Counting stats are per game. "
        "File rank and file dollars are this file's figures, not FantasyHelper prices."
    )


def _present_row(kind: str, raw: dict[str, object]) -> dict[str, object]:
    labels = _PROJECTION_LABELS if kind == "projection" else _STAT_LABELS
    presented: dict[str, object] = {}
    for key, label in labels.items():
        value = raw[key]
        if not isinstance(value, float):
            presented[label] = value
            continue
        whole_season_total = kind == "stats" and key not in {"fg_pct", "ft_pct"}
        whole_rank = key == "source_rank"
        if (whole_season_total or whole_rank) and value.is_integer():
            presented[label] = int(value)
        else:
            presented[label] = value
    return presented


def _column_config(kind: str) -> dict[str, st.column_config.NumberColumn]:
    config: dict[str, st.column_config.NumberColumn] = {
        "FG%": st.column_config.NumberColumn(format="%.3f"),
        "FT%": st.column_config.NumberColumn(format="%.3f"),
    }
    if kind == "projection":
        rate = st.column_config.NumberColumn(format="%.3f")
        for label in _RATE_LABELS:
            config[label] = rate
        config["File dollars"] = st.column_config.NumberColumn(format="%.2f")
    return config
