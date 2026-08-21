"""
Player self-service: log in with your name + team(s), see your own matches and
open referee slots as a scrollable list of info cards (grouped by day), tap a
card to see full details, and assign/unassign yourself as referee for open ones.

A match needs exactly 2 referees (any mix of official VBL/Twizzit refs and
volunteers). Once 2 names are attached, the match is no longer choosable —
you can still see who's assigned, you just can't add a 3rd.

Cards instead of a FullCalendar list view: on a narrow phone (iPhone SE et al.)
FullCalendar's list rows force horizontal scrolling once the text is long enough
(team names + location + ref names). Plain vertical Streamlit content never
needs horizontal scrolling, so cards are the more reliably mobile-friendly choice
here — the "Weekends" page keeps the real calendar, since a side-by-side
Saturday/Sunday view actually needs a grid.
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import auth, match_view, roster, theme

load_dotenv()

st.set_page_config(page_title="Mijn wedstrijden", layout="wide", page_icon="🧑‍⚖️")
theme.inject_css()
theme.app_logo()
theme.inject_pwa()
theme.bottom_nav(current="wedstrijden")

CLUB_GUID = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
OWN_TEAM_PREFIX = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
TWIZZIT_CSV_PATH = os.environ.get("TWIZZIT_CSV_PATH", "data/twizzit_export.csv")

st.markdown(
    """
    <style>
    div[class*="st-key-card_"] { margin-bottom: 0.5rem; }
    div[class*="st-key-card_"] .stButton { margin-top: -0.6rem; }
    div[class*="st-key-card_"] .stButton > button {
        border-radius: 0 0 12px 12px !important;
        background-color: #f0f3f7 !important;
        color: #10243e !important;
        border: none !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        box-shadow: none !important;
        min-height: 2.1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
theme.page_header("🧑‍⚖️ Mijn wedstrijden", f"Ingelogd als {player_name} · {', '.join(player_teams)}")

kalender = match_view.build_kalender(calendar_df, player_teams)

st.subheader("📅 Mijn kalender")
st.caption(
    "🔵 eigen wedstrijd (info) · 🔴❗ nog geen ref · 🟠❗ nog 1 ref nodig · ⚪ volzet (2 refs) · "
    "**vet** = aangeduid door BVBL, *cursief* = clubref — tik op een wedstrijd voor details. "
    "Liever enkel zaterdag/zondag, groter en overzichtelijker? Ga naar **📆 Weekend** onderaan."
)

if kalender.empty:
    st.info("Geen wedstrijden gevonden voor deze selectie.")
    st.stop()

volunteers, volunteers_by_match = match_view.get_volunteers_by_match()
match_dialog = match_view.make_match_dialog(kalender, volunteers_by_match, player_name, player_teams)

for _, day_matches in kalender.groupby(kalender["DT"].dt.date):
    day_matches = day_matches.sort_values("DT")
    st.markdown(
        f'<div style="font-weight:700; color:#10243e; margin:1rem 0 0.4rem 0; '
        f'font-size:0.95rem; text-transform:capitalize;">{match_view.day_label(day_matches.iloc[0]["DT"])}</div>',
        unsafe_allow_html=True,
    )
    for _, row in day_matches.iterrows():
        status = match_view.match_status(row, volunteers_by_match, player_name)
        entries = match_view.assigned_entries(
            volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource")
        )
        with st.container(key=f"card_{row['wedguid']}"):
            st.markdown(
                f"""
                <div style="background:white; border-left:5px solid {status['color']}; border-radius:12px 12px 0 0;
                            padding:0.7rem 0.85rem 0.6rem 0.75rem; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem;">
                    <span style="font-weight:700; color:#10243e; font-size:0.92rem;">{row['thuisploeg']} - {row['tegenstander']}</span>
                    {match_view.status_badge_html(status)}
                  </div>
                  <div style="color:#666; font-size:0.8rem; margin-top:0.35rem;">
                    🕐 {row['DT'].strftime('%H:%M')} · 📍 {row['locatie']} · 🏆 {row['reeks']}
                  </div>
                  <div style="margin-top:0.45rem; font-size:0.84rem;">{match_view.ref_line_html(entries)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("👉 Bekijk / kies", key=f"open_{row['wedguid']}", use_container_width=True):
                match_dialog(row["wedguid"])

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
