"""
Shared match-calendar building blocks used by both the "Mijn wedstrijden" (list)
page and the "Weekends" (timegrid) page, so the two stay in sync — same colors,
same assignment rules, same detail dialog — without duplicating the logic.
"""
import pandas as pd
import streamlit as st

from src import assignments_store, data_loader, vbl_source
from src.crosscheck import cross_check_referees

REQUIRED_REFS = 2

COLOR_OWN = "#1f77b4"    # blue — your own team's match, informational only
COLOR_OPEN = "#2ca02c"   # green — still at least 1 free slot, choosable
COLOR_MINE = "#ff7f0e"   # orange — you occupy one of the slots on this match
COLOR_FULL = "#888888"   # grey — 2 referees already assigned, no longer choosable


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
        official = cross[["wedguid", "refFinal1", "refFinal2"]]
    else:
        official = calendar_df[["wedguid", "ref1", "ref2"]].rename(
            columns={"ref1": "refFinal1", "ref2": "refFinal2"}
        )
    calendar_df = calendar_df.merge(official, on="wedguid", how="left")

    team_options = sorted(calendar_df["ownTeamCode"].dropna().unique())
    return calendar_df, team_options


def build_kalender(calendar_df: pd.DataFrame, player_teams) -> pd.DataFrame:
    """Own team's matches (info only) + other teams' home matches (choosable as ref)."""
    own_matches = calendar_df[calendar_df["ownTeamCode"].isin(player_teams)].copy()
    own_matches["Type"] = "Mijn wedstrijd"

    other_home = calendar_df[
        calendar_df["isHome"] & (~calendar_df["ownTeamCode"].isin(player_teams))
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


def _assigned_names(volunteers_by_match, wedguid, ref1, ref2):
    names = [n for n in (ref1, ref2) if isinstance(n, str) and n.strip()]
    names += volunteers_by_match.get(wedguid, [])
    return names


def match_status(row, volunteers_by_match, player_name):
    """One place computing color/icon/assigned-names/full-state for a match row."""
    if row["Type"] == "Mijn wedstrijd":
        return {"color": COLOR_OWN, "icon": "🔵", "names": [], "am_i_assigned": False, "is_full": False}
    names = _assigned_names(volunteers_by_match, row["wedguid"], row["refFinal1"], row["refFinal2"])
    am_i_assigned = player_name in names
    is_full = len(names) >= REQUIRED_REFS
    if am_i_assigned:
        color, icon = COLOR_MINE, "🟠"
    elif is_full:
        color, icon = COLOR_FULL, "⚪"
    else:
        color, icon = COLOR_OPEN, "🟢"
    return {"color": color, "icon": icon, "names": names, "am_i_assigned": am_i_assigned, "is_full": is_full}


def build_events(kalender: pd.DataFrame, volunteers_by_match, player_name):
    def _color(row):
        return match_status(row, volunteers_by_match, player_name)["color"]

    return [
        {
            "id": row["wedguid"],
            "title": f"{row['thuisploeg']} - {row['tegenstander']}",
            "start": row["DT"].isoformat(),
            "end": (row["DT"] + pd.Timedelta(hours=1, minutes=30)).isoformat(),
            "backgroundColor": _color(row),
            "borderColor": _color(row),
        }
        for _, row in kalender.iterrows()
    ]


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
            st.write(f"👥 **Toegewezen** ({len(names)}/{REQUIRED_REFS}): {', '.join(names)}")
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
