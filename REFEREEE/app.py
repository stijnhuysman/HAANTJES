"""
Haantjes Refereeing — single consolidated player app.

Header: club logo + player name + team chips (one row). Below that, 3 tabs:
  - Wedstrijdlijst: cards for the matches that actually matter to this player —
    their own team's games, plus other teams' home games they're old/senior
    enough to referee (younger age categories).
  - Komende weekends: a real calendar, zaterdag + zondag side by side.
  - Mijn toewijzingen: the matches where this player is assigned as referee.

Logging in as "admin" (password-gated, see auth.ADMIN_NAME) bypasses all of that
scoping and shows every home match across every team instead.

Run with: streamlit run app.py
"""
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_calendar import calendar

from src import auth, match_view, roster, theme

load_dotenv()

st.set_page_config(page_title="Haantjes Refereeing", layout="wide", page_icon="🏀")
theme.inject_css()
theme.inject_pwa()

CLUB_GUID = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
OWN_TEAM_PREFIX = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
TWIZZIT_CSV_PATH = os.environ.get("TWIZZIT_CSV_PATH", "data/twizzit_export.csv")

# card styling — shared by the Wedstrijdlijst and Mijn toewijzingen tabs
st.markdown(
    """
    <style>
    div[class*="st-key-card_"] { margin-bottom: 0.5rem; position: relative; }

    /* status badge ("volzet"/"nog 1 nodig"/...) — top-right corner, inside the card */
    .match-card-badge { position: absolute; top: 10px; right: 10px; }

    /* the "Kies" button sits right underneath the badge, in that same corner —
       not a full-width bar attached to the card anymore */
    div[class*="st-key-open_"] {
        position: absolute !important; top: 42px; right: 10px; z-index: 5; width: auto !important;
    }
    div[class*="st-key-open_"] .stButton { margin: 0 !important; }
    div[class*="st-key-open_"] .stButton > button {
        width: auto !important; min-height: 1.9rem !important; padding: 0.25rem 0.7rem !important;
        border-radius: 999px !important;
        background-color: #f0f3f7 !important; color: #10243e !important;
        border: none !important; font-size: 0.75rem !important; font-weight: 600 !important;
        box-shadow: none !important;
    }

    /* "Wissel" (logout) right-aligned next to the name, vertically centered on
       the header row, instead of a full-width button on its own line */
    .st-key-header_row { position: relative; }
    div[class*="st-key-logout_btn"] {
        position: absolute !important; top: 50%; right: 0; transform: translateY(-50%);
        z-index: 5; width: auto !important;
    }
    div[class*="st-key-logout_btn"] .stButton > button {
        width: auto !important; min-height: 1.9rem !important; padding: 0.3rem 0.8rem !important;
        font-size: 0.78rem !important; font-weight: 600 !important;
        border-radius: 999px !important;
        background-color: #f0f3f7 !important; color: #10243e !important; border: none !important;
        box-shadow: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    with st.spinner("Wedstrijden laden..."):
        calendar_df, team_options = match_view.load_context(CLUB_GUID, OWN_TEAM_PREFIX, TWIZZIT_CSV_PATH)
        roster_df = roster.load_roster()
except Exception as e:
    st.error(f"Kon de wedstrijd- of spelersgegevens niet ophalen: {e}")
    st.stop()

if calendar_df.empty:
    st.info("Geen data geladen.")
    st.stop()

player_name, player_teams = auth.login_gate(roster_df, team_options)
is_admin_user = player_name == auth.ADMIN_NAME

with st.container(key="header_row"):
    theme.header_bar(player_name, ["Alle thuiswedstrijden"] if is_admin_user else player_teams)
    auth.logout_button()

if is_admin_user:
    # admin sees every home match, across all teams — no age/eligibility scoping
    kalender = calendar_df[calendar_df["isHome"]].copy()
    kalender["Type"] = "Beschikbaar"
else:
    kalender = match_view.build_kalender(calendar_df, player_teams)

# toekomstige wedstrijden — vanaf vandaag (op datum, niet tijdstip, zodat een
# wedstrijd die vandaag al bezig/voorbij is nog zichtbaar blijft, en het volledige
# lopende weekend nooit halverwege wordt afgekapt)
kalender = kalender[kalender["DT"].dt.date >= date.today()]

volunteers, volunteers_by_match = match_view.get_volunteers_by_match()
match_dialog = match_view.make_match_dialog(kalender, volunteers_by_match, player_name, player_teams)

tab_list, tab_weekend, tab_mine = st.tabs(["📋 Lijst", "📆 Weekend", "✅ Toewijzingen"])

with tab_list:
    st.markdown(match_view.legend_html(), unsafe_allow_html=True)
    if kalender.empty:
        st.info("Geen wedstrijden gevonden voor deze selectie.")
    else:
        match_view.render_match_cards(kalender, volunteers_by_match, player_name, match_dialog, key_prefix="list_")

with tab_weekend:
    # known Streamlit quirk: a custom component (the calendar) inside a non-default
    # st.tabs() tab mounts while its panel is still display:none, so its own
    # Streamlit.setFrameHeight() call measures 0 and gets stuck there forever —
    # force the iframe's real height from the outside, overriding that
    st.markdown(
        """
        <style>
        div[class*="st-key-ref_calendar_weekend"] iframe { height: 700px !important; min-height: 700px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(match_view.legend_html(), unsafe_allow_html=True)
    st.caption("zaterdag en zondag naast elkaar · tik op een wedstrijd voor details")
    if kalender.empty:
        st.info("Geen wedstrijden gevonden voor deze selectie.")
    else:
        events = match_view.build_events(kalender, volunteers_by_match, player_name)

        def _current_or_next_weekend_anchor() -> str:
            """Today itself if today is already zaterdag/zondag (lopend weekend),
            otherwise the upcoming zaterdag."""
            today = date.today()
            weekday = today.weekday()  # maandag=0 ... zondag=6
            if weekday >= 5:
                return today.isoformat()
            return (today + timedelta(days=5 - weekday)).isoformat()

        weekend_cal_state = calendar(
            events=events,
            options={
                "initialView": "timeGridWeek",
                "initialDate": _current_or_next_weekend_anchor(),
                # week laten starten op zaterdag, zodat za + de zondag erna samen in 1
                # rij staan (met firstDay=0 hoort een zondag bij de zaterdag 6 dagen LATER)
                "firstDay": 6,
                "hiddenDays": [1, 2, 3, 4, 5],
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
                "height": 700,
                "slotMinTime": "08:00:00",
                "slotMaxTime": "23:00:00",
                "slotLabelFormat": {"hour": "numeric", "minute": "2-digit", "hour12": False},
                "allDaySlot": False,
                "nowIndicator": True,
                "eventDisplay": "block",
                "expandRows": True,
            },
            custom_css="""
                /* force the two day-columns to always share exactly the available
                   width — no horizontal scrolling, ever, no matter how long an
                   event's text is */
                .fc-scrollgrid, .fc-scrollgrid table { table-layout: fixed !important; width: 100% !important; }
                /* kill horizontal scroll (that's the overflow bug), but keep vertical
                   scroll — 08:00-23:00 is 15 hours, taller than the 700px calendar
                   height, so a visible scrollbar here is needed to reach every hour */
                .fc-scroller { overflow-x: hidden !important; overflow-y: auto !important; }
                .fc-scroller::-webkit-scrollbar { width: 6px; }
                .fc-scroller::-webkit-scrollbar-thumb { background: #c7d0dc; border-radius: 3px; }
                .fc-view-harness { overflow: visible !important; }
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

with tab_mine:
    mine = volunteers[volunteers["player_name"] == player_name] if not volunteers.empty else pd.DataFrame()
    if mine.empty:
        st.caption("Nog geen wedstrijden toegewezen.")
    else:
        mine_matches = calendar_df[calendar_df["wedguid"].isin(mine["match_key"])].copy()
        mine_matches["Type"] = "Beschikbaar"  # reuse the status-color machinery (never "Mijn wedstrijd")
        mine_dialog = match_view.make_match_dialog(mine_matches, volunteers_by_match, player_name, player_teams)
        match_view.render_match_cards(mine_matches, volunteers_by_match, player_name, mine_dialog, key_prefix="mine_")
