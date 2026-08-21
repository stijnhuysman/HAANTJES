"""
Shared match-calendar building blocks used by both the "Mijn wedstrijden" (list)
page and the "Weekends" (timegrid) page, so the two stay in sync — same colors,
same assignment rules, same detail dialog — without duplicating the logic.
"""
import pandas as pd
import streamlit as st

from src import assignments_store, data_loader, roster, textstyle, vbl_source
from src.crosscheck import cross_check_referees

REQUIRED_REFS = 2

COLOR_OWN = "#1f77b4"     # blue — your own team's match, informational only
COLOR_NONE = "#d62728"    # red — nog geen ref toegewezen
COLOR_PARTIAL = "#ff7f0e" # orange — nog 1 ref nodig
COLOR_FULL = "#888888"    # grey — volzet (2 refs), no longer choosable

STATUS_LABELS = {"🔵": "Eigen wedstrijd", "🔴": "Nog geen ref", "🟠": "Nog 1 nodig", "⚪": "Volzet"}

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


def ref_line_html(entries) -> str:
    """Real <b>/<i> tags (not the Unicode trick build_events uses) — this is meant
    for st.markdown/raw HTML contexts, which render actual HTML, unlike FullCalendar
    event titles which only ever show plain text."""
    if not entries:
        return '<span style="color:#999;">Nog niemand toegewezen</span>'
    parts = [f"<b>{e['name']}</b>" if e["vbl"] else f"<i>{e['name']}</i>" for e in entries]
    return "🧑‍⚖️ " + ", ".join(parts)


@st.cache_data(ttl=900)
def load_vbl_calendar(club_guid: str, own_team_prefix: str) -> pd.DataFrame:
    return vbl_source.get_club_calendar(club_guid, own_team_prefix)


def load_context(club_guid: str, own_team_prefix: str, twizzit_csv_path: str):
    """Returns (calendar_df, team_options): VBL calendar merged with the cross-checked
    official referee columns (refFinal1/refFinal2), plus the list of own team codes."""
    calendar_df = load_vbl_calendar(club_guid, own_team_prefix)
    if calendar_df.empty:
        return calendar_df, []

    twizzit, twizzit_error = data_loader.get_twizzit_calendar(twizzit_csv_path, own_team_prefix)
    if twizzit is not None and not twizzit.empty and not twizzit_error:
        cross = cross_check_referees(calendar_df, twizzit)
        official = cross[["wedguid", "refFinal1", "refFinal2", "refSource"]]
    else:
        # no Twizzit to cross-check against -> ref1/ref2 here are VBL's own fields, so
        # any name present was, by definition, aangeduid door Basketbal Vlaanderen
        official = calendar_df[["wedguid", "ref1", "ref2"]].rename(
            columns={"ref1": "refFinal1", "ref2": "refFinal2"}
        )
        official["refSource"] = "VBL"
    calendar_df = calendar_df.merge(official, on="wedguid", how="left")

    team_options = sorted(calendar_df["ownTeamCode"].dropna().unique())
    return calendar_df, team_options


def build_kalender(calendar_df: pd.DataFrame, player_teams) -> pd.DataFrame:
    """Own team's matches (info only) + other teams' home matches the player is
    old/senior enough to referee, per the club's age-eligibility rule (own tier ->
    ELIGIBLE_TO_REF[own tier], see src/roster.py)."""
    own_matches = calendar_df[calendar_df["ownTeamCode"].isin(player_teams)].copy()
    own_matches["Type"] = "Mijn wedstrijd"

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
    1 ref nodig, grey = volzet — regardless of whether one of the names is you."""
    if row["Type"] == "Mijn wedstrijd":
        return {"color": COLOR_OWN, "icon": "🔵", "names": [], "entries": [], "am_i_assigned": False, "is_full": False}
    entries = assigned_entries(volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"], row.get("refSource"))
    names = [e["name"] for e in entries]
    am_i_assigned = player_name in names
    is_full = len(names) >= REQUIRED_REFS
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


def make_match_dialog(kalender: pd.DataFrame, volunteers_by_match, player_name, player_teams):
    """Returns a @st.dialog-decorated function(wedguid) closed over this page's state."""

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

        if m["Type"] == "Mijn wedstrijd":
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

        if status["am_i_assigned"]:
            if st.button("➖ Verwijder mijn toewijzing", use_container_width=True):
                assignments_store.unassign(wedguid, player_name)
                st.success("Toewijzing verwijderd.")
                st.rerun()
        elif not status["is_full"]:
            if st.button("➕ Wijs mezelf toe als scheidsrechter", use_container_width=True, type="primary"):
                assignments_store.assign(wedguid, player_name, ",".join(player_teams))
                st.success("Toegewezen!")
                st.rerun()

        if status["is_full"]:
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
