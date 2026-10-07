"""
Shared match-calendar building blocks used by both the "Mijn wedstrijden" (list)
page and the "Weekends" (timegrid) page, so the two stay in sync — same colors,
same assignment rules, same detail dialog — without duplicating the logic.
"""
import os
from datetime import timedelta

import pandas as pd
import streamlit as st

from src import assignments_store, data_loader, roster, textstyle, vbl_store, vbl_sync
from src.crosscheck import cross_check_referees
from src.vbl_source import OWN_CLUB_FULLNAME, _extract_own_team_code, _parse_agegroup

# Fallback admin password (checked in auth.py's login screen), used only when
# the ADMIN_PASSWORD env var isn't set. This repo is public on GitHub — anyone
# can read this literal value from the source. Set ADMIN_PASSWORD in .env
# locally and in the Streamlit Cloud app's Secrets for the real deployment, so
# the password that actually protects the live app is never committed anywhere.
DEFAULT_ADMIN_PASSWORD = "Haantjes9700"
ADMIN_NAME = "admin"

# Second admin login (ADMIN_PASSWORD_2, same public-fallback caveat as above): the
# same admin view and powers, except that adding a referee is a pick from the
# players the ref hierarchy allows for that match and who are free at that time
# (see ref_options) — no free-text name. A separate pseudo-user rather than a
# flag on "admin", so it can't be turned into full admin by clearing a flag.
DEFAULT_ADMIN_HIERARCHY_PASSWORD = "1111"
ADMIN_HIERARCHY_NAME = "admin-hiërarchie"


def is_admin_name(name) -> bool:
    return name in (ADMIN_NAME, ADMIN_HIERARCHY_NAME)

# Board members: same all-matches view as admin (no age/eligibility scoping),
# but strictly read-only — no self-assign, no adding someone else, no removing
# anyone's assignment. No password gate: unlike admin it can't change anything.
BESTUUR_NAME = "Bestuur"

# Generic pseudo-user for volunteer refs with no personal roster entry: same
# all-matches view as admin/Bestuur (no age/eligibility scoping), and can add
# themselves as a referee — but since "player_name" here is the literal string
# "Extern" rather than a real name, the normal self-assign button (which would
# record "Extern" itself as the ref) is hidden; they type their real name into
# the existing "add someone else" field instead. No password gate.
EXTERN_NAME = "Extern"

REQUIRED_REFS = 2

COLOR_OWN = "#1f77b4"     # blue — your own team's match, informational only
COLOR_NONE = "#d62728"    # red — nog geen ref toegewezen
COLOR_PARTIAL = "#ff7f0e" # orange — nog 1 ref nodig
COLOR_FULL = "#888888"    # grey — volzet (2 refs), no longer choosable
COLOR_BBVL_WAIT = "#9467bd"  # purple — U14+, still reserved for BVBL's own assignment

STATUS_LABELS = {
    "🔵": "Eigen wedstrijd",
    "🔴": "Nog geen ref",
    "🟠": "Nog 1 nodig",
    "⚪": "Volzet",
    "🟣": "wss toewijzing door BBVL",
}

# U14 and every category above it (U16, U18, U21, Senioren): Basketbal Vlaanderen
# is expected to assign its own official referee for these first. Club
# self-assignment for these categories only opens on the Tuesday before the
# match — and only if BVBL hasn't filled it in by then.
BBVL_PRIORITY_TIERS = {14, 16, 18, 21, "SE"}

# Club self-assignment opens from the last occurrence of this weekday strictly
# before the match (Monday=0, so Tuesday=1), at this hour.
BBVL_OPEN_WEEKDAY = 1
BBVL_OPEN_HOUR = 0
_TIER_LABELS = {14: "U14", 16: "U16", 18: "U18", 21: "U21", "SE": "Senioren"}

# Specific team codes (exact ownTeamCode match, e.g. "J16 B") that never wait on
# BVBL regardless of tier — some B-teams are known to not get an official
# assigned by Basketbal Vlaanderen, so the club self-assigns from day one for
# them. Club-configurable via BBVL_EXCLUDED_TEAMS in .env / Streamlit Secrets
# (comma-separated), no code change needed to add/remove a team.
BBVL_EXCLUDED_TEAMS = {
    code.strip().upper()
    for code in os.environ.get("BBVL_EXCLUDED_TEAMS", "J16 B,J18 B").split(",")
    if code.strip()
}


def _bbvl_open_cutoff(dt: pd.Timestamp) -> pd.Timestamp:
    """00:00 of the Tuesday before the match — the latest Tuesday strictly before the
    match's own day, so a Tuesday match opens a week earlier, not on the day itself."""
    days_since_open_day = (dt.weekday() - BBVL_OPEN_WEEKDAY) % 7 or 7
    return dt.normalize() - pd.Timedelta(days=days_since_open_day) + pd.Timedelta(hours=BBVL_OPEN_HOUR)


