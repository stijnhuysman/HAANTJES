"""
Weekend view — same matches and assignment rules as "Mijn wedstrijden", but shown
as zaterdag + zondag full-height time columns side by side (FullCalendar's
timeGridWeek with maandag-vrijdag hidden), so the match blocks are bigger and
easier to read than the compact list view.
"""
import os

import streamlit as st
from dotenv import load_dotenv
from streamlit_calendar import calendar

from src import auth, match_view, theme

load_dotenv()

st.set_page_config(page_title="Weekends", layout="wide", page_icon="📆")
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
theme.page_header("📆 Weekends", f"Ingelogd als {player_name} · {', '.join(player_teams)}")

kalender = match_view.build_kalender(calendar_df, player_teams)

st.caption(
    "🔵 eigen wedstrijd (info) · 🟢 nog een plaats vrij · 🟠 door jou toegewezen · ⚪ volzet (2 refs) — "
    "zaterdag en zondag naast elkaar, klik op een wedstrijd voor details."
)

if kalender.empty:
    st.info("Geen wedstrijden gevonden voor deze selectie.")
    st.stop()

volunteers, volunteers_by_match = match_view.get_volunteers_by_match()
events = match_view.build_events(kalender, volunteers_by_match, player_name)
match_dialog = match_view.make_match_dialog(kalender, volunteers_by_match, player_name, player_teams)

weekend_cal_state = calendar(
    events=events,
    options={
        "initialView": "timeGridWeek",
        # week laten starten op zaterdag, zodat za + de zondag erna samen in 1 rij staan
        # (met de standaard firstDay=0 hoort een zondag bij de zaterdag 6 dagen LATER,
        # niet bij de zaterdag van datzelfde weekend)
        "firstDay": 6,
        # FullCalendar dagnummering: 0=zo, 1=ma ... 6=za -> verberg ma t/m vr, za komt
        # zo als eerste kolom (links), zo als tweede (rechts)
        "hiddenDays": [1, 2, 3, 4, 5],
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "height": 750,
        "slotMinTime": "08:00:00",
        "slotMaxTime": "23:00:00",
        "allDaySlot": False,
        "nowIndicator": True,
        "eventDisplay": "block",
    },
    custom_css="""
        .fc-timegrid-event .fc-event-title { font-size: 0.9em; font-weight: 600; white-space: normal; }
        .fc-timegrid-event .fc-event-time { font-size: 0.85em; }
        .fc-timegrid-event { cursor: pointer; }
        .fc-col-header-cell-cushion { font-size: 1.05em; font-weight: 600; padding: 6px; }
    """,
    key="ref_calendar_weekend",
)

weekend_clicked = weekend_cal_state.get("eventClick") if weekend_cal_state else None
if weekend_clicked:
    wedguid = weekend_clicked["event"]["id"]
    if st.session_state.get("_last_dialog_wedguid_weekend") != wedguid:
        st.session_state["_last_dialog_wedguid_weekend"] = wedguid
        match_dialog(wedguid)
