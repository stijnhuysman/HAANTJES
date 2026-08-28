"""
Shared match-calendar building blocks used by both the "Mijn wedstrijden" (list)
page and the "Weekends" (timegrid) page, so the two stay in sync — same colors,
same assignment rules, same detail dialog — without duplicating the logic.
"""
import os

import pandas as pd
import streamlit as st

from src import assignments_store, data_loader, roster, textstyle, vbl_store
from src.crosscheck import cross_check_referees
from src.vbl_source import OWN_CLUB_FULLNAME, _extract_own_team_code, _parse_agegroup

# Fallback admin password (checked in auth.py's login screen), used only when
# the ADMIN_PASSWORD env var isn't set. This repo is public on GitHub — anyone
# can read this literal value from the source. Set ADMIN_PASSWORD in .env
# locally and in the Streamlit Cloud app's Secrets for the real deployment, so
# the password that actually protects the live app is never committed anywhere.
DEFAULT_ADMIN_PASSWORD = "Haantjes9700"
ADMIN_NAME = "admin"

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
# self-assignment for these categories only opens from Wednesday 15:00 of that
# match's own week — and only if BVBL hasn't filled it in by then.
BBVL_PRIORITY_TIERS = {14, 16, 18, 21, "SE"}
_TIER_LABELS = {14: "U14", 16: "U16", 18: "U18", 21: "U21", "SE": "Senioren"}


def _bbvl_open_cutoff(dt: pd.Timestamp) -> pd.Timestamp:
    """Wednesday 15:00 of dt's own week (Monday=0 .. Sunday=6, so Wednesday=2)."""
    days_since_wednesday = (dt.weekday() - 2) % 7
    return dt.normalize() - pd.Timedelta(days=days_since_wednesday) + pd.Timedelta(hours=15)


def bbvl_priority_info(row):
    """None for categories below U14, and for friendlies (OEFEN) regardless of
    category — BVBL only assigns officials to real competition matches, never
    to a practice match, so those stay in the normal red/orange/grey situation.
    Otherwise a dict with the tier label, the Wednesday-15:00 cutoff for this
    specific match, and whether that cutoff has passed yet — used to show the
    "toewijzing verwacht via BVBL" note and to gate self-assignment until then."""
    if "OEFEN" in str(row.get("reeks", "")).upper():
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
    so that snapshot, not a per-request fetch, is what's authoritative here."""
    return vbl_store.load_calendar()


def load_vbl_only():
    """Returns (calendar_df, team_options) from VBL alone — no Twizzit involved, so
    this can run before login (team_options is needed by the login screen itself)
    without ever touching the Twizzit upload widget."""
    calendar_df = load_vbl_calendar()
    if calendar_df.empty:
        return calendar_df, []
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
    red/orange until that match's Wednesday-15:00 cutoff, since BVBL — not club
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


def render_match_cards(matches: pd.DataFrame, volunteers_by_match, player_name, match_dialog, key_prefix: str = ""):
    """Renders each match as an info card grouped by day (team names, status badge,
    time/location/competition, ref names) with a button opening match_dialog —
    used by both the main match list and "Mijn toewijzingen". Card styling itself
    (the `div[class*="st-key-card_"]` rules) is injected once, at page level.
    key_prefix must be distinct per call site: st.tabs() renders every tab's content
    in the same script run (only hides the inactive ones), so the same wedguid
    appearing in two tabs at once would otherwise collide on the same widget key.
    Admin capabilities (removing any assigned ref) live inside match_dialog
    itself now — see make_match_dialog — rather than a separate button/dialog."""
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


def make_match_dialog(kalender: pd.DataFrame, volunteers_by_match, player_name, player_teams):
    """Returns a @st.dialog-decorated function(wedguid) closed over this page's
    state. When player_name == ADMIN_NAME, an extra "verwijder eender wie" control
    appears — normal users can only remove their own assignment, admin can remove
    any club-volunteer assignment (VBL/Twizzit-sourced official refs aren't stored
    in our DB at all, so there's nothing here to actually remove for those).
    When player_name == BESTUUR_NAME, the dialog stops right after showing who's
    assigned — no self-assign, no adding someone else, no removing anyone: a pure
    read-only overview for the board."""
    is_admin = player_name == ADMIN_NAME
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
        # window closes, Wednesday 15:00 of that match's week
        locked = bool(priority) and not priority["is_open"] and not is_admin and not status["am_i_assigned"]

        if locked:
            st.caption(
                f"Zelf kiezen kan vanaf woensdag {priority['cutoff'].strftime('%d/%m')} 15:00u, "
                "indien dan nog niet ingevuld door BVBL."
            )
        elif status["am_i_assigned"]:
            if st.button("➖ Verwijder mijn toewijzing", use_container_width=True):
                assignments_store.unassign(wedguid, player_name)
                st.success("Toewijzing verwijderd.")
                st.rerun()
        elif not status["is_full"] and not is_extern:
            if st.button("➕ Wijs mezelf toe als scheidsrechter", use_container_width=True, type="primary"):
                assignments_store.assign(wedguid, player_name, ",".join(player_teams))
                st.success("Toegewezen!")
                st.rerun()

        if locked:
            pass  # caption above already covers it — no add-other-name field either
        elif status["is_full"]:
            st.warning(f"Deze wedstrijd heeft al {REQUIRED_REFS} scheidsrechters — er kan niemand meer bij.")
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