def bbvl_priority_info(row):
    """None for categories below U14, for friendlies (OEFEN) regardless of
    category — BVBL only assigns officials to real competition matches, never
    to a practice match, so those stay in the normal red/orange/grey situation —
    and for any team code listed in BBVL_EXCLUDED_TEAMS (e.g. "J16 B"), which
    never waits on BVBL regardless of tier. Otherwise a dict with the tier
    label, the Tuesday-before-the-match cutoff for this specific match, and
    whether that cutoff has passed yet — used to show the "toewijzing verwacht via
    BVBL" note and to gate self-assignment until then."""
    if "OEFEN" in str(row.get("reeks", "")).upper():
        return None
    own_team_code = str(row.get("ownTeamCode", "") or "").strip().upper()
    if own_team_code in BBVL_EXCLUDED_TEAMS:
        return None
    tier = roster.parse_age(row.get("ownTeamCode"))
    if tier not in BBVL_PRIORITY_TIERS:
        return None
    cutoff = _bbvl_open_cutoff(row["DT"])
    return {"tier": tier, "label": _TIER_LABELS.get(tier, str(tier)), "cutoff": cutoff, "is_open": pd.Timestamp.now() >= cutoff}



_NL_WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def day_label(dt) -> str:
    """'zaterdag 22/08', without relying on server locale for Dutch weekday names."""
    return f"{_NL_WEEKDAYS[dt.weekday()]} {dt.strftime('%d/%m')}"


def status_badge_html(status) -> str:
    label = STATUS_LABELS.get(status["icon"], "")
    return (
        f'<span style="background:{status["color"]}22; color:{status["color"]}; font-weight:700; '
        f'font-size:0.72rem; padding:0.2rem 0.6rem; border-radius:999px; white-space:nowrap;">'
        f'{status["icon"]} {label}</span>'
    )


def legend_html() -> str:
    """Compact 2-line legend (status colors, then bold/italic meaning) — each
    icon+label is kept on one line (white-space:nowrap) while the row itself
    wraps, so it never breaks a phrase mid-way like a plain st.caption would."""

    def _item(text: str) -> str:
        return f'<span style="white-space:nowrap; margin-right:0.7rem;">{text}</span>'

    line1 = "".join(
        _item(t) for t in ["🔵 eigen wedstrijd", "🔴 nog geen ref", "🟠 nog 1 nodig", "⚪ volzet", "🟣 wss BBVL"]
    )
    line2 = "".join(_item(t) for t in ["<b>vet</b> = BVBL", "<i>cursief</i> = clubref"])
    return (
        '<div style="font-size:0.78rem; color:#666; line-height:1.7; margin-bottom:0.6rem;">'
        f'<div style="display:flex; flex-wrap:wrap;">{line1}</div>'
        f'<div style="display:flex; flex-wrap:wrap;">{line2}</div>'
        "</div>"
    )


def ref_line_html(entries) -> str:
    """Real <b>/<i> tags (not the Unicode trick build_events uses) — this is meant
    for st.markdown/raw HTML contexts, which render actual HTML, unlike FullCalendar
    event titles which only ever show plain text."""
    if not entries:
        return '<span style="color:#999;">Nog niemand toegewezen</span>'
    parts = [f"<b>{e['name']}</b>" if e["vbl"] else f"<i>{e['name']}</i>" for e in entries]
    return "🧑‍⚖️ " + ", ".join(parts)


@st.cache_data(ttl=900)
def load_vbl_calendar() -> pd.DataFrame:
    """Reads the daily-synced VBL snapshot (src/vbl_store.py, refreshed by
    sync_vbl.py) rather than hitting the live VBL API on every page load — VBL
    is the only source allowed to overwrite referee assignments in this app,
    so that snapshot, not a per-request fetch, is what's authoritative here.

    ensure_fresh() first updates the DB from Basketbal Vlaanderen if that
    snapshot is missing or over a day old, so the app can't end up serving an
    empty or stale calendar when the daily job didn't run. Normally the job has
    already done it and this is a single MAX(synced_at) query."""
    vbl_sync.ensure_fresh()
    return vbl_store.load_calendar()


def load_vbl_only():
    """Returns (calendar_df, team_options) from VBL alone — no Twizzit involved, so
    this can run before login (team_options is needed by the login screen itself)
    without ever touching the Twizzit upload widget. G08 (U8) matches are dropped
    here — no referee is needed at that age, so they're excluded from the whole
    app rather than just from ref-eligibility (own_tier_from_teams already treats
    them as unreffable via roster.parse_age, but that alone still let admin/coach/
    Extern/Bestuur see and assign them via the all_games bypass)."""
    calendar_df = load_vbl_calendar()
    if calendar_df.empty:
        return calendar_df, []
    calendar_df = calendar_df[~calendar_df["ownTeamCode"].str.contains("G08", na=False)]
    team_options = sorted(calendar_df["ownTeamCode"].dropna().unique())
    return calendar_df, team_options


