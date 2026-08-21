"""
REFEREEE — admin calendar (step 1 of the referee-assignment app).

Two sources, one calendar:
  - Basketbal Vlaanderen: full season for the club, incl. already-known
    referee assignments (working now, no login needed).
  - Twizzit: the team's own agenda, filtered to "Wedstrijden" — exported
    manually as CSV (Beheer agenda > Wedstrijden > export), no login needed.

Run with: streamlit run app.py
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import auth, data_loader, theme, vbl_source
from src.crosscheck import cross_check_referees

load_dotenv()

st.set_page_config(page_title="Haantjes — Refereeing kalender", layout="wide", page_icon="🏀")
theme.inject_css()

CLUB_GUID = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
OWN_TEAM_PREFIX = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
TWIZZIT_CSV_PATH = os.environ.get("TWIZZIT_CSV_PATH", "data/twizzit_export.csv")


@st.cache_data(ttl=900)
def load_vbl_calendar(club_guid: str, own_team_prefix: str) -> pd.DataFrame:
    return vbl_source.get_club_calendar(club_guid, own_team_prefix)


try:
    calendar = load_vbl_calendar(CLUB_GUID, OWN_TEAM_PREFIX)
except Exception as e:
    st.error(f"Kon Basketbal Vlaanderen kalender niet ophalen: {e}")
    calendar = pd.DataFrame()

team_options = sorted(calendar["ownTeamCode"].dropna().unique()) if not calendar.empty else []
player_name, player_teams = auth.login_gate(team_options)

with st.sidebar:
    st.header("Filters")
    if st.button("🔄 Ververs data"):
        load_vbl_calendar.clear()
        st.session_state.pop("twizzit_df", None)

theme.page_header("🏀 Haantjes — Refereeing kalender", f"Ingelogd als {player_name}")

twizzit, twizzit_error = data_loader.get_twizzit_calendar(TWIZZIT_CSV_PATH, OWN_TEAM_PREFIX)
if twizzit is None:
    twizzit = pd.DataFrame()

tab_own, tab_home, tab_twizzit, tab_cross = st.tabs(
    [
        "📅 Eigen team (alle wedstrijden)",
        "🏠 Thuiswedstrijden (alle teams)",
        "🔗 Twizzit export",
        "🔍 Cross-check (VBL vs Twizzit)",
    ]
)

with tab_own:
    st.caption("Alle wedstrijden (thuis + uit) van elk Haantjes-team, via Basketbal Vlaanderen.")
    if not calendar.empty:
        age_options = sorted(calendar["agegroup"].dropna().astype(str).unique())
        chosen_ages = st.multiselect("Leeftijdscategorie / team", age_options, default=age_options)
        filtered = calendar[calendar["agegroup"].astype(str).isin(chosen_ages)]
        st.dataframe(
            filtered.sort_values("DT")[
                ["DT", "thuisploeg", "tegenstander", "locatie", "reeks", "isHome", "ref1", "ref2", "uitslag"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Geen data geladen.")

with tab_home:
    st.caption("Enkel de wedstrijden die in onze eigen zaal gespeeld worden.")
    if not calendar.empty:
        home = calendar[calendar["isHome"]].sort_values("DT")
        st.dataframe(
            home[["DT", "thuisploeg", "tegenstander", "locatie", "reeks", "ref1", "ref2", "uitslag"]],
            use_container_width=True,
            hide_index=True,
        )
        missing_refs = home[(home["ref1"] == "") & (home["ref2"] == "")]
        st.metric("Thuiswedstrijden zonder toegewezen scheidsrechter", len(missing_refs))
    else:
        st.info("Geen data geladen.")

with tab_twizzit:
    st.caption("Wedstrijden zoals geëxporteerd uit Twizzit (Beheer agenda > Wedstrijden).")
    if twizzit_error:
        st.error(f"Kon Twizzit-export niet inlezen: {twizzit_error}")
    elif twizzit.empty:
        st.warning(
            f"Nog geen bestand gevonden op `{TWIZZIT_CSV_PATH}` en nog niets geüpload. "
            "Exporteer in Twizzit onder Beheer agenda > filter Wedstrijden, en upload dat "
            "CSV-bestand via de knop bovenaan de pagina."
        )
    else:
        team_options = sorted(twizzit["team"].dropna().unique())
        chosen_teams = st.multiselect("Team", team_options, default=team_options)
        filtered_tw = twizzit[twizzit["team"].isin(chosen_teams)]
        st.dataframe(
            filtered_tw[
                ["DT", "team", "thuisploeg", "tegenstander", "isHome", "ref1", "ref2", "resource", "scoreThuis", "scoreUit"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        home_tw = filtered_tw[filtered_tw["isHome"]]
        missing_refs_tw = home_tw[(home_tw["ref1"] == "") & (home_tw["ref2"] == "")]
        st.metric("Thuiswedstrijden zonder toegewezen scheidsrechter (Twizzit)", len(missing_refs_tw))

with tab_cross:
    st.caption(
        "Vergelijkt scheidsrechter-toewijzingen tussen beide bronnen, gematched op datum/tijd + thuisploeg. "
        "Basketbal Vlaanderen heeft voorrang; Twizzit vult enkel aan waar VBL nog niets heeft."
    )
    if calendar.empty or twizzit.empty:
        st.info("Beide bronnen moeten geladen zijn om te kunnen cross-checken.")
    else:
        cross = cross_check_referees(calendar, twizzit)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Bron: VBL", int((cross["refSource"] == "VBL").sum()))
        col2.metric("Bron: Twizzit (aangevuld)", int((cross["refSource"] == "Twizzit").sum()))
        col3.metric("Nog geen ref", int((cross["refSource"] == "geen").sum()))
        col4.metric("⚠️ Mismatches", int(cross["refMismatch"].sum()))

        show_only_mismatch = st.checkbox("Toon enkel mismatches", value=False)
        display = cross[cross["refMismatch"]] if show_only_mismatch else cross

        st.dataframe(
            display[
                [
                    "DT", "thuisploeg", "tegenstander", "isHome",
                    "vbl_ref1", "vbl_ref2", "tw_ref1", "tw_ref2",
                    "refFinal1", "refFinal2", "refSource", "refMismatch",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
