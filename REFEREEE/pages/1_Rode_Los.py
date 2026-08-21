"""Rode Los — home games only (isHome), with official + volunteer referees."""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import assignments_store, auth, data_loader, roster, theme, vbl_source
from src.crosscheck import cross_check_referees

load_dotenv()

st.set_page_config(page_title="Rode Los — thuiswedstrijden", layout="wide", page_icon="🏟️")
theme.inject_css()
theme.app_logo()
theme.inject_pwa()
theme.bottom_nav(current="rode_los")

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

if calendar.empty:
    st.info("Geen data geladen.")
    st.stop()

team_options = sorted(calendar["ownTeamCode"].dropna().unique())
roster_df = roster.load_roster()
player_name, player_teams = auth.login_gate(roster_df, team_options)

theme.page_header("🏟️ Rode Los — thuiswedstrijden", f"Ingelogd als {player_name}")

home = calendar[calendar["isHome"]].copy()

twizzit, twizzit_error = data_loader.get_twizzit_calendar(TWIZZIT_CSV_PATH, OWN_TEAM_PREFIX)
if twizzit_error:
    st.warning(f"Kon Twizzit niet meenemen in cross-check: {twizzit_error}")
    home["refFinal1"], home["refFinal2"], home["refSource"] = home["ref1"], home["ref2"], "VBL"
elif twizzit is not None and not twizzit.empty:
    cross = cross_check_referees(calendar, twizzit)
    home = home.merge(
        cross[["wedguid", "refFinal1", "refFinal2", "refSource"]],
        on="wedguid",
        how="left",
    )
else:
    home["refFinal1"], home["refFinal2"], home["refSource"] = home["ref1"], home["ref2"], "VBL"

volunteers = assignments_store.get_assignments()
if not volunteers.empty:
    vol_by_match = volunteers.groupby("match_key")["player_name"].apply(list).to_dict()
else:
    vol_by_match = {}
home["vrijwilligers"] = home["wedguid"].map(lambda k: ", ".join(vol_by_match.get(k, [])))

age_options = sorted(home["agegroup"].dropna().astype(str).unique())
chosen_ages = st.multiselect("Leeftijdscategorie / team", age_options, default=age_options)
filtered = home[home["agegroup"].astype(str).isin(chosen_ages)].sort_values("DT")

st.dataframe(
    filtered[
        ["DT", "thuisploeg", "tegenstander", "reeks", "refFinal1", "refFinal2", "refSource", "vrijwilligers"]
    ],
    use_container_width=True,
    hide_index=True,
)

missing = filtered[(filtered["refFinal1"] == "") & (filtered["vrijwilligers"] == "")]
st.metric("Thuiswedstrijden zonder ref (officieel of vrijwilliger)", len(missing))
