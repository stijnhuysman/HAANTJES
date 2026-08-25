"""
Club roster (players + coaches -> team(s)) loaded from the "Jeugdrefs" tab of
the public REFCALENDAR SPELERS.xlsx workbook on GitHub — one row per person
per team, with its own Titel column ("Speler"/"Coach") as the role. Drives the
login dropdown (pick a real name instead of typing one) and the age-based
refereeing-eligibility rule: a person's OWN category is the highest-ranked
team they're on ("highest number wins"), and that category determines which
other categories' home games they're allowed to referee — except coaches,
who are eligible to referee any home match regardless of category (see
is_coach()).
"""
import re

import pandas as pd
import streamlit as st

ROSTER_URL = (
    "https://raw.githubusercontent.com/stijnhuysman/HAANTJES/main/"
    "REFEREEE/REFCALENDAR%20SPELERS.xlsx"
)

# Age ladder, highest to lowest. "SE" (senioren) has no numeric age and ranks above 21.
AGE_LADDER = ["SE", 21, 18, 16, 14, 12, 10]

# Which age tiers a player of a given own tier is allowed to referee.
# SE can ref everything below except the youngest (10). The youngest (10) is
# deliberately NOT bumped up to ref SE/21 games — instead given the same target
# tiers as the "16" rung (14, 12), so a 10-year-old refs games a couple of age
# groups up instead of adult senior games.
ELIGIBLE_TO_REF = {
    "SE": [21, 18, 16, 14, 12],
    21: [18, 16, 14, 12],
    18: [16, 14, 12, 10],
    16: [14, 12, 10],
    14: [12, 10],
    12: [10],
    10: [14, 12],
}

# Not a real age-based playing team — treated as the most senior/permissive tier.
_NON_AGE_TEAMS = {"Trainerspoule"}

_NUMERIC_RUNGS = [r for r in AGE_LADDER if isinstance(r, int)]


def parse_age(team_code: str):
    """'DSE A'/'HSE B' -> 'SE'; 'J21 A' -> 21; 'M19 A' -> 18 (snapped to nearest rung);
    'G08 A' (U8) -> None — younger than the youngest ref-eligible rung (U10), no
    referee needed for those games, so they're excluded rather than snapped."""
    if not isinstance(team_code, str) or not team_code.strip():
        return None
    if team_code in _NON_AGE_TEAMS:
        return "SE"
    if "SE" in team_code:
        return "SE"
    match = re.search(r"\d+", team_code)
    if not match:
        return None
    age = int(match.group())
    if age < min(_NUMERIC_RUNGS):
        return None
    return min(_NUMERIC_RUNGS, key=lambda r: abs(r - age))


def own_tier_from_teams(team_codes):
    """'Highest number wins' across every team a player belongs to."""
    tiers = [t for t in (parse_age(c) for c in team_codes) if t is not None]
    if not tiers:
        return None
    return min(tiers, key=AGE_LADDER.index)


def eligible_ref_tiers(own_tier):
    return ELIGIBLE_TO_REF.get(own_tier, [])


@st.cache_data(ttl=3600)
def load_roster() -> pd.DataFrame:
    """One row per (person, team): columns name, team, photo, ageTier, role
    ("Speler" or "Coach", straight from Jeugdrefs' own Titel column) — a
    person coaching one team and playing another just gets one row each;
    teams_for_player/own_tier_from_teams naturally combine them."""
    df = pd.read_excel(ROSTER_URL, sheet_name="Jeugdrefs", engine="openpyxl")
    df = df.rename(columns={"Naam": "name", "Profielfoto": "photo", "TEAM": "team", "Titel": "role"})
    df = df[["name", "photo", "team", "role"]]
    df = df.dropna(subset=["name", "team"])
    df["name"] = df["name"].astype(str).str.strip()
    df["team"] = df["team"].astype(str).str.strip()
    df["ageTier"] = df["team"].apply(parse_age)
    return df


def player_names(roster: pd.DataFrame):
    return sorted(roster["name"].dropna().unique())


def is_coach(roster: pd.DataFrame, name: str) -> bool:
    """Coaches ref-eligibility is unscoped: any home match, any age category —
    they're not restricted to ELIGIBLE_TO_REF like players are."""
    return bool((roster.loc[roster["name"] == name, "role"] == "Coach").any())


def teams_for_player(roster: pd.DataFrame, name: str):
    return sorted(roster.loc[roster["name"] == name, "team"].unique())


def photo_for_player(roster: pd.DataFrame, name: str):
    photos = roster.loc[roster["name"] == name, "photo"].dropna()
    return photos.iloc[0] if not photos.empty else None
