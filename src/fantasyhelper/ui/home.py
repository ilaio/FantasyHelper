"""Home screen shown before a league exists."""

import streamlit as st


def render() -> None:
    st.title("FantasyHelper")
    st.write("No league is loaded yet.")
