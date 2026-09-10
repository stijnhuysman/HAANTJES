"""
Daily VBL sync — fetches the full Basketbal Vlaanderen season calendar and
updates the backend DB the app reads (src/vbl_store.py).

Thin CLI wrapper around src/vbl_sync.py, which holds the actual fetch + upsert
and is shared with the app's own on-read refresh. Run daily by the GitHub
Actions workflow (.github/workflows/sync-vbl.yml) — DATABASE_URL there must
point at the same DB the deployed app uses.

Run manually with: python sync_vbl.py
"""
from dotenv import load_dotenv

from src import vbl_sync

load_dotenv()


def main():
    written = vbl_sync.sync_calendar()
    if written == 0:
        print("Lege/mislukte fetch van Basketbal Vlaanderen — backend niet aangepast, bestaande data blijft behouden.")
    else:
        print(f"Synced {written} wedstrijden van Basketbal Vlaanderen naar de backend.")


if __name__ == "__main__":
    main()
