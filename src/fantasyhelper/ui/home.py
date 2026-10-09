"""Home screen shown before a league exists."""

import streamlit as st

from fantasyhelper.stats.inbox import import_inbox
from fantasyhelper.stats.store import Dataset, list_datasets, load_player_rows

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


def render() -> None:
    st.title("FantasyHelper")
    st.write("No league is loaded yet.")

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
    selected = st.selectbox(
        "Dataset",
        [dataset.file_name for dataset in datasets],
        format_func=labels.get,
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
