"""
Twizzit "Beheer agenda" export, filtered on Wedstrijden.

No login/scraping needed: export the filtered agenda as CSV from Twizzit
(Beheer agenda > filter Wedstrijden > export) and save it as
data/twizzit_export.csv (or pass any path to load_twizzit_export()).
"""
import re

import pandas as pd

_MOJIBAKE_MARKERS = ("Ã", "â€")
_OFFICIALS_RE = re.compile(r"officials:\s*([^<]+)")


def _fix_mojibake(text):
    """Twizzit's export double-encodes accented characters (e.g. 'BelgiÃ«' for 'België')."""
    if not isinstance(text, str) or not any(m in text for m in _MOJIBAKE_MARKERS):
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def _parse_officials(omschrijving):
    if not isinstance(omschrijving, str):
        return []
    m = _OFFICIALS_RE.search(omschrijving)
    if not m:
        return []
    return [name.strip() for name in m.group(1).split(",") if name.strip()]


def _split_title(titel):
    """'<reeks>: <thuisploeg> - <tegenstander>' -> (reeks, thuisploeg, tegenstander)."""
    if not isinstance(titel, str) or ":" not in titel:
        return None, titel, None
    reeks, matchup = titel.split(":", 1)
    reeks = reeks.strip()
    if " - " in matchup:
        home, away = matchup.split(" - ", 1)
        return reeks, home.strip(), away.strip()
    return reeks, matchup.strip(), None


def load_twizzit_export(path_or_buffer, own_team_prefix: str = "BBC Haantjes ") -> pd.DataFrame:
    """`path_or_buffer` is a file path (local dev) or an uploaded file-like object."""
    df = pd.read_csv(path_or_buffer, sep=";", dtype=str)
    df = df[df["Activity subtype"] == "Competitiewedstrijd"].reset_index(drop=True)

    for col in ("Titel", "Omschrijving", "Groep", "Resource", "Resource address"):
        df[col] = df[col].apply(_fix_mojibake)

    split = df["Titel"].apply(_split_title)
    df["reeks"] = split.apply(lambda t: t[0])
    df["thuisploeg"] = split.apply(lambda t: t[1])
    df["tegenstander"] = split.apply(lambda t: t[2])

    officials = df["Omschrijving"].apply(_parse_officials)
    df["ref1"] = officials.apply(lambda o: o[0] if len(o) > 0 else "")
    df["ref2"] = officials.apply(lambda o: o[1] if len(o) > 1 else "")

    combined = df["Startdatum"].astype(str).str.strip() + " " + df["Start tijdstip"].astype(str).str.strip()
    df["DT"] = pd.to_datetime(combined, format="%d/%m/%y %H:%M", errors="coerce")

    df["isHome"] = df["thuisploeg"].astype(str).str.startswith(own_team_prefix)

    score = df["Score"].astype(str).str.lstrip("'").str.strip()
    scores_split = score.str.split(" - ", n=1, expand=True)
    df["scoreThuis"] = pd.to_numeric(scores_split[0], errors="coerce") if 0 in scores_split else None
    df["scoreUit"] = pd.to_numeric(scores_split[1], errors="coerce") if 1 in scores_split else None

    out = df.rename(
        columns={
            "Game id": "gameId",
            "Groep": "team",
            "Resource": "resource",
            "Resource address": "address",
        }
    )
    return out[
        [
            "gameId", "DT", "reeks", "team", "thuisploeg", "tegenstander",
            "isHome", "ref1", "ref2", "resource", "address", "scoreThuis", "scoreUit",
        ]
    ].sort_values("DT").reset_index(drop=True)


if __name__ == "__main__":
    df = load_twizzit_export("data/twizzit_export.csv")
    print(f"{len(df)} wedstrijden geladen uit Twizzit-export")
    print(df.head(10))
