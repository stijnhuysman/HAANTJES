"""
The one place where Basketbal Vlaanderen data enters the backend DB.

Basketbal Vlaanderen is the only source allowed to overwrite referee
assignments in this app, so the fetch + upsert pair lives here and is shared by
both entry points that keep the DB up to date:

  - sync_vbl.py — the daily job (.github/workflows/sync-vbl.yml), which needs
    DATABASE_URL pointed at the same DB the deployed app uses.
  - match_view.load_vbl_calendar() — calls ensure_fresh() on read, so a job
    that never ran (or never got a DATABASE_URL) can't leave the app showing an
    empty or day-old calendar.
"""
import os
from datetime import datetime, timedelta, timezone

from src import vbl_source, vbl_store

# How old the stored snapshot may get before a read refreshes it itself. The
# daily job normally beats this, so ensure_fresh() is a no-op in the deployed
# setup and only kicks in when that job didn't run.
MAX_SNAPSHOT_AGE = timedelta(hours=24)


def sync_calendar() -> int:
    """Fetches the full club season from Basketbal Vlaanderen and writes it to
    the backend DB. Returns how many wedstrijden were written (0 for an empty
    fetch, which upsert_calendar leaves the stored data untouched for)."""
    club_guid = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
    own_team_prefix = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")

    calendar_df = vbl_source.get_club_calendar(club_guid, own_team_prefix)
    return vbl_store.upsert_calendar(calendar_df)


def snapshot_age():
    """How long ago the stored snapshot was synced, or None if never synced."""
    last = vbl_store.last_synced_at()
    if not last:
        return None

    synced_at = last if isinstance(last, datetime) else datetime.fromisoformat(str(last))
    if synced_at.tzinfo is None:
        # synced_at is written as UTC (see vbl_store.upsert_calendar), but a
        # driver can hand it back without the offset
        synced_at = synced_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - synced_at


def ensure_fresh(max_age: timedelta = MAX_SNAPSHOT_AGE) -> int:
    """Refreshes the stored snapshot when it's missing or older than max_age.
    Returns rows written, 0 when the snapshot was already fresh enough.

    A failing fetch is deliberately swallowed: this runs on a page load, and
    Basketbal Vlaanderen being unreachable must not stop the app from rendering
    whatever is already stored. Two cold sessions racing here is harmless —
    upsert_calendar is idempotent."""
    age = snapshot_age()
    if age is not None and age < max_age:
        return 0

    try:
        return sync_calendar()
    except Exception as e:
        print(f"VBL-refresh mislukt ({e}) - app werkt verder op de bestaande backend-data.")
        return 0
