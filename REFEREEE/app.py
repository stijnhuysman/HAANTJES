"""
Haantjes Refereeing — single consolidated player app.

Header: club logo + player name + team chips (one row). Below that, 3 tabs:
  - Wedstrijdlijst: cards for the matches that actually matter to this player —
    their own team's games, plus other teams' home games they're old/senior
    enough to referee (younger age categories).
  - Komende weekends: a real calendar, zaterdag + zondag side by side.
  - Mijn toewijzingen: the matches where this player is assigned as referee.

Logging in as "admin" (password-gated, see auth.ADMIN_NAME) — or with the second
admin password as "admin-hiërarchie", which only differs in picking referees from
a hierarchy-based list instead of typing any name — bypasses all of that
scoping and shows every home match across every team instead, plus 2 extra tabs:
  - Thuiswedstrijden: every home match, filterable on geen ref / 1 ref / volzet
    (plain ref count, independent of the BBVL-wait state).
  - Club overzicht: those home matches plus the away matches of every team a
    potential ref plays for — the full club picture.
  - Opties: the coming weekend's home matches, each with a sub-card listing the
    teams/players who may referee it and aren't playing themselves at that time.

Run with: streamlit run app.py
"""
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_calendar import calendar

from src import auth, match_view, roster, theme

load_dotenv()

st.set_page_config(page_title="Haantjes Refereeing", layout="wide", page_icon="🏀")
theme.inject_css()
theme.inject_pwa()

_APP_DIR = Path(__file__).resolve().parent

OWN_TEAM_PREFIX = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")
# relative (whether from .env or the default) is resolved against this file's own
# folder, not the current working directory streamlit happened to be launched from
_twizzit_path = os.environ.get("TWIZZIT_CSV_PATH", "data/twizzit_export.csv")
TWIZZIT_CSV_PATH = _twizzit_path if Path(_twizzit_path).is_absolute() else str(_APP_DIR / _twizzit_path)

