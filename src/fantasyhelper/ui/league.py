"""Compact league header. Create and edit open over the screen."""

import html

import streamlit as st

from fantasyhelper.leagues.league import (
    BUDGET_MAX,
    BUDGET_MIN,
    CATEGORIES,
    ROSTER_MAX,
    ROSTER_MIN,
    TEAM_MAX,
    TEAM_MIN,
    League,
    LeagueSettings,
    create_league,
    default_settings,
    list_leagues,
    remove_league,
    summary,
    update_league,
)


def render_league() -> None:
    leagues = list_leagues()
    if not leagues:
        _render_empty()
        return

    ids = [league.id for league in leagues]
    _prepare_open(ids)
    current = st.session_state.get("open-league", ids[0])
    league = next(item for item in leagues if item.id == current)
    left, right = st.columns([1.2, 1], vertical_alignment="center")
    with left:
        _name(league.settings.name)
        _details(summary(league))
    with right:
        edit, remove, create, switch = st.columns(4, vertical_alignment="bottom")
        with edit:
            if st.button("Edit league", key="edit-league", width="stretch"):
                _edit_dialog(league)
        with remove:
            if st.button("Remove league", key="remove-league", width="stretch"):
                remaining = tuple(item.id for item in leagues if item.id != league.id)
                _remove_dialog(league.id, league.settings.name, remaining)
        with create:
            if st.button("Create league", key="create-league", width="stretch"):
                st.session_state["create_generation"] = (
                    st.session_state.get("create_generation", 0) + 1
                )
                _create_dialog()
        with switch:
            _switch_league(leagues)


def _render_empty() -> None:
    left, right = st.columns([1.2, 1], vertical_alignment="center")
    with left:
        _name("No league is loaded yet.")
    with right:
        if st.button("Create league", key="create-league", width="stretch"):
            st.session_state["create_generation"] = (
                st.session_state.get("create_generation", 0) + 1
            )
            _create_dialog()


def _name(text: str) -> None:
    st.markdown(
        f"<p class='league-name'>{html.escape(text)}</p>",
        unsafe_allow_html=True,
    )


def _details(text: str) -> None:
    st.markdown(
        f"<p class='league-details'>{html.escape(text)}</p>",
        unsafe_allow_html=True,
    )


def _prepare_open(ids: list[int]) -> None:
    pending = st.session_state.pop("open-league-pending", None)
    if pending in ids:
        st.session_state["open-league"] = pending
    elif st.session_state.get("open-league") not in ids:
        st.session_state.pop("open-league", None)


def _switch_league(leagues: list[League]) -> None:
    ids = [league.id for league in leagues]
    labels = {league.id: league.settings.name for league in leagues}
    kwargs = {}
    if "open-league" not in st.session_state:
        kwargs["index"] = 0
    st.selectbox(
        "Switch league",
        ids,
        format_func=lambda league_id: labels[league_id],
        key="open-league",
        width="stretch",
        **kwargs,
    )


@st.dialog("Edit league", width="large")
def _edit_dialog(league: League) -> None:
    settings = _settings_form(
        prefix=f"edit-{league.id}",
        defaults=league.settings,
        submit_label="Save",
    )
    if settings is None:
        return
    errors = update_league(league.id, settings)
    if errors:
        for message in errors:
            st.error(message)
        return
    st.rerun()


@st.dialog("Create league", width="large")
def _create_dialog() -> None:
    generation = st.session_state.get("create_generation", 0)
    settings = _settings_form(
        prefix=f"create-{generation}",
        defaults=default_settings(),
        submit_label="Create league",
    )
    if settings is None:
        return
    created = create_league(settings)
    if not isinstance(created, int):
        for message in created:
            st.error(message)
        return
    st.session_state["open-league-pending"] = created
    st.rerun()


@st.dialog("Remove league")
def _remove_dialog(league_id: int, name: str, remaining: tuple[int, ...]) -> None:
    st.write(
        f"Remove {name}? It leaves the list. Draft entries for this league stay."
    )
    if st.button("Remove league", key="confirm-remove"):
        remove_league(league_id)
        if remaining:
            st.session_state["open-league-pending"] = remaining[0]
        st.rerun()
    if st.button("Keep league", key="keep-league"):
        st.rerun()


def _settings_form(
    *,
    prefix: str,
    defaults: LeagueSettings,
    submit_label: str,
) -> LeagueSettings | None:
    with st.form(f"{prefix}-form"):
        name = st.text_input("Name", value=defaults.name, key=f"{prefix}-name")
        season = st.text_input(
            "Season",
            value=defaults.season,
            key=f"{prefix}-season",
            help="The season this league is drafting. Prices use the 2025-26 season.",
        )
        team_count = st.number_input(
            "Teams",
            min_value=TEAM_MIN,
            max_value=TEAM_MAX,
            value=defaults.team_count,
            step=1,
            key=f"{prefix}-teams",
        )
        budget = st.number_input(
            "Budget",
            min_value=BUDGET_MIN,
            max_value=BUDGET_MAX,
            value=defaults.budget,
            step=1,
            key=f"{prefix}-budget",
        )
        roster_size = st.number_input(
            "Roster spots",
            min_value=ROSTER_MIN,
            max_value=ROSTER_MAX,
            value=defaults.roster_size,
            step=1,
            key=f"{prefix}-roster",
        )
        st.write("Categories")
        columns = st.columns(3)
        selected: list[str] = []
        for index, (key, label) in enumerate(CATEGORIES):
            with columns[index % 3]:
                if st.checkbox(
                    label,
                    value=key in defaults.categories,
                    key=f"{prefix}-cat-{key}",
                ):
                    selected.append(key)
        submitted = st.form_submit_button(submit_label)
    if not submitted:
        return None
    return LeagueSettings(
        name=name.strip(),
        season=season.strip(),
        team_count=_as_int(team_count),
        budget=_as_int(budget),
        roster_size=_as_int(roster_size),
        categories=frozenset(selected),
    )


def _as_int(value: object) -> int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0
