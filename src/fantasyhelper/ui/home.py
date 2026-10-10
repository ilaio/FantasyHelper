"""Home screen: the open league, then the imported player tables."""

import streamlit as st

from fantasyhelper.stats.inbox import import_inbox
from fantasyhelper.stats.store import Dataset, list_datasets, load_player_rows
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
[data-testid="stMainBlockContainer"],
.block-container {
    max-width: 100%;
    padding-top: 1.25rem;
    padding-left: 1.25rem;
    padding-right: 1.25rem;
}
.league-name {
    font-size: 1.4rem;
    font-weight: 600;
    line-height: 1.3;
    margin: 0;
    color: #000000;
}
.league-details {
    font-size: 0.85rem;
    line-height: 1.4;
    margin: 0.2rem 0 0;
    color: #000000;
}
div[data-testid="stCaptionContainer"] p {
    font-size: 0.8rem;
    color: #767676;
}
</style>
"""


def render() -> None:
    st.set_page_config(page_title="FantasyHelper", layout="wide")
    st.markdown(_LAYOUT, unsafe_allow_html=True)
    st.title("FantasyHelper")
    render_league()
    _render_datasets()


def _render_datasets() -> None:
    st.subheader("Players")
    report = import_inbox()
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
