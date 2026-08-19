"""
Basketbal Vlaanderen (VBL) season schedule for one club.

Adapted from HAANTJES/REFKALENDER/Thuismatchen.ipynb — that notebook already
proved this works: the club's full season (all matches, both home and away,
including already-assigned referees where known) is available as plain JSON,
no login or browser automation required.
"""
import os
import re
import pandas as pd
import requests

VBL_MATCHES_URL = "https://vblcb.wisseq.eu/VBLCB_WebService/data/OrgMatchesByGuid?issguid={guid}"
OWN_CLUB_FULLNAME = "BBC Haantjes Certifisc Oudenaarde"


def fetch_season(club_guid: str) -> pd.DataFrame:
    """Fetch the full season schedule for a club GUID as a raw DataFrame."""
    url = VBL_MATCHES_URL.format(guid=club_guid)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    return pd.DataFrame(payload)


def _parse_datetime(season: pd.DataFrame) -> pd.DataFrame:
    begin_fixed = (
        season["beginTijd"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "00:00")
        .str.replace(".", ":", regex=False)
    )
    combined = season["datumString"].astype(str).str.strip() + " " + begin_fixed
    season["DT"] = pd.to_datetime(combined, dayfirst=True, errors="coerce")

    mask_nat = season["DT"].isna()
    if mask_nat.any():
        season.loc[mask_nat, "DT"] = pd.to_datetime(
            season.loc[mask_nat, "datumString"], dayfirst=True, errors="coerce"
        )
    return season.sort_values("DT").reset_index(drop=True)


def _parse_agegroup(team_name: str):
    if not isinstance(team_name, str):
        return team_name
    if "HSE" in team_name:
        return "Heren"
    if "DSE" in team_name:
        return "Dames"
    m = re.search(r"[GJM]\s?(\d{2})", team_name)
    if m:
        return int(m.group(1))
    return team_name


def _extract_own_team_code(thuisploeg, tegenstander, own_full_name=OWN_CLUB_FULLNAME):
    """'BBC Haantjes Certifisc Oudenaarde DSE A' -> 'DSE A'; None if neither side is us."""
    for name in (thuisploeg, tegenstander):
        if isinstance(name, str) and own_full_name in name:
            code = name.replace(own_full_name, "").strip()
            if code:
                return code
    return None


def get_club_calendar(club_guid: str, own_team_prefix: str) -> pd.DataFrame:
    """
    Full season calendar for the club, with referee names split out, an
    `isHome` flag (own_team_prefix matched against the home team name), and
    an `ownTeamCode` (e.g. "DSE A", "G12 B") for whichever side is our team.
    """
    season = fetch_season(club_guid)
    season = _parse_datetime(season)

    season["isHome"] = season["tTNaam"].astype(str).str.startswith(own_team_prefix)
    season["ref1"] = season["wedOff"].apply(
        lambda x: x[0] if isinstance(x, (list, tuple)) and len(x) > 0 else ""
    )
    season["ref2"] = season["wedOff"].apply(
        lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else ""
    )
    season["agegroup"] = season["tTNaam"].apply(_parse_agegroup)
    season["ownTeamCode"] = season.apply(
        lambda r: _extract_own_team_code(r["tTNaam"], r["tUNaam"]), axis=1
    )

    out = season.rename(
        columns={
            "tTNaam": "thuisploeg",
            "tUNaam": "tegenstander",
            "accNaam": "locatie",
            "pouleNaam": "reeks",
            "guid": "wedguid",
        }
    )
    return out[
        [
            "wedguid",
            "DT",
            "thuisploeg",
            "tegenstander",
            "locatie",
            "reeks",
            "agegroup",
            "ownTeamCode",
            "isHome",
            "ref1",
            "ref2",
            "uitslag",
        ]
    ]


def get_home_matches(club_guid: str, own_team_prefix: str) -> pd.DataFrame:
    """Only the matches played at home by any team of the club."""
    calendar = get_club_calendar(club_guid, own_team_prefix)
    return calendar[calendar["isHome"]].reset_index(drop=True)


if __name__ == "__main__":
    guid = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
    prefix = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
    df = get_home_matches(guid, prefix)
    print(f"{len(df)} thuiswedstrijden gevonden voor {prefix.strip()}")
    print(df.head(10))
