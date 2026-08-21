"""
Weekend view — same matches and assignment rules as "Mijn wedstrijden", but shown
as zaterdag + zondag full-height time columns side by side (FullCalendar's
timeGridWeek with maandag-vrijdag hidden), so the match blocks are bigger and
easier to read than the compact list view.
"""
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv
from streamlit_calendar import calendar

from src import auth, match_view, roster, theme


def _current_or_next_weekend_anchor() -> str:
    """Any date inside the weekend to show on open: today itself if today is
    already zaterdag/zondag (lopend weekend), otherwise the upcoming zaterdag."""
    today = date.today()
    weekday = today.weekday()  # maandag=0 ... zondag=6
    if weekday >= 5:  # zaterdag(5) of zondag(6)
        return today.isoformat()
    days_until_saturday = 5 - weekday
    return (today + timedelta(days=days_until_saturday)).isoformat()

load_dotenv()

st.set_page_config(page_title="Weekends", layout="wide", page_icon="📆")
theme.inject_css()
theme.app_logo()
theme.inject_pwa()
theme.bottom_nav(current="weekends")

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

roster_df = roster.load_roster()
player_name, player_teams = auth.login_gate(roster_df, team_options)
theme.page_header("📆 Weekends", f"Ingelogd als {player_name} · {', '.join(player_teams)}")

kalender = match_view.build_kalender(calendar_df, player_teams)

st.caption(
    "🔵 eigen wedstrijd (info) · 🔴❗ nog geen ref · 🟠❗ nog 1 ref nodig · ⚪ volzet (2 refs) · "
    "**vet** = aangeduid door BVBL, *cursief* = clubref — "
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
        # bij het openen meteen het lopende (als vandaag za/zo is) of eerstkomende
        # weekend tonen, niet noodzakelijk "vandaag" zelf (zie firstDay-opmerking hieronder)
        "initialDate": _current_or_next_weekend_anchor(),
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
        "slotLabelFormat": {"hour": "numeric", "minute": "2-digit", "hour12": False},
        "allDaySlot": False,
        "nowIndicator": True,
        "eventDisplay": "block",
        "expandRows": True,
    },
    custom_css="""
        /* force the two day-columns to always share exactly the available width —
           no horizontal scrolling, ever, no matter how long an event's text is */
        .fc-scrollgrid, .fc-scrollgrid table { table-layout: fixed !important; width: 100% !important; }
        .fc-scroller { overflow: hidden !important; }
        .fc-view-harness { overflow: visible !important; }

        /* narrow time axis so the two day columns get almost all the width */
        .fc-timegrid-axis, .fc-timegrid-axis-frame { width: 30px !important; max-width: 30px !important; }
        .fc-timegrid-slot-label-cushion { font-size: 0.62em !important; padding: 0 1px !important; }

        .fc-timegrid-col { min-width: 0 !important; }
        .fc-timegrid-event .fc-event-title {
            font-size: 0.72em; font-weight: 600; white-space: pre-line; line-height: 1.25;
            overflow-wrap: anywhere; word-break: break-word;
        }
        .fc-timegrid-event .fc-event-time { font-size: 0.65em; overflow-wrap: anywhere; }
        .fc-timegrid-event { cursor: pointer; }
        .fc-col-header-cell-cushion { font-size: 0.85em; font-weight: 600; padding: 3px; overflow-wrap: anywhere; }
    """,
    key="ref_calendar_weekend",
)

weekend_clicked = weekend_cal_state.get("eventClick") if weekend_cal_state else None
if weekend_clicked:
    wedguid = weekend_clicked["event"]["id"]
    if st.session_state.get("_last_dialog_wedguid_weekend") != wedguid:
        st.session_state["_last_dialog_wedguid_weekend"] = wedguid
        match_dialog(wedguid)
