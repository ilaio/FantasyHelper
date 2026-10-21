"""Teams tab: named teams and which player is on which team."""

import html

import streamlit as st

from fantasyhelper.leagues.league import League
from fantasyhelper.leagues.teams import (
    UNASSIGNED,
    Team,
    add_team,
    clear_team_player,
    list_team_players,
    list_teams,
    place_team_player,
    rename_team,
)
from fantasyhelper.stats.store import load_baseline_rows
from fantasyhelper.ui.prices import mirror_punt_switches, show_placement_table
from fantasyhelper.valuation.prices import PriceRow, build_price_table, with_personal_prices
from fantasyhelper.valuation.projection import lines_from_rows


def render_teams(league: League) -> None:
    settings = league.settings
    players, seasons, projections = load_baseline_rows()
    table = build_price_table(
        lines_from_rows(players, seasons, projections),
        settings.categories,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    names = {int(player["id"]): str(player["name"]) for player in players}
    punted: frozenset[str] = frozenset()
    if table.error:
        st.error(table.error)
    elif table.rows:
        punted = mirror_punt_switches(league.id, settings.categories)
    else:
        st.write("No players are in the projection yet.")
    _add_team(league.id)
    if table.error:
        _rename_only(league.id)
        return
    display = with_personal_prices(
        table.rows,
        punted,
        settings.team_count,
        settings.budget,
        settings.roster_size,
    )
    message = st.session_state.get(_move_error_key(league.id), "")
    if message:
        st.error(message)
    _lists(league.id, display, names, settings.categories)


def _apply_team_choice(
    editor_key: str,
    league_id: int,
    player_ids: tuple[int, ...],
    teams: tuple[tuple[str, int], ...],
) -> None:
    """Write the Team cells changed in this editor. One change moves one player."""
    state = st.session_state[editor_key]
    by_name = dict(teams)
    messages: list[str] = []
    for index, changes in state["edited_rows"].items():
        if "Team" not in changes or index >= len(player_ids):
            continue
        choice = changes["Team"]
        player_id = player_ids[index]
        if choice == UNASSIGNED:
            clear_team_player(league_id, player_id)
            continue
        team_id = by_name.get(choice)
        if team_id is None:
            messages.append("That team is no longer available.")
            continue
        messages.extend(place_team_player(league_id, player_id, team_id))
    st.session_state[_move_error_key(league_id)] = messages[0] if messages else ""


def _add_team(league_id: int) -> None:
    clear_key = f"team-clear-{league_id}"
    name_key = f"new-team-{league_id}"
    if st.session_state.pop(clear_key, False):
        st.session_state[name_key] = ""
    with st.container(horizontal=True, vertical_alignment="bottom", gap="small", wrap=False):
        st.text_input("Team name", key=name_key, width=280)
        submitted = st.button("Add team", key=f"add-team-{league_id}")
    if not submitted:
        return
    errors = add_team(league_id, str(st.session_state.get(name_key, "")))
    if errors:
        for message in errors:
            st.error(message)
        return
    st.session_state[clear_key] = True
    st.rerun()


def _rename_only(league_id: int) -> None:
    for team in list_teams(league_id):
        _team_name(league_id, team)


def _lists(
    league_id: int,
    rows: tuple[PriceRow, ...],
    names: dict[int, str],
    active: frozenset[str],
) -> None:
    teams = list_teams(league_id)
    placed = {item.player_id: item.team_id for item in list_team_players(league_id)}
    known = {row.player_id for row in rows}
    by_team: dict[int, list[int]] = {}
    for player_id, team_id in placed.items():
        if player_id not in known:
            by_team.setdefault(team_id, []).append(player_id)
    destinations = (UNASSIGNED, *(team.name for team in teams))
    team_pairs = tuple((team.name, team.id) for team in teams)
    _list_title("Players")
    unassigned = tuple(row for row in rows if row.player_id not in placed)
    _placement(
        league_id,
        f"teams-players-{league_id}",
        unassigned,
        tuple(UNASSIGNED for _row in unassigned),
        (),
        destinations,
        team_pairs,
        active,
    )
    for team in teams:
        _team_name(league_id, team)
        members = tuple(row for row in rows if placed.get(row.player_id) == team.id)
        extras = tuple(
            sorted(
                by_team.get(team.id, ()),
                key=lambda player_id: names.get(player_id, "").casefold(),
            )
        )
        blanks = tuple((names.get(player_id, "Unknown player"), team.name) for player_id in extras)
        _placement(
            league_id,
            f"teams-roster-{league_id}-{team.id}",
            members,
            tuple(team.name for _row in members),
            blanks,
            destinations,
            team_pairs,
            active,
            extra_ids=extras,
        )


def _placement(
    league_id: int,
    editor_key: str,
    rows: tuple[PriceRow, ...],
    labels: tuple[str, ...],
    blanks: tuple[tuple[str, str], ...],
    destinations: tuple[str, ...],
    team_pairs: tuple[tuple[str, int], ...],
    active: frozenset[str],
    extra_ids: tuple[int, ...] = (),
) -> None:
    player_ids = tuple(row.player_id for row in rows) + extra_ids
    show_placement_table(
        rows,
        labels,
        active,
        destinations,
        key=editor_key,
        on_change=_apply_team_choice,
        args=(editor_key, league_id, player_ids, team_pairs),
        blanks=blanks,
    )


def _team_name(league_id: int, team: Team) -> None:
    key = f"team-name-{league_id}-{team.id}"
    message_key = f"team-name-error-{league_id}-{team.id}"
    if key not in st.session_state:
        st.session_state[key] = team.name
    st.text_input(
        "Team name",
        key=key,
        width=280,
        on_change=_commit_name,
        args=(league_id, team.id, key, team.name),
    )
    message = st.session_state.get(message_key, "")
    if message:
        st.error(message)


def _commit_name(league_id: int, team_id: int, key: str, previous: str) -> None:
    message_key = f"team-name-error-{league_id}-{team_id}"
    errors = rename_team(league_id, team_id, str(st.session_state.get(key, "")))
    if errors:
        st.session_state[key] = previous
        st.session_state[message_key] = errors[0]
        return
    stored = next(
        (team.name for team in list_teams(league_id) if team.id == team_id),
        previous,
    )
    st.session_state[key] = stored
    st.session_state[message_key] = ""


def _move_error_key(league_id: int) -> str:
    return f"teams-move-error-{league_id}"


def _list_title(title: str) -> None:
    st.markdown(
        f"<p class='list-title'>{html.escape(title)}</p>",
        unsafe_allow_html=True,
    )
