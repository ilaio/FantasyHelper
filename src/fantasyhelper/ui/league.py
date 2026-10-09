"""League list, settings form, and remove confirmation."""

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
    open_league,
    remove_league,
    summary,
    update_league,
)


def render_league() -> None:
    st.subheader("League")
    leagues = list_leagues()
    if not leagues:
        st.write("No league is loaded yet.")
        _create_form(show_cancel=False)
        return

    league = _select_open(leagues)
    st.write(summary(league))
    _edit_form(league)
    _remove_control(league)
    if st.button("New league"):
        st.session_state["creating_league"] = True
        st.session_state["create_generation"] = st.session_state.get("create_generation", 0) + 1
    if st.session_state.get("creating_league"):
        _create_form(show_cancel=True)


def _select_open(leagues: list[League]) -> League:
    labels = {league.id: league.settings.name for league in leagues}
    open_id = next(league.id for league in leagues if league.is_open)
    selected = st.selectbox(
        "Open league",
        [league.id for league in leagues],
        index=[league.id for league in leagues].index(open_id),
        format_func=lambda league_id: labels[league_id],
        key="open-league",
    )
    if selected != open_id:
        open_league(selected)
        st.session_state.pop("confirm_remove_id", None)
    return next(league for league in leagues if league.id == selected)


def _edit_form(league: League) -> None:
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


def _reset_league_widgets() -> None:
    st.session_state.pop("open-league", None)
    st.session_state["create_generation"] = st.session_state.get("create_generation", 0) + 1


def _create_form(*, show_cancel: bool) -> None:
    if show_cancel and st.button("Cancel new league"):
        st.session_state["creating_league"] = False
        st.rerun()
    generation = st.session_state.get("create_generation", 0)
    settings = _settings_form(
        prefix=f"create-{generation}",
        defaults=default_settings(),
        submit_label="Create league",
    )
    if settings is None:
        return
    errors = create_league(settings)
    if errors:
        for message in errors:
            st.error(message)
        return
    st.session_state["creating_league"] = False
    _reset_league_widgets()
    st.rerun()


def _remove_control(league: League) -> None:
    pending = st.session_state.get("confirm_remove_id")
    if pending not in (None, league.id):
        st.session_state.pop("confirm_remove_id", None)
        pending = None
    if pending == league.id:
        st.warning(
            f"Remove {league.settings.name}? The league's draft entries are removed with it. "
            "Imported players stay."
        )
        if st.button("Remove league"):
            remove_league(league.id)
            st.session_state.pop("confirm_remove_id", None)
            st.session_state["creating_league"] = False
            _reset_league_widgets()
            st.rerun()
        if st.button("Keep league"):
            st.session_state.pop("confirm_remove_id", None)
            st.rerun()
        return
    if st.button("Remove this league"):
        st.session_state["confirm_remove_id"] = league.id
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
        st.caption("Categories")
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
