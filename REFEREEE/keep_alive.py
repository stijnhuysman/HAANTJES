"""
Keep-alive for the deployed app on Streamlit Community Cloud.

Community Cloud puts an app to sleep after a period without visitors, and that
period can't be configured. A plain HTTP request (curl) isn't enough to count as
a visit, so this opens the app in a real headless browser instead — and if the
app is already asleep, clicks Streamlit's own "get this app back up" button.

Run on a schedule by the GitHub Actions workflow (.github/workflows/keep-alive.yml).
Run manually with: python keep_alive.py
"""
import os
import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://clubrefshaantjes.streamlit.app/")

# time given to the app itself to boot/render once the page is open — a cold
# start after sleeping takes well over a minute on Community Cloud
BOOT_WAIT_MS = 90_000


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)
        except PlaywrightTimeoutError:
            print(f"Kon {APP_URL} niet openen (timeout).")
            browser.close()
            return 1

        wake_button = page.get_by_role("button", name=re.compile("get this app back up", re.IGNORECASE))
        try:
            wake_button.wait_for(timeout=15_000)
            wake_button.click()
            print("App sliep — wake-up knop aangeklikt.")
        except PlaywrightTimeoutError:
            print("App was wakker.")

        # stay on the page long enough for the app's own session to start, so
        # Community Cloud registers it as real use
        page.wait_for_timeout(BOOT_WAIT_MS)
        print(f"Bezocht: {APP_URL}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