# card styling — shared by the Wedstrijdlijst and Mijn toewijzingen tabs
st.markdown(
    """
    <style>
    div[class*="st-key-card_"] { margin-bottom: 0.5rem; position: relative; }

    /* status badge ("volzet"/"nog 1 nodig"/...) — top-right corner, inside the card */
    .match-card-badge { position: absolute; top: 10px; right: 10px; }

    /* invisible overlay button over the title text — clicking the title itself
       also opens the dialog, not just the "Details" button. Its own text
       mirrors the visible title (see render_match_cards), and matching that
       text's font here lets the button wrap/grow exactly like the real title
       (one line or two), instead of a fixed height that only covered one. */
    div[class*="st-key-title_"] {
        position: absolute !important; top: 6px; left: 6px; right: 7rem;
        z-index: 4; width: auto !important;
    }
    div[class*="st-key-title_"] .stButton { margin: 0 !important; }
    div[class*="st-key-title_"] .stButton > button {
        width: 100% !important; height: auto !important; min-height: 0 !important;
        background: transparent !important; border: none !important; box-shadow: none !important;
        color: transparent !important; padding: 0 !important;
        font-size: 0.92rem !important; font-weight: 700 !important; line-height: 1.3 !important;
        white-space: normal !important; text-align: left !important;
    }

    /* the "Kies" button sits right underneath the badge, in that same corner —
       not a full-width bar attached to the card anymore */
    div[class*="st-key-open_"] {
        position: absolute !important; top: 42px; right: 10px; z-index: 5; width: auto !important;
    }
    div[class*="st-key-open_"] .stButton { margin: 0 !important; }
    div[class*="st-key-open_"] .stButton > button {
        width: auto !important; min-height: 1.9rem !important; padding: 0.25rem 0.7rem !important;
        border-radius: 999px !important;
        background-color: #f0f3f7 !important; color: #10243e !important;
        border: none !important; font-size: 0.75rem !important; font-weight: 600 !important;
        box-shadow: none !important;
    }

    /* "Wissel" (logout) right-aligned next to the name, vertically centered on
       the header row, instead of a full-width button on its own line */
    .st-key-header_row { position: relative; }
    div[class*="st-key-logout_btn"] {
        position: absolute !important; top: 50%; right: 0; transform: translateY(-50%);
        z-index: 5; width: auto !important;
    }
    div[class*="st-key-logout_btn"] .stButton > button {
        width: auto !important; min-height: 1.9rem !important; padding: 0.3rem 0.8rem !important;
        font-size: 0.78rem !important; font-weight: 600 !important;
        border-radius: 999px !important;
        background-color: #f0f3f7 !important; color: #10243e !important; border: none !important;
        box-shadow: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    with st.spinner("Wedstrijden laden..."):
        calendar_df, team_options = match_view.load_vbl_only()
        roster_df = roster.load_roster()
except Exception as e:
    st.error(f"Kon de wedstrijd- of spelersgegevens niet ophalen: {e}")
    st.stop()

if calendar_df.empty:
    st.info("Geen data geladen.")
    st.stop()

player_name, player_teams = auth.login_gate(roster_df, team_options)
# the hierarchy-restricted admin (second admin password) gets the same view and
# powers as admin; only its "add a referee" control differs (see make_match_dialog)
is_admin_user = match_view.is_admin_name(player_name)
is_bestuur_user = player_name == match_view.BESTUUR_NAME
is_extern_user = player_name == match_view.EXTERN_NAME
# coaches and "Extern"-team roster members (e.g. Tijs Simoens) both get the same
# unrestricted all-teams/all-ages eligibility — see roster.has_all_games_access
all_games_user = (
    not is_admin_user
    and not is_bestuur_user
    and not is_extern_user
    and roster.has_all_games_access(roster_df, player_name)
)

# Twizzit's file_uploader fallback (when no local CSV exists) only ever shows for
# admin — regular players never see/trigger that upload control
calendar_df = match_view.merge_twizzit(calendar_df, TWIZZIT_CSV_PATH, OWN_TEAM_PREFIX, allow_upload=is_admin_user)

with st.container(key="header_row"):
    all_matches_label = is_admin_user or is_bestuur_user or is_extern_user or all_games_user
    theme.header_bar(player_name, ["Alle thuiswedstrijden"] if all_matches_label else player_teams)
    auth.logout_button()

if is_admin_user or is_bestuur_user or is_extern_user:
    # admin, Bestuur and Extern see every home match, across all teams — no
    # age/eligibility scoping. Bestuur is read-only from here on (see
    # make_match_dialog); Extern can assign (typing a real name), admin can
    # additionally remove anyone's assignment
    kalender = calendar_df[calendar_df["isHome"]].copy()
    kalender["Type"] = "Beschikbaar"
else:
    kalender = match_view.build_kalender(calendar_df, player_teams, all_games=all_games_user)

# toekomstige wedstrijden — vanaf vandaag (op datum, niet tijdstip, zodat een
# wedstrijd die vandaag al bezig/voorbij is nog zichtbaar blijft, en het volledige
# lopende weekend nooit halverwege wordt afgekapt)
kalender = kalender[kalender["DT"].dt.date >= date.today()]

volunteers, volunteers_by_match = match_view.get_volunteers_by_match()


def _hierarchy_candidates(match_row):
    """Players the ref hierarchy allows for this match and who are free at that
    time, in option order (closest team in age first) — the pick-list shown to
    the hierarchy-restricted admin instead of a free-text name."""
    same_day = calendar_df[calendar_df["DT"].dt.date == match_row["DT"].date()]
    options = match_view.ref_options(match_row, same_day, roster_df, volunteers_by_match)
    return [(name, f"{name} · {option['team']}") for option in options for name in option["players"]]


ref_candidates = _hierarchy_candidates if player_name == match_view.ADMIN_HIERARCHY_NAME else None
match_dialog = match_view.make_match_dialog(
    kalender, volunteers_by_match, player_name, player_teams, ref_candidates=ref_candidates
)

tab_labels = ["📋 Lijst", "📆 Weekend", "✅ Toewijzingen"]
if is_admin_user:
    tab_labels += ["🏠 Thuiswedstrijden", "🏀 Club overzicht", "🧩 Opties"]
tabs = st.tabs(tab_labels)
tab_list, tab_weekend, tab_mine = tabs[:3]

# card/legend colors (🔴/🟠/⚪/🔵) stay as-is — only the filter groups 🔴+🟠 together
STATUS_FILTER_ICONS = {
    "Alles": None,
    "🔵 Eigen": {"🔵"},
    "🔴🟠 Ref(s) nodig": {"🔴", "🟠"},
    "⚪ Volzet": {"⚪"},
}

with tab_list:
    st.markdown(match_view.legend_html(), unsafe_allow_html=True)
    status_filter = st.segmented_control(
        "Filter",
        options=list(STATUS_FILTER_ICONS.keys()),
        default="Alles",
        required=True,
        label_visibility="collapsed",
        key="list_status_filter",
    )
    wanted_icons = STATUS_FILTER_ICONS.get(status_filter)
    if wanted_icons is None:
        filtered_list = kalender
    else:
        mask = kalender.apply(
            lambda row: match_view.match_status(row, volunteers_by_match, player_name)["icon"] in wanted_icons, axis=1
        )
        filtered_list = kalender[mask]

    if filtered_list.empty:
        st.info("Geen wedstrijden gevonden voor deze selectie.")
    else:
        match_view.render_match_cards(
            filtered_list, volunteers_by_match, player_name, match_dialog, key_prefix="list_"
        )

with tab_weekend:
    # known Streamlit quirk: a custom component (the calendar) inside a non-default
    # st.tabs() tab mounts while its panel is still display:none, so its own
    # Streamlit.setFrameHeight() call measures 0 and gets stuck there forever —
    # force the iframe's real height from the outside, overriding that
    st.markdown(
        """
        <style>
        div[class*="st-key-ref_calendar_weekend"] iframe { height: 700px !important; min-height: 700px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(match_view.legend_html(), unsafe_allow_html=True)
    st.caption("zaterdag en zondag naast elkaar · tik op een wedstrijd voor details")
    if kalender.empty:
        st.info("Geen wedstrijden gevonden voor deze selectie.")
    else:
        events = match_view.build_events(kalender, volunteers_by_match, player_name)

        def _current_or_next_weekend_anchor() -> str:
            """Today itself if today is already zaterdag/zondag (lopend weekend),
            otherwise the upcoming zaterdag."""
            today = date.today()
            weekday = today.weekday()  # maandag=0 ... zondag=6
            if weekday >= 5:
                return today.isoformat()
            return (today + timedelta(days=5 - weekday)).isoformat()

        weekend_cal_state = calendar(
            events=events,
            options={
                "initialView": "timeGridWeek",
                "initialDate": _current_or_next_weekend_anchor(),
                # week laten starten op zaterdag, zodat za + de zondag erna samen in 1
                # rij staan (met firstDay=0 hoort een zondag bij de zaterdag 6 dagen LATER)
                "firstDay": 6,
                "hiddenDays": [1, 2, 3, 4, 5],
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
                "height": 700,
                "slotMinTime": "08:00:00",
                "slotMaxTime": "23:00:00",
                "slotLabelFormat": {"hour": "numeric", "minute": "2-digit", "hour12": False},
                "allDaySlot": False,
                "nowIndicator": True,
                "eventDisplay": "block",
                "expandRows": True,
            },
            custom_css="""
                /* force the two day-columns to always share exactly the available
                   width — no horizontal scrolling, ever, no matter how long an
                   event's text is */
                .fc-scrollgrid, .fc-scrollgrid table { table-layout: fixed !important; width: 100% !important; }
                /* kill horizontal scroll (that's the overflow bug), but keep vertical
                   scroll — 08:00-23:00 is 15 hours, taller than the 700px calendar
                   height, so a visible scrollbar here is needed to reach every hour */
                .fc-scroller { overflow-x: hidden !important; overflow-y: auto !important; }
                .fc-scroller::-webkit-scrollbar { width: 6px; }
                .fc-scroller::-webkit-scrollbar-thumb { background: #c7d0dc; border-radius: 3px; }
                .fc-view-harness { overflow: visible !important; }
                .fc-timegrid-axis, .fc-timegrid-axis-frame { width: 30px !important; max-width: 30px !important; }
                .fc-timegrid-slot-label-cushion { font-size: 0.62em !important; padding: 0 1px !important; }
                .fc-timegrid-col { min-width: 0 !important; }
                .fc-timegrid-event .fc-event-title {
                    font-size: 0.72em; font-weight: 600; white-space: pre-line; line-height: 1.25;
                    overflow-wrap: anywhere; word-break: break-word;
                }
                .fc-timegrid-event .fc-event-time { font-size: 0.65em; overflow-wrap: anywhere; }
                .fc-timegrid-event { cursor: pointer; }
                .fc-col-header-cell-cushion { font-size: 0.85em; font-weight: 600; padding: 3px; overflow-wrap: anywhere; }
            """,
            key="ref_calendar_weekend",
        )

        weekend_clicked = weekend_cal_state.get("eventClick") if weekend_cal_state else None
        if weekend_clicked:
            wedguid = weekend_clicked["event"]["id"]
            if st.session_state.get("_last_dialog_wedguid_weekend") != wedguid:
                st.session_state["_last_dialog_wedguid_weekend"] = wedguid
                match_dialog(wedguid)

with tab_mine:
    mine = volunteers[volunteers["player_name"] == player_name] if not volunteers.empty else pd.DataFrame()
    if mine.empty:
        st.caption("Nog geen wedstrijden toegewezen.")
    else:
        mine_matches = calendar_df[calendar_df["wedguid"].isin(mine["match_key"])].copy()
        mine_matches["Type"] = "Beschikbaar"  # reuse the status-color machinery (never "Mijn wedstrijd")
        mine_dialog = match_view.make_match_dialog(
            mine_matches, volunteers_by_match, player_name, player_teams, ref_candidates=ref_candidates
        )
        match_view.render_match_cards(mine_matches, volunteers_by_match, player_name, mine_dialog, key_prefix="mine_")


def _admin_filtered_cards(matches, filter_options, key):
    """Filter control + match cards for the admin-only tabs. Filters on the plain
    ref count (see match_view.REF_COUNT_FILTERS), not on the BBVL-aware card color."""
    option = st.segmented_control(
        "Filter", options=filter_options, default="Alles", required=True,
        label_visibility="collapsed", key=f"{key}_filter",
    )
    filtered = match_view.filter_matches(matches, volunteers_by_match, option)
    st.caption(f"{len(filtered)} wedstrijd(en)")
    if filtered.empty:
        st.info("Geen wedstrijden gevonden voor deze selectie.")
        return
    dialog = match_view.make_match_dialog(
        matches, volunteers_by_match, player_name, player_teams, ref_candidates=ref_candidates
    )
    match_view.render_match_cards(filtered, volunteers_by_match, player_name, dialog, key_prefix=f"{key}_")


if is_admin_user:
    upcoming = calendar_df[calendar_df["DT"].dt.date >= date.today()]

    with tabs[3]:
        st.caption(
            "Alle thuiswedstrijden + uitwedstrijden van Dames/Heren (HSE/DSE) · "
            "filter op aantal toegewezen refs, los van BBVL-toewijzing"
        )
        home_matches = upcoming[upcoming["isHome"]].copy()
        home_matches["Type"] = "Beschikbaar"
        # senior away matches as blue info cards, like in Club overzicht
        senior_away = match_view.filter_category(upcoming[~upcoming["isHome"]], "Dames/Heren").copy()
        senior_away["Type"] = "Mijn wedstrijd"
        home_tab_matches = pd.concat([home_matches, senior_away], ignore_index=True).sort_values("DT")
        _admin_filtered_cards(
            home_tab_matches, list(match_view.REF_COUNT_FILTERS) + [match_view.AWAY_FILTER_LABEL], key="adminhome"
        )

    with tabs[4]:
        st.caption(
            "Thuiswedstrijden die een ref nodig hebben + uitwedstrijden van ploegen "
            "waarin een potentiële ref speelt"
        )
        club_matches = match_view.build_club_overview(upcoming, roster_df)
        category = st.segmented_control(
            "Categorie", options=list(match_view.CATEGORY_FILTERS), default="Alle categorieën", required=True,
            label_visibility="collapsed", key="adminclub_category",
        )
        club_matches = match_view.filter_category(club_matches, category)
        _admin_filtered_cards(
            club_matches, list(match_view.REF_COUNT_FILTERS) + [match_view.AWAY_FILTER_LABEL], key="adminclub"
        )

    with tabs[5]:
        saturday, sunday = match_view.upcoming_weekend(date.today())
        st.caption(
            f"Thuiswedstrijden van het komend weekend ({saturday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}) "
            "zonder BVBL-ref en met nog 0 of 1 clubref, met per wedstrijd de ploegen/spelers die mogen "
            "fluiten volgens de ref-hiërarchie en zelf geen overlappende wedstrijd hebben"
        )
        # every match of the weekend (home + away) — needed to check who's playing when
        weekend_matches = upcoming[upcoming["DT"].dt.date.isin([saturday, sunday])]
        weekend_home = weekend_matches[weekend_matches["isHome"]].copy()
        # only matches that still need club refs: no BVBL ref yet, and not volzet
        if not weekend_home.empty:
            weekend_home = weekend_home[
                weekend_home.apply(lambda row: match_view.needs_club_refs(row, volunteers_by_match), axis=1)
            ]
        weekend_home["Type"] = "Beschikbaar"
        if weekend_home.empty:
            st.info("Geen thuiswedstrijden dit weekend die nog clubrefs nodig hebben.")
        else:
            options_dialog = match_view.make_match_dialog(
                weekend_home, volunteers_by_match, player_name, player_teams, ref_candidates=ref_candidates
            )

            def _options_subcard(row):
                options = match_view.ref_options(
                    row, weekend_matches, roster_df, volunteers_by_match,
                    excluded_tiers=match_view.OPTIES_EXCLUDED_REF_TIERS,
                )
                st.markdown(match_view.options_subcard_html(options), unsafe_allow_html=True)

            match_view.render_match_cards(
                weekend_home, volunteers_by_match, player_name, options_dialog,
                key_prefix="adminopties_", below_card=_options_subcard,
            )
