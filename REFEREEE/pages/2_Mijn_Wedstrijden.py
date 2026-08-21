"""
Player self-service: log in with your name + team(s), see a real calendar view
combining your own matches and open referee slots, click a match to see
details, and assign/unassign yourself as referee for open ones.

A match needs exactly 2 referees (any mix of official VBL/Twizzit refs and
volunteers). Once 2 names are attached, the match is no longer choosable —
you can still see who's assigned, you just can't add a 3rd.

For a more readable weekend-only view, see the "Weekends" page in the sidebar.
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_calendar import calendar

from src import auth, match_view, theme

load_dotenv()

st.set_page_config(page_title="Mijn wedstrijden", layout="wide", page_icon="🧑‍⚖️")
theme.inject_css()

CLUB_GUID = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
OWN_TEAM_PREFIX = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
TWIZZIT_CSV_PATH = os.environ.get("TWIZZIT_CSV_PATH", "data/twizzit_export.csv")

try:
    calendar_df, team_options = match_view.load_context(CLUB_GUID, OWN_TEAM_PREFIX, TWIZZIT_CSV_PATH)
except Exception as e:
    st.error(f"Kon Basketbal Vlaanderen kalender niet ophalen: {e}")
    st.stop()

if calendar_df.empty:
    st.info("Geen data geladen.")
    st.stop()

player_name, player_teams = auth.login_gate(team_options)
theme.page_header("🧑‍⚖️ Mijn wedstrijden", f"Ingelogd als {player_name} · {', '.join(player_teams)}")

kalender = match_view.build_kalender(calendar_df, player_teams)

st.subheader("📅 Mijn kalender")
st.caption(
    "🔵 eigen wedstrijd (info) · 🟢 nog een plaats vrij · 🟠 door jou toegewezen · ⚪ volzet (2 refs) — "
    "klik op een wedstrijd voor details. Liever enkel zaterdag/zondag, groter en overzichtelijker? "
    "Ga naar **📆 Weekends** in de zijbalk."
)

if kalender.empty:
    st.info("Geen wedstrijden gevonden voor deze selectie.")
    st.stop()

volunteers, volunteers_by_match = match_view.get_volunteers_by_match()
events = match_view.build_events(kalender, volunteers_by_match, player_name)
match_dialog = match_view.make_match_dialog(kalender, volunteers_by_match, player_name, player_teams)

cal_state = calendar(
    events=events,
    options={
        "initialView": "listMonth",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "listWeek,listMonth,dayGridMonth"},
        "height": 650,
        "eventDisplay": "block",
    },
    custom_css="""
        .fc-list-event-title, .fc-list-event-time { font-size: 0.85em; }
        .fc-list-day-cushion { font-size: 0.9em; padding: 4px 8px; }
        .fc-list-event:hover td { cursor: pointer; background-color: #f0f0f0; }
    """,
    key="ref_calendar",
)

clicked = cal_state.get("eventClick") if cal_state else None
if clicked:
    wedguid = clicked["event"]["id"]
    # only pop the dialog open for a genuinely NEW click — otherwise it would
    # reopen on every unrelated rerun, since the component keeps returning the
    # last click it saw even after you've closed the dialog
    if st.session_state.get("_last_dialog_wedguid") != wedguid:
        st.session_state["_last_dialog_wedguid"] = wedguid
        match_dialog(wedguid)

st.divider()

st.subheader("✅ Mijn huidige toewijzingen")
mine = volunteers[volunteers["player_name"] == player_name] if not volunteers.empty else pd.DataFrame()
if mine.empty:
    st.caption("Nog geen wedstrijden toegewezen.")
else:
    mine_detail = calendar_df[calendar_df["wedguid"].isin(mine["match_key"])]
    st.dataframe(
        mine_detail[["DT", "thuisploeg", "tegenstander", "locatie"]].sort_values("DT"),
        use_container_width=True,
        hide_index=True,
    )
