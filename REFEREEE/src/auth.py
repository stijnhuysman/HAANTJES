"""
Shared login gate. The player picks their real name from the club roster (the
"Jeugdrefs" tab) instead of typing free text — their team(s) are derived
automatically and shown immediately on selection, in a small profile-preview
card (photo + name + team chips), like a real mobile app's login screen. Only
the chosen name is remembered in the browser's localStorage so it doesn't have
to be repicked every visit. Call login_gate(roster, team_options) at the top
of every page that needs to know who's using the app — team_options is the
set of team codes that actually appear in this season's VBL calendar, so
roster teams with no matches (e.g. mid-season changes) get dropped rather
than crash the page. Stops the page and shows the login form if no identity
is known yet.
"""
from pathlib import Path

import streamlit as st
from streamlit_local_storage import LocalStorage

from src import roster as roster_mod

_LOGO_PATH = Path(__file__).resolve().parent.parent / "logo_haantjes.jpg"


def _avatar_html(photo_url: str | None, size: int = 64) -> str:
    if photo_url:
        return (
            f'<img src="{photo_url}" style="width:{size}px;height:{size}px;border-radius:50%;'
            f'object-fit:cover;border:3px solid #1f77b4;display:block;" />'
        )
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#e8edf3;'
        f'display:flex;align-items:center;justify-content:center;font-size:{size * 0.45}px;">🙂</div>'
    )


def _team_chips_html(teams) -> str:
    if not teams:
        return '<span style="color:#c0392b;font-size:0.82rem;">Geen wedstrijden gevonden voor je team(en)</span>'
    return "".join(
        f'<span style="display:inline-block;background:#eef4fb;color:#1f77b4;border-radius:999px;'
        f'padding:0.2rem 0.7rem;font-size:0.78rem;font-weight:600;margin:0.15rem 0.3rem 0 0;">{t}</span>'
        for t in teams
    )


def login_gate(roster, team_options):
    """Returns (player_name, player_teams) once logged in; otherwise renders
    the login form and stops the page."""
    ls = LocalStorage(key="ref_app_storage")

    if "player_name" not in st.session_state:
        st.session_state["player_name"] = ls.getItem("ref_player_name") or ""

    name = st.session_state["player_name"]
    all_names = roster_mod.player_names(roster)

    if name and name in all_names:
        teams = [t for t in roster_mod.teams_for_player(roster, name) if t in team_options]
        if teams:
            # no sidebar in this app (mobile-only layout) — profile bar lives inline
            # at the top of the page instead
            photo = roster_mod.photo_for_player(roster, name)
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:0.7rem; background:white;
                            border-radius:14px; padding:0.6rem 0.9rem; margin-bottom:0.75rem;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                    {_avatar_html(photo, size=44)}
                    <div style="flex:1;">
                        <div style="font-weight:700; color:#10243e;">{name}</div>
                        <div style="margin-top:0.15rem;">{_team_chips_html(teams)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("🔓 Wissel van gebruiker", use_container_width=True):
                ls.deleteItem("ref_player_name", key="delete_ref_player_name")
                st.session_state["player_name"] = ""
                st.rerun()
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
                Kies je naam om wedstrijden te bekijken en jezelf toe te wijzen als scheidsrechter
            </p>
            """,
            unsafe_allow_html=True,
        )

        input_name = st.selectbox(
            "Jouw naam",
            options=all_names,
            index=None,
            placeholder="🔍 Zoek je naam...",
            label_visibility="collapsed",
            key="login_name_select",
        )

        preview_teams = []
        if input_name:
            photo = roster_mod.photo_for_player(roster, input_name)
            preview_teams = [t for t in roster_mod.teams_for_player(roster, input_name) if t in team_options]
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:0.85rem; background:#f7f9fb;
                            border-radius:16px; padding:0.8rem 1rem; margin: 0.9rem 0 1.1rem 0;">
                    {_avatar_html(photo)}
                    <div>
                        <div style="font-weight:700; color:#10243e; font-size:1.02rem;">{input_name}</div>
                        <div style="margin-top:0.25rem;">{_team_chips_html(preview_teams)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button(
            "➡️ Inloggen",
            use_container_width=True,
            type="primary",
            disabled=not preview_teams,
        ):
            ls.setItem("ref_player_name", input_name, key="set_ref_player_name")
            st.session_state["player_name"] = input_name
            st.rerun()

    st.stop()