def _twizzit_only_matches(calendar_df: pd.DataFrame, twizzit: pd.DataFrame) -> pd.DataFrame:
    """Club-internal friendlies (Oefenwedstrijd) — matches where BOTH sides are
    one of our own teams. VBL only tracks official competition matches against
    external opponents, so these never appear there; restricting to
    both-sides-own-club (rather than "any Twizzit row with no VBL match") avoids
    ever synthesizing a duplicate of a real VBL fixture that's just spelled
    slightly differently between the two sources — seen in practice, VBL's
    "Basket Midwest BP Tielt" vs Twizzit's "Basket Midwest Izegem" for what's
    actually the same away match. Synthesized into calendar-shaped rows, with a
    stable synthetic wedguid derived from Twizzit's own gameId (or DT+thuisploeg
    when that's blank), so they render and get assigned like a VBL match."""
    both_own = twizzit["thuisploeg"].str.contains(OWN_CLUB_FULLNAME, na=False) & twizzit[
        "tegenstander"
    ].str.contains(OWN_CLUB_FULLNAME, na=False)
    vbl_keys = set(zip(calendar_df["DT"], calendar_df["thuisploeg"]))
    only = twizzit[both_own & ~twizzit.apply(lambda r: (r["DT"], r["thuisploeg"]) in vbl_keys, axis=1)].copy()
    if only.empty:
        return only

    only["wedguid"] = "twz-" + only["gameId"].fillna(
        only["DT"].astype(str) + "|" + only["thuisploeg"]
    ).astype(str)
    only["locatie"] = only["resource"]
    only["ownTeamCode"] = only.apply(
        lambda r: _extract_own_team_code(r["thuisploeg"], r["tegenstander"]), axis=1
    )
    only["agegroup"] = only["ownTeamCode"].apply(_parse_agegroup)
    only["uitslag"] = None
    only["refFinal1"] = only["ref1"]
    only["refFinal2"] = only["ref2"]
    only["refSource"] = "Twizzit"

    return only[
        [
            "wedguid", "DT", "thuisploeg", "tegenstander", "locatie", "reeks", "agegroup",
            "ownTeamCode", "isHome", "ref1", "ref2", "uitslag", "refFinal1", "refFinal2", "refSource",
        ]
    ]


def merge_twizzit(calendar_df: pd.DataFrame, twizzit_csv_path: str, own_team_prefix: str, allow_upload: bool):
    """Merges cross-checked official referee columns (refFinal1/refFinal2/refSource)
    into calendar_df, and appends Twizzit-only matches (friendlies VBL never tracks)
    as extra rows of their own. allow_upload gates the Twizzit file_uploader
    fallback — only True for the admin login, per the club's request that regular
    players never see/trigger that upload control."""
    twizzit, twizzit_error = data_loader.get_twizzit_calendar(twizzit_csv_path, own_team_prefix, allow_upload)
    if twizzit is not None and not twizzit.empty and not twizzit_error:
        cross = cross_check_referees(calendar_df, twizzit)
        official = cross[["wedguid", "refFinal1", "refFinal2", "refSource"]].dropna(subset=["wedguid"])
        merged = calendar_df.merge(official, on="wedguid", how="left")
        extra = _twizzit_only_matches(calendar_df, twizzit)
        return pd.concat([merged, extra], ignore_index=True) if not extra.empty else merged
    else:
        # no Twizzit to cross-check against -> ref1/ref2 here are VBL's own fields, so
        # any name present was, by definition, aangeduid door Basketbal Vlaanderen
        official = calendar_df[["wedguid", "ref1", "ref2"]].rename(
            columns={"ref1": "refFinal1", "ref2": "refFinal2"}
        )
        official["refSource"] = "VBL"
        return calendar_df.merge(official, on="wedguid", how="left")


def build_kalender(calendar_df: pd.DataFrame, player_teams, all_games: bool = False) -> pd.DataFrame:
    """Own team's matches (info only) + other teams' home matches the player is
    old/senior enough to referee, per the club's age-eligibility rule (own tier ->
    ELIGIBLE_TO_REF[own tier], see src/roster.py). all_games=True (coaches) skips
    that age-eligibility check entirely — every other team's home match is fair
    game, regardless of category."""
    own_matches = calendar_df[calendar_df["ownTeamCode"].isin(player_teams)].copy()
    own_matches["Type"] = "Mijn wedstrijd"

    if all_games:
        eligible_mask = True
    else:
        own_tier = roster.own_tier_from_teams(player_teams)
        eligible_tiers = roster.eligible_ref_tiers(own_tier)
        eligible_mask = calendar_df["ownTeamCode"].apply(roster.parse_age).isin(eligible_tiers)

    other_home = calendar_df[
        calendar_df["isHome"] & (~calendar_df["ownTeamCode"].isin(player_teams)) & eligible_mask
    ].copy()
    other_home["Type"] = "Beschikbaar"

    return pd.concat([own_matches, other_home], ignore_index=True).sort_values("DT")


