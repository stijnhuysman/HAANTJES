"""
Shared login gate. The player picks their real name from the club roster (the
"Jeugdrefs" tab) instead of typing free text — a simple 2-step control: first a
name-picker (styled like a button/pill), which turns into a single "Inloggen"
button once a name is chosen. Only the chosen name is remembered in the
browser's localStorage so it doesn't have to be repicked every visit. Call
login_gate(roster, team_options) once at the top of the app — team_options is
the set of team codes that actually appear in this season's VBL calendar, so
roster teams with no matches (e.g. mid-season changes) get dropped rather than
crash the page. Stops the page and shows the login form if no identity is
known yet. Once logged in, the app's own header_bar (see theme.py) is what
actually displays name/teams/logo — this module only owns identity + the
small "switch user" control.
"""
import os
from pathlib import Path

import streamlit as st
from streamlit_local_storage import LocalStorage

from src import roster as roster_mod
from src.match_view import ADMIN_NAME, DEFAULT_ADMIN_PASSWORD

_LOGO_PATH = Path(__file__).resolve().parent.parent / "logo_haantjes.jpg"


def login_gate(roster, team_options):
    """Returns (player_name, player_teams) once logged in; otherwise renders
    the login form and stops the page. player_name == ADMIN_NAME ("admin") is a
    special password-gated pseudo-user with player_teams == [] — app.py
    special-cases that to show every home match across all teams, and
    make_match_dialog (match_view.py) unlocks a "remove any assignment"
    control for it, instead of just your own."""
    ls = LocalStorage(key="ref_app_storage")

    if "player_name" not in st.session_state:
        st.session_state["player_name"] = ls.getItem("ref_player_name") or ""
    if "login_picked_name" not in st.session_state:
        st.session_state["login_picked_name"] = None

    name = st.session_state["player_name"]
    all_names = roster_mod.player_names(roster)

    if name == ADMIN_NAME:
        return ADMIN_NAME, []

    if name and name in all_names:
        teams = [t for t in roster_mod.teams_for_player(roster, name) if t in team_options]
        # a coach doesn't need their own team to have matches — they're eligible
        # to referee every other team's home matches regardless (see match_view's
        # all_games bypass), so an empty teams list shouldn't block login
        if teams or roster_mod.is_coach(roster, name):
            return name, teams

    # --- Login screen: centered card, like a mobile app's welcome/login page ---
    st.markdown(
        """
        <style>
        .st-key-login_card {
            max-width: 440px;
            margin: 1.5rem auto;
            background: white;
            border-radius: 22px;
            box-shadow: 0 8px 28px rgba(16, 36, 62, 0.12);
            padding: 2rem 1.75rem 1.75rem 1.75rem;
        }
        @media (max-width: 640px) {
            .st-key-login_card { margin: 0.5rem auto; padding: 1.5rem 1.1rem; border-radius: 18px; }
        }
        /* name-picker styled to look like a rounded button/pill, not a form field */
        .st-key-login_card div[data-baseweb="select"] > div {
            border-radius: 999px !important;
            border: 2px solid #1f77b4 !important;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="login_card"):
        if _LOGO_PATH.exists():
            st.image(str(_LOGO_PATH), width=88)
        st.markdown(
            """
            <h2 style="margin: 0.6rem 0 0.15rem 0; color:#10243e;">Welkom terug 👋</h2>
            <p style="color:#777; margin: 0 0 1.1rem 0; font-size: 0.95rem;">
                Tik je naam in om wedstrijden te bekijken en jezelf toe te wijzen als scheidsrechter
            </p>
            """,
            unsafe_allow_html=True,
        )

        picked = st.session_state["login_picked_name"]

        if picked is None:
            # step 1: just the name-picker, nothing else (roster names + admin)
            input_name = st.selectbox(
                "Jouw naam",
                options=all_names + [ADMIN_NAME],
                index=None,
                placeholder="Tik je voornaam in...",
                label_visibility="collapsed",
                key="login_name_select",
            )
            if input_name:
                st.session_state["login_picked_name"] = input_name
                st.rerun()
        elif picked == ADMIN_NAME:
            # admin: password-gated instead of the normal team-eligibility check
            pw = st.text_input("Admin wachtwoord", type="password", key="login_admin_pw")
            if st.button("🔓 Inloggen als admin", use_container_width=True, type="primary"):
                admin_password = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
                if pw == admin_password:
                    ls.setItem("ref_player_name", ADMIN_NAME, key="set_ref_player_name")
                    st.session_state["player_name"] = ADMIN_NAME
                    st.session_state["login_picked_name"] = None
                    st.rerun()
                else:
                    st.error("Fout wachtwoord.")
            if st.button("⬅️ Andere naam", key="login_pick_again"):
                st.session_state["login_picked_name"] = None
                st.rerun()
        else:
            # step 2: the picker is replaced by a single "Inloggen" button —
            # only a warning appears if this player currently has no matches.
            # Coaches are exempt: they're eligible to referee every other
            # team's home matches regardless of whether their own team has
            # any games right now, so an empty preview shouldn't block them.
            preview_teams = [t for t in roster_mod.teams_for_player(roster, picked) if t in team_options]
            is_coach_pick = roster_mod.is_coach(roster, picked)
            if not preview_teams and not is_coach_pick:
                st.warning(f"Voor {picked}'s team(en) zijn momenteel geen wedstrijden gevonden.")
            elif st.button(f"➡️ Inloggen als {picked}", use_container_width=True, type="primary"):
                ls.setItem("ref_player_name", picked, key="set_ref_player_name")
                st.session_state["player_name"] = picked
                st.session_state["login_picked_name"] = None
                st.rerun()
            if st.button("⬅️ Andere naam", key="login_pick_again"):
                st.session_state["login_picked_name"] = None
                st.rerun()

    st.stop()


def logout_button():
    """Small "switch user" control — call this right after theme.header_bar(),
    both wrapped in the same st.container(key="header_row") in app.py, so CSS
    can right-align this next to the name instead of it being a full-width
    button on its own line."""
    ls = LocalStorage(key="ref_app_storage")
    if st.button("🔓 Wissel", key="logout_btn"):
        ls.deleteItem("ref_player_name", key="delete_ref_player_name")
        st.session_state["player_name"] = ""
        st.rerun()
