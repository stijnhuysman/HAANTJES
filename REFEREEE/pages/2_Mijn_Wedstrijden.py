"""
Player self-service: log in with your name + team, see your own matches,
and volunteer for open referee slots at home games (Rode Los).
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import assignments_store, data_loader, vbl_source
from src.crosscheck import cross_check_referees

load_dotenv()

st.set_page_config(page_title="Mijn wedstrijden", layout="wide")
st.title("🧑‍⚖️ Mijn wedstrijden")

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
    st.stop()

if calendar.empty:
    st.info("Geen data geladen.")
    st.stop()

# Resolve official referees (VBL has priority, Twizzit fills gaps) so we know
# which home games are genuinely still open.
twizzit, twizzit_error = data_loader.get_twizzit_calendar(TWIZZIT_CSV_PATH, OWN_TEAM_PREFIX)
if twizzit is not None and not twizzit.empty and not twizzit_error:
    cross = cross_check_referees(calendar, twizzit)
    official = cross[["wedguid", "refFinal1"]].rename(columns={"refFinal1": "officialRef"})
else:
    official = calendar[["wedguid", "ref1"]].rename(columns={"ref1": "officialRef"})

calendar = calendar.merge(official, on="wedguid", how="left")

st.subheader("Wie ben je?")
col1, col2 = st.columns(2)
player_name = col1.text_input("Jouw naam").strip()

team_options = sorted(calendar["ownTeamCode"].dropna().unique())
player_team = col2.selectbox("Jouw team", [""] + team_options)

if not player_name or not player_team:
    st.info("Vul je naam en team in om verder te gaan.")
    st.stop()

st.divider()

# --- Eigen wedstrijden: informational, so the player doesn't double-book ---
st.subheader(f"📅 Wanneer speelt {player_team} zelf?")
own_matches = calendar[calendar["ownTeamCode"] == player_team].sort_values("DT")
st.dataframe(
    own_matches[["DT", "thuisploeg", "tegenstander", "locatie", "isHome"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

# --- Open thuiswedstrijden: home games, not our own team, no official ref yet ---
st.subheader("🙋 Beschikbare thuiswedstrijden om als scheidsrechter toe te wijzen")

volunteers = assignments_store.get_assignments()

open_home = calendar[
    calendar["isHome"]
    & (calendar["ownTeamCode"] != player_team)
    & (calendar["officialRef"].fillna("") == "")
].sort_values("DT")

if volunteers.empty:
    claimed_by_others = set()
    my_claims = set()
else:
    claimed_by_others = set(volunteers.loc[volunteers["player_name"] != player_name, "match_key"])
    my_claims = set(volunteers.loc[volunteers["player_name"] == player_name, "match_key"])

open_home = open_home[~open_home["wedguid"].isin(claimed_by_others)].copy()
open_home["Ik doe deze"] = open_home["wedguid"].isin(my_claims)

if open_home.empty:
    st.info("Geen open thuiswedstrijden gevonden (buiten je eigen team) op dit moment.")
else:
    edited = st.data_editor(
        open_home[["Ik doe deze", "DT", "thuisploeg", "tegenstander", "reeks", "locatie", "wedguid"]],
        column_config={"wedguid": None},  # hide raw id, still present in the returned frame
        disabled=["DT", "thuisploeg", "tegenstander", "reeks", "locatie"],
        hide_index=True,
        use_container_width=True,
        key="open_home_editor",
    )

    if st.button("✅ Bevestig mijn keuzes"):
        before = my_claims
        after = set(edited.loc[edited["Ik doe deze"], "wedguid"])

        for match_key in after - before:
            assignments_store.assign(match_key, player_name, player_team)
        for match_key in before - after:
            assignments_store.unassign(match_key, player_name)

        st.success(f"Bijgewerkt: {len(after - before)} toegevoegd, {len(before - after)} verwijderd.")
        st.rerun()

st.divider()

st.subheader("✅ Mijn huidige toewijzingen")
mine = volunteers[volunteers["player_name"] == player_name] if not volunteers.empty else pd.DataFrame()
if mine.empty:
    st.caption("Nog geen wedstrijden toegewezen.")
else:
    mine_detail = calendar[calendar["wedguid"].isin(mine["match_key"])]
    st.dataframe(
        mine_detail[["DT", "thuisploeg", "tegenstander", "locatie"]].sort_values("DT"),
        use_container_width=True,
        hide_index=True,
    )