def potential_ref_teams(roster_df: pd.DataFrame) -> set:
    """Every team with at least one member who could referee somewhere — coaches/
    "Extern" (all games), or players whose own tier has eligible target tiers."""
    teams = set()
    for name, person in roster_df.groupby("name"):
        person_teams = list(person["team"])
        if roster.has_all_games_access(roster_df, name) or roster.eligible_ref_tiers(
            roster.own_tier_from_teams(person_teams)
        ):
            teams.update(person_teams)
    return teams


def build_club_overview(calendar_df: pd.DataFrame, roster_df: pd.DataFrame) -> pd.DataFrame:
    """Admin's full club overview: every home match (the ones needing a ref), plus
    every away match of a team a potential ref plays for — so it's visible when
    those refs are themselves away and can't be assigned. Away matches reuse the
    "Mijn wedstrijd" type: blue, informational only, no assign controls."""
    home = calendar_df[calendar_df["isHome"]].copy()
    home["Type"] = "Beschikbaar"
    away = calendar_df[
        ~calendar_df["isHome"] & calendar_df["ownTeamCode"].isin(potential_ref_teams(roster_df))
    ].copy()
    away["Type"] = "Mijn wedstrijd"
    return pd.concat([home, away], ignore_index=True).sort_values("DT")


AGE_RANK = {tier: i for i, tier in enumerate(roster.AGE_LADDER)}


def _team_sort_key(team: str):
    """Seniors first, then U21 down to U10 — the roster's own age ladder; teams with
    no age (Extern, ...) last."""
    return (AGE_RANK.get(roster.parse_age(team), len(AGE_RANK)), team)


def player_booking_counts(roster_df: pd.DataFrame, volunteers: pd.DataFrame, calendar_df: pd.DataFrame, today=None) -> pd.DataFrame:
    """One row per (team, person) of the roster, with how many matches that person
    is booked in for as club ref: `booked` = every assignment on record, `upcoming`
    = those whose match is today or later. Counted per person, so someone on two
    teams has the same numbers on both rows. Only club assignments count —
    referees assigned by BVBL itself aren't in the assignments table. Names are
    matched case-insensitively, since admins can type a name freely."""
    today = today or pd.Timestamp.now().date()
    key = lambda s: s.astype(str).str.strip().str.casefold()

    if volunteers.empty:
        counts = pd.DataFrame(columns=["nameKey", "booked", "upcoming"])
    else:
        match_date = calendar_df.drop_duplicates("wedguid").set_index("wedguid")["DT"]
        booked = volunteers[["match_key", "player_name"]].copy()
        booked["nameKey"] = key(booked["player_name"])
        booked = booked.drop_duplicates(["match_key", "nameKey"])
        booked["upcoming"] = booked["match_key"].map(match_date).map(lambda dt: pd.notna(dt) and dt.date() >= today)
        counts = (booked.groupby("nameKey")
                        .agg(booked=("match_key", "count"), upcoming=("upcoming", "sum")).reset_index())

    people = roster_df[["name", "team", "role"]].drop_duplicates().copy()
    people["nameKey"] = key(people["name"])
    out = people.merge(counts, on="nameKey", how="left").drop(columns="nameKey")
    out[["booked", "upcoming"]] = out[["booked", "upcoming"]].fillna(0).astype(int)
    out["teamOrder"] = out["team"].map(_team_sort_key)
    return out.sort_values(["teamOrder", "booked", "name"]).drop(columns="teamOrder").reset_index(drop=True)


def whatsapp_team_text(team: str, rows: pd.DataFrame, today=None) -> str:
    """WhatsApp-formatted message for one team (*bold* header, one bullet per
    person with their booked-match count), ready to paste or forward."""
    today = today or pd.Timestamp.now().date()
    lines = [f"*{team}* — geboekte wedstrijden als scheids (stand {today.strftime('%d/%m/%Y')})"]
    lines += [f"• {r['name']} — {r['booked']}" for _, r in rows.iterrows()]
    return "\n".join(lines)


# Admin filters on the plain number of assigned refs — deliberately independent of
# the purple "wss BBVL" state, which hides a match's real 0/1/2 count until the
# BVBL cutoff. None = no ref-count filter; "away" = only the away matches.
REF_COUNT_FILTERS = {
    "Alles": None,
    "🔴 Geen ref": 0,
    "🟠 1 ref": 1,
    "⚪ Volzet": REQUIRED_REFS,
}
AWAY_FILTER_LABEL = "🔵 Uitwedstrijden"


# Admin "Club overzicht" category filter: label -> ownTeamCode prefixes (e.g. "HSE"
# covers HSE A/B/C). None = every category. Categories not listed in any group
# (e.g. G10, G12, M12, M14) only show under "Alle categorieën".
CATEGORY_FILTERS = {
    "Alle categorieën": None,
    "Dames/Heren": ("HSE", "DSE"),
    "J18/M19/J21": ("J18", "M19", "J21"),
    "J16/M16/G14": ("J16", "M16", "G14"),
}


