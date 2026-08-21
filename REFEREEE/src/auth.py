"""
Shared login gate. Remembers the player's name + team(s) in the browser's
localStorage (via streamlit-local-storage) so they don't retype it every
visit — call login_gate(team_options) at the top of every page that needs
to know who's using the app. Stops the page and shows a login form if no
identity is known yet.
"""
import streamlit as st
from streamlit_local_storage import LocalStorage


def login_gate(team_options):
    """Returns (player_name, player_teams) once logged in; otherwise renders
    the login form and stops the page."""
    ls = LocalStorage(key="ref_app_storage")

    if "player_name" not in st.session_state:
        st.session_state["player_name"] = ls.getItem("ref_player_name") or ""
    if "player_teams" not in st.session_state:
        stored_teams = ls.getItem("ref_player_teams")
        st.session_state["player_teams"] = stored_teams.split(",") if stored_teams else []

    name = st.session_state["player_name"]
    teams = [t for t in st.session_state["player_teams"] if t in team_options]

    if name and teams:
        with st.sidebar:
            st.markdown(f"### 👤 {name}")
            st.caption(", ".join(teams))
            if st.button("🔓 Wissel van gebruiker", use_container_width=True):
                ls.deleteItem("ref_player_name", key="delete_ref_player_name")
                ls.deleteItem("ref_player_teams", key="delete_ref_player_teams")
                st.session_state["player_name"] = ""
                st.session_state["player_teams"] = []
                st.rerun()
        return name, teams

    # --- Login form ---
    st.markdown(
        """
        <div style="text-align:center; padding: 3rem 0 1.5rem 0;">
          <h1 style="margin-bottom:0; color:#10243e;">🏀 Haantjes Refereeing</h1>
          <p style="color:#666;">Log in om wedstrijden te bekijken en jezelf toe te wijzen als scheidsrechter</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            input_name = st.text_input("Jouw naam", value=name)
            input_teams = st.multiselect("Jouw team(en)", team_options, default=teams)
            submitted = st.form_submit_button("➡️ Inloggen", use_container_width=True, type="primary")

        if submitted:
            input_name = input_name.strip()
            if not input_name or not input_teams:
                st.error("Vul je naam in en kies minstens één team.")
            else:
                ls.setItem("ref_player_name", input_name, key="set_ref_player_name")
                ls.setItem("ref_player_teams", ",".join(input_teams), key="set_ref_player_teams")
                st.session_state["player_name"] = input_name
                st.session_state["player_teams"] = input_teams
                st.rerun()

    st.stop()
