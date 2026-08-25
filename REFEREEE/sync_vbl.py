"""
Daily VBL sync — fetches the full Basketbal Vlaanderen season calendar and
overwrites the persisted snapshot the app reads (src/vbl_store.py).

Basketbal Vlaanderen is the only source allowed to overwrite referee
assignments in the app, so this script is the one place that authoritative
data enters the shared backend DB. Run daily by the GitHub Actions workflow
(.github/workflows/sync-vbl.yml) — DATABASE_URL there must point at the same
DB the deployed app uses.

Run manually with: python sync_vbl.py
"""
import os

from dotenv import load_dotenv

from src import vbl_source, vbl_store

load_dotenv()


def main():
    club_guid = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
    own_team_prefix = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")

    calendar_df = vbl_source.get_club_calendar(club_guid, own_team_prefix)
    vbl_store.replace_calendar(calendar_df)
    print(f"Synced {len(calendar_df)} wedstrijden van Basketbal Vlaanderen naar de backend.")


if __name__ == "__main__":
    main()