def filter_category(matches: pd.DataFrame, option: str) -> pd.DataFrame:
    prefixes = CATEGORY_FILTERS.get(option)
    if prefixes is None or matches.empty:
        return matches
    codes = matches["ownTeamCode"].fillna("").str.strip().str.upper()
    return matches[codes.str.startswith(prefixes)]


# --- Admin "Opties" tab: which teams/players could referee a match ---------------

MATCH_DURATION = pd.Timedelta(hours=1, minutes=30)
# A player's own match blocks them from refereeing when the two overlap. An own
# home match only blocks its own time slot; an own away match also blocks the
# travel time on either side of it.
HOME_CONFLICT_WINDOW = MATCH_DURATION
AWAY_CONFLICT_WINDOW = pd.Timedelta(hours=3)

# Age tiers never offered as referee options on the Opties tab: U10/U12 players
# (e.g. G10, G12, M12) are too young to be proposed as ref, even where the ref
# hierarchy itself would allow them. Their own matches are still listed.
OPTIES_EXCLUDED_REF_TIERS = (10, 12)


def needs_club_refs(row, volunteers_by_match) -> bool:
    """True when a match still needs club referees: Basketbal Vlaanderen hasn't
    aangeduid any ref for it, and it has fewer than REQUIRED_REFS club refs
    (Twizzit-only officials and volunteers — everything not VBL-sourced)."""
    entries = assigned_entries(volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource"))
    if any(e["vbl"] for e in entries):
        return False
    return len(entries) < REQUIRED_REFS


def upcoming_weekend(today) -> tuple:
    """(zaterdag, zondag) of the lopend weekend when today is already zaterdag/
    zondag, otherwise of the next one."""
    weekday = today.weekday()  # maandag=0 ... zondag=6
    saturday = today - timedelta(days=weekday - 5) if weekday >= 5 else today + timedelta(days=5 - weekday)
    return saturday, saturday + timedelta(days=1)


def _conflicts(own_match, dt) -> bool:
    window = HOME_CONFLICT_WINDOW if own_match["isHome"] else AWAY_CONFLICT_WINDOW
    return abs(own_match["DT"] - dt) < window


def ref_options(
    match, weekend_matches: pd.DataFrame, roster_df: pd.DataFrame, volunteers_by_match, excluded_tiers=()
) -> list:
    """Candidate referees for one match, grouped per team and ordered
    hierarchically — the team closest in age above the match first, seniors last.

    A player is a candidate when their own tier may referee this match's tier
    (roster.ELIGIBLE_TO_REF), they don't play in the match's own team, none of
    their teams has a match that overlaps it (see _conflicts), and they aren't
    already assigned to another overlapping match. Each player is listed under
    their highest playing team — the one that sets their own tier. Pure coaches
    (no playing team) are left out: they can referee anything, so they'd show
    up under every match. Players whose own tier is in excluded_tiers are left
    out too (see OPTIES_EXCLUDED_REF_TIERS)."""
    match_tier = roster.parse_age(match["ownTeamCode"])
    if match_tier is None:
        return []

    busy_as_ref = {
        name
        for _, other in weekend_matches.iterrows()
        if other["wedguid"] != match["wedguid"] and abs(other["DT"] - match["DT"]) < MATCH_DURATION
        for name in volunteers_by_match.get(other["wedguid"], [])
    }

    by_team = {}
    for name, person in roster_df.groupby("name"):
        playing_teams = list(person.loc[person["role"] == "Speler", "team"])
        if not playing_teams:
            continue
        # eligibility follows the teams they PLAY in; being busy covers every team
        # they're on, so a match they coach blocks them too
        all_teams = list(person["team"])
        own_tier = roster.own_tier_from_teams(playing_teams)
        if own_tier in excluded_tiers or match_tier not in roster.eligible_ref_tiers(own_tier):
            continue
        if match["ownTeamCode"] in all_teams or name in busy_as_ref:
            continue
        own_matches = weekend_matches[weekend_matches["ownTeamCode"].isin(all_teams)]
        if any(_conflicts(m, match["DT"]) for _, m in own_matches.iterrows()):
            continue
        home_team = sorted(t for t in playing_teams if roster.parse_age(t) == own_tier)[0]
        by_team.setdefault(home_team, []).append(name)

    options = []
    for team, names in by_team.items():
        team_matches = weekend_matches[weekend_matches["ownTeamCode"] == team].sort_values("DT")
        options.append({"team": team, "tier": roster.parse_age(team), "players": sorted(names), "team_matches": team_matches})
    # AGE_LADDER runs senior -> youngest, so a higher index is closer in age
    options.sort(key=lambda o: (-roster.AGE_LADDER.index(o["tier"]), o["team"]))
    return options


_NL_WEEKDAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def options_subcard_html(options) -> str:
    """The "opties" sub-card under a match card: one compact row per candidate team
    (team + that team's own match this weekend); clicking a row folds open the
    available players. Plain HTML <details>, so opening one causes no rerun."""
    if not options:
        return (
            '<div style="background:#f7f9fb; border-radius:10px; padding:0.5rem 0.75rem; margin:-0.2rem 0 0.8rem 0.9rem; '
            'font-size:0.8rem; color:#999;">Geen beschikbare spelers volgens de ref-hiërarchie.</div>'
        )
    rows = []
    for i, option in enumerate(options, start=1):
        if option["team_matches"].empty:
            own = "geen eigen match"
        else:
            own = ", ".join(
                f"{_NL_WEEKDAYS_SHORT[m['DT'].weekday()]} {m['DT'].strftime('%H:%M')} {'thuis' if m['isHome'] else 'uit'}"
                for _, m in option["team_matches"].iterrows()
            )
        players = "".join(f"<li>{name}</li>" for name in option["players"])
        rows.append(
            '<details style="border-bottom:1px solid #e6eaf0; padding:0.3rem 0;">'
            '<summary style="cursor:pointer; list-style-position:inside;">'
            f'<b>Optie {i} · {option["team"]}</b> <span style="color:#666;">· {own}</span></summary>'
            f'<ul style="margin:0.3rem 0 0.2rem 1.1rem; padding:0; color:#10243e;">{players}</ul>'
            "</details>"
        )
    return (
        '<div style="background:#f7f9fb; border-radius:10px; padding:0.35rem 0.75rem; margin:-0.2rem 0 0.8rem 0.9rem; '
        f'font-size:0.8rem;">{"".join(rows)}</div>'
    )


def ref_count(row, volunteers_by_match) -> int:
    entries = assigned_entries(volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource"))
    return min(len(entries), REQUIRED_REFS)


def filter_matches(matches: pd.DataFrame, volunteers_by_match, option: str) -> pd.DataFrame:
    """Applies an admin filter (REF_COUNT_FILTERS key or AWAY_FILTER_LABEL). Ref-count
    options only ever return home matches — away matches have no ref to count."""
    if matches.empty:
        return matches
    if option == AWAY_FILTER_LABEL:
        return matches[~matches["isHome"]]
    wanted = REF_COUNT_FILTERS.get(option)
    if wanted is None:
        return matches
    home = matches[matches["isHome"]]
    if home.empty:
        return home
    return home[home.apply(lambda row: ref_count(row, volunteers_by_match) == wanted, axis=1)]


def get_volunteers_by_match():
    volunteers = assignments_store.get_assignments()
    by_match = (
        volunteers.groupby("match_key")["player_name"].apply(list).to_dict()
        if not volunteers.empty
        else {}
    )
    return volunteers, by_match


def assigned_entries(volunteers_by_match, wedguid, ref1, ref2, ref_source):
    """Every ref assigned to a match, each tagged whether Basketbal Vlaanderen (VBL)
    itself aanduid'de them (bold everywhere they're shown) — anything else (Twizzit-only
    official, or a club volunteer) is a "clubref" (shown in italic)."""
    entries = []
    for n in (ref1, ref2):
        if isinstance(n, str) and n.strip():
            entries.append({"name": n.strip(), "vbl": ref_source == "VBL"})
    for n in volunteers_by_match.get(wedguid, []):
        entries.append({"name": n, "vbl": False})
    return entries


def match_status(row, volunteers_by_match, player_name):
    """One place computing color/icon/assigned-names/full-state for a match row.
    Urgency-based coloring for choosable matches: red = nog geen ref, orange = nog
    1 ref nodig, grey = volzet — regardless of whether one of the names is you.
    U14+ matches get an extra purple "wss toewijzing door BBVL" status instead of
    red/orange until the Tuesday before the match, since BVBL — not club
    volunteers — is expected to fill those first (see bbvl_priority_info)."""
    if row["Type"] == "Mijn wedstrijd":
        return {"color": COLOR_OWN, "icon": "🔵", "names": [], "entries": [], "am_i_assigned": False, "is_full": False}
    entries = assigned_entries(volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource"))
    names = [e["name"] for e in entries]
    am_i_assigned = player_name in names
    is_full = len(names) >= REQUIRED_REFS

    if not is_full:
        priority = bbvl_priority_info(row)
        if priority and not priority["is_open"]:
            return {
                "color": COLOR_BBVL_WAIT, "icon": "🟣", "names": names, "entries": entries,
                "am_i_assigned": am_i_assigned, "is_full": False,
            }

    if is_full:
        color, icon = COLOR_FULL, "⚪"
    elif len(names) == 1:
        color, icon = COLOR_PARTIAL, "🟠"
    else:
        color, icon = COLOR_NONE, "🔴"
    return {"color": color, "icon": icon, "names": names, "entries": entries, "am_i_assigned": am_i_assigned, "is_full": is_full}


def build_events(kalender: pd.DataFrame, volunteers_by_match, player_name):
    def _color(row):
        return match_status(row, volunteers_by_match, player_name)["color"]

    events = []
    for _, row in kalender.iterrows():
        entries = assigned_entries(
            volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource")
        )
        # bold (Unicode, not markup — FullCalendar titles are plain text) when VBL
        # aanduid'de the ref, italic for a Twizzit-only or club/volunteer ref
        ref_text = ", ".join(textstyle.bold(e["name"]) if e["vbl"] else textstyle.italic(e["name"]) for e in entries)
        ref_line = f"🧑‍⚖️ {ref_text}" if ref_text else "🧑‍⚖️ nog geen ref"
        title = f"{row['thuisploeg']} - {row['tegenstander']}\n📍{row['locatie']} · {ref_line}"

        events.append(
            {
                "id": row["wedguid"],
                "title": title,
                "start": row["DT"].isoformat(),
                "end": (row["DT"] + pd.Timedelta(hours=1, minutes=30)).isoformat(),
                "backgroundColor": _color(row),
                "borderColor": _color(row),
            }
        )
    return events


def render_match_cards(
    matches: pd.DataFrame, volunteers_by_match, player_name, match_dialog, key_prefix: str = "", below_card=None
):
    """Renders each match as an info card grouped by day (team names, status badge,
    time/location/competition, ref names) with a button opening match_dialog —
    used by both the main match list and "Mijn toewijzingen". Card styling itself
    (the `div[class*="st-key-card_"]` rules) is injected once, at page level.
    key_prefix must be distinct per call site: st.tabs() renders every tab's content
    in the same script run (only hides the inactive ones), so the same wedguid
    appearing in two tabs at once would otherwise collide on the same widget key.
    Admin capabilities (removing any assigned ref) live inside match_dialog
    itself now — see make_match_dialog — rather than a separate button/dialog.
    below_card, if given, is called with each match row right after its card
    (e.g. the admin "Opties" tab's sub-card)."""
    for _, day_matches in matches.groupby(matches["DT"].dt.date):
        day_matches = day_matches.sort_values("DT")
        st.markdown(
            f'<div style="font-weight:700; color:#10243e; margin:1rem 0 0.4rem 0; '
            f'font-size:0.95rem; text-transform:capitalize;">{day_label(day_matches.iloc[0]["DT"])}</div>',
            unsafe_allow_html=True,
        )
        for _, row in day_matches.iterrows():
            status = match_status(row, volunteers_by_match, player_name)
            entries = assigned_entries(
                volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource")
            )
            with st.container(key=f"card_{key_prefix}{row['wedguid']}"):
                st.markdown(
                    f"""
                    <div style="background:white; border-left:5px solid {status['color']}; border-radius:12px;
                                padding:0.7rem 7rem 0.6rem 0.75rem; box-shadow:0 1px 4px rgba(0,0,0,0.06);
                                min-height:92px; box-sizing:border-box;">
                      <div style="font-weight:700; color:#10243e; font-size:0.92rem;">{row['thuisploeg']} - {row['tegenstander']}</div>
                      <div style="color:#666; font-size:0.8rem; margin-top:0.35rem;">
                        🕐 {row['DT'].strftime('%H:%M')} · 📍 {row['locatie']} · 🏆 {row['reeks']}
                      </div>
                      <div style="margin-top:0.45rem; font-size:0.84rem;">{ref_line_html(entries)}</div>
                      <div class="match-card-badge">{status_badge_html(status)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                # invisible overlay button (styled via div[class*="st-key-title_"] at
                # page level) — clicking the title text itself also opens the dialog
                if st.button(
                    f"{row['thuisploeg']} - {row['tegenstander']}", key=f"title_{key_prefix}{row['wedguid']}"
                ):
                    match_dialog(row["wedguid"])
                if st.button("👉 Details", key=f"open_{key_prefix}{row['wedguid']}"):
                    match_dialog(row["wedguid"])
            if below_card is not None:
                below_card(row)


def make_match_dialog(kalender: pd.DataFrame, volunteers_by_match, player_name, player_teams, ref_candidates=None):
    """Returns a @st.dialog-decorated function(wedguid) closed over this page's
    state. When player_name == ADMIN_NAME, an extra "verwijder eender wie" control
    appears — normal users can only remove their own assignment, admin can remove
    any club-volunteer assignment (VBL/Twizzit-sourced official refs aren't stored
    in our DB at all, so there's nothing here to actually remove for those).
    When player_name == BESTUUR_NAME, the dialog stops right after showing who's
    assigned — no self-assign, no adding someone else, no removing anyone: a pure
    read-only overview for the board.
    When player_name == ADMIN_HIERARCHY_NAME, ref_candidates(match_row) -> [(name,
    label)] replaces the free-text "add someone else" field with a pick-list of
    exactly those names (shown as their label), and there's no self-assign (the
    pseudo-user isn't a real ref)."""
    is_admin = is_admin_name(player_name)
    is_hierarchy_admin = player_name == ADMIN_HIERARCHY_NAME
    is_bestuur = player_name == BESTUUR_NAME
    is_extern = player_name == EXTERN_NAME

    @st.dialog("Wedstrijd details")
    def _match_dialog(wedguid):
        match = kalender[kalender["wedguid"] == wedguid]
        if match.empty:
            st.warning("Deze wedstrijd is niet meer beschikbaar (kalender ondertussen ververst).")
            return

        m = match.iloc[0]
        status = match_status(m, volunteers_by_match, player_name)
        st.subheader(f"{m['thuisploeg']} — {m['tegenstander']}")
        st.write(f"📅 {m['DT'].strftime('%d/%m/%Y %H:%M')}")
        st.write(f"📍 {m['locatie']}")
        st.write(f"🏆 {m['reeks']}")

        if m["Type"] == "Mijn wedstrijd" and not is_admin and not is_bestuur:
            st.info("Dit is een wedstrijd van je eigen team — je kan jezelf hier niet aan toewijzen.")
            return

        names = status["names"]
        st.divider()
        if names:
            # real Markdown here (st.write renders it) — bold = aangeduid door BVBL,
            # italic = clubref (Twizzit-only official, of vrijwilliger)
            formatted = ", ".join(
                f"**{e['name']}** (BVBL)" if e["vbl"] else f"*{e['name']}* (clubref)"
                for e in status["entries"]
            )
            st.write(f"👥 **Toegewezen** ({len(names)}/{REQUIRED_REFS}): {formatted}")
        else:
            st.write(f"👥 **Nog niemand toegewezen** (0/{REQUIRED_REFS})")

        priority = bbvl_priority_info(m)
        if priority:
            st.info(f"📋 Categorie: {priority['label']} — toewijzing verwacht via BVBL.")

        if is_bestuur:
            return  # read-only: overview only, no assign/remove controls at all

        if is_admin:
            removable = [e["name"] for e in status["entries"] if not e["vbl"]]
            if removable:
                to_remove = st.selectbox(
                    "🔧 Admin: verwijder een toewijzing", options=[""] + removable, key=f"admin_remove_select_{wedguid}"
                )
                if to_remove and st.button(f"🗑️ Verwijder {to_remove}", key=f"admin_remove_btn_{wedguid}", use_container_width=True):
                    assignments_store.unassign(wedguid, to_remove)
                    st.success(f"{to_remove} verwijderd.")
                    st.rerun()

        if m["Type"] == "Mijn wedstrijd":
            return  # admin viewing an own-team match: info + remove-toewijzing only, no self-assign

        # U14-and-up: club self-assignment (new signups only — removing your own
        # existing assignment always stays possible) is locked until BVBL's own
        # window closes, the Tuesday before the match
        locked = bool(priority) and not priority["is_open"] and not is_admin and not status["am_i_assigned"]

        if locked:
            st.caption(
                f"Zelf kiezen kan vanaf dinsdag {priority['cutoff'].strftime('%d/%m')}, "
                "indien dan nog niet ingevuld door BVBL."
            )
        elif status["am_i_assigned"]:
            if st.button("➖ Verwijder mijn toewijzing", use_container_width=True):
                assignments_store.unassign(wedguid, player_name)
                st.success("Toewijzing verwijderd.")
                st.rerun()
        elif not status["is_full"] and not is_extern and not is_hierarchy_admin:
            if st.button("➕ Wijs mezelf toe als scheidsrechter", use_container_width=True, type="primary"):
                assignments_store.assign(wedguid, player_name, ",".join(player_teams))
                st.success("Toegewezen!")
                st.rerun()

        if locked:
            pass  # caption above already covers it — no add-other-name field either
        elif status["is_full"]:
            st.warning(f"Deze wedstrijd heeft al {REQUIRED_REFS} scheidsrechters — er kan niemand meer bij.")
        elif is_hierarchy_admin and ref_candidates is not None:
            st.divider()
            assigned_lower = {n.lower() for n in names}
            labels = {name: label for name, label in ref_candidates(m) if name.lower() not in assigned_lower}
            if not labels:
                st.caption("Geen beschikbare spelers volgens de ref-hiërarchie voor deze wedstrijd.")
            else:
                picked = st.selectbox(
                    "Kies een scheidsrechter (volgens ref-hiërarchie, vrij op dat moment)",
                    options=list(labels), format_func=labels.get, index=None,
                    placeholder="Tik een naam of ploeg...", key=f"hier_{wedguid}",
                )
                if st.button("➕ Voeg toe", use_container_width=True, disabled=picked is None):
                    assignments_store.assign(wedguid, picked, f"toegevoegd door {player_name}")
                    st.success(f"{picked} toegevoegd!")
                    st.rerun()
        else:
            st.divider()
            other_name = st.text_input("Naam van iemand anders toevoegen als scheidsrechter", key=f"other_{wedguid}")
            if st.button("➕ Voeg andere toe", use_container_width=True):
                other_name = other_name.strip()
                existing_lower = [n.lower() for n in names]
                if not other_name:
                    st.error("Vul eerst een naam in.")
                elif other_name.lower() in existing_lower:
                    st.error("Deze persoon is al toegewezen aan deze wedstrijd.")
                else:
                    assignments_store.assign(wedguid, other_name, f"toegevoegd door {player_name}")
                    st.success(f"{other_name} toegevoegd!")
                    st.rerun()

    return _match_dialog
