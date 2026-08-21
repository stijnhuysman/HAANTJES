"""Shared visual styling — call inject_css() + app_logo() at the top of every page."""
from pathlib import Path

import streamlit as st

_LOGO_PATH = Path(__file__).resolve().parent.parent / "logo_haantjes.jpg"


def app_logo():
    """Club logo top-left of the app (above the sidebar nav), on every page."""
    if _LOGO_PATH.exists():
        st.logo(str(_LOGO_PATH), size="large")


def inject_pwa():
    """Adds PWA tags (manifest, icons, theme-color) to the real <head> — Streamlit's
    own st.markdown/html only reaches the body, so this reaches into the parent
    document via a component iframe instead. Lets phones "Add to Home Screen" with
    the club icon and open full-screen (no browser address bar), like a real app.
    Requires [server] enableStaticServing = true in .streamlit/config.toml and the
    icons/manifest.json under static/ (served at /app/static/...)."""
    st.iframe(
        """
        <script>
        (function() {
            const doc = window.parent.document;
            if (doc.getElementById('haantjes-pwa-tags')) return;
            const marker = doc.createElement('meta');
            marker.id = 'haantjes-pwa-tags';
            marker.name = 'haantjes-pwa-tags';
            doc.head.appendChild(marker);

            function addLink(rel, href) {
                const el = doc.createElement('link');
                el.rel = rel;
                el.href = href;
                doc.head.appendChild(el);
            }
            function addMeta(name, content) {
                const el = doc.createElement('meta');
                el.name = name;
                el.content = content;
                doc.head.appendChild(el);
            }

            addLink('manifest', '/app/static/manifest.json');
            addLink('icon', '/app/static/icon-192.png');
            addLink('apple-touch-icon', '/app/static/apple-touch-icon.png');
            addMeta('theme-color', '#1f77b4');
            addMeta('apple-mobile-web-app-capable', 'yes');
            addMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
            addMeta('apple-mobile-web-app-title', 'Haantjes Ref');
            addMeta('mobile-web-app-capable', 'yes');
        })();
        </script>
        """,
        height=1,
        width=1,
    )


def inject_css():
    """Always renders the phone-app layout — a fixed, phone-width column with a
    bottom tab bar — regardless of the viewport/device. There is deliberately no
    "desktop view": on a wide monitor this just shows the same narrow app column
    centered on the page, instead of spreading out into a wide sidebar layout."""
    st.markdown(
        """
        <style>
        .stApp { background-color: #f5f6f8; }

        h1, h2, h3, h4 { font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; }

        /* hide Streamlit's default chrome so this reads as an app, not a data notebook */
        #MainMenu, footer { visibility: hidden; height: 0; }

        /* no sidebar / desktop nav anywhere — the bottom tab bar is the only nav */
        section[data-testid="stSidebar"],
        [data-testid^="stSidebar"] { display: none !important; }

        /* fixed phone-width column, centered, on every screen size — tuned to still
           breathe on a narrow iPhone SE (375px) viewport */
        .block-container {
            max-width: 480px;
            margin: 0 auto;
            padding: 0.75rem 0.7rem 5.75rem 0.7rem;
        }
        h1 { font-size: 1.35rem; }
        h2 { font-size: 1.1rem; }

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            padding: 0.6rem 1.1rem;
            min-height: 2.75rem;
            width: 100%;
            font-size: 1.05rem;
        }

        div[data-testid="stMetric"] {
            background-color: white;
            border-radius: 10px;
            padding: 0.6rem 0.8rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        /* big, thumb-friendly tap targets everywhere */
        div[data-baseweb="select"] > div, .stTextInput input, .stMultiSelect > div {
            min-height: 2.75rem;
            font-size: 1rem;
        }

        /* columns always stack full-width — no side-by-side desktop layout */
        div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


NAV_ITEMS = [
    ("wedstrijden", "pages/2_Mijn_Wedstrijden.py", "Wedstrijdlijst", "🧑‍⚖️"),
    ("weekends", "pages/3_Weekends.py", "Weekend", "📆"),
]


def bottom_nav(current: str):
    """Fixed bottom tab bar — the app's only navigation, styled like a real phone
    app's tab bar: icon stacked above label, and the current tab highlighted (a
    pill behind icon+label), so it's obvious where you are. `current` is one of
    NAV_ITEMS' keys ("wedstrijden", "weekends") — each page passes its own so
    only that tab gets the active styling. Overzicht/Rode Los are intentionally
    not in NAV_ITEMS (hidden from navigation) — the app files still exist, just
    not advertised as player-facing destinations."""
    with st.container(key="bottom_nav"):
        cols = st.columns(len(NAV_ITEMS))
        for col, (key, path, label, icon) in zip(cols, NAV_ITEMS):
            with col:
                with st.container(key=f"navtab_{key}"):
                    st.page_link(path, label=label, icon=icon, use_container_width=True)

    st.markdown(
        f"""
        <style>
        .st-key-bottom_nav {{
            position: fixed; left: 50%; transform: translateX(-50%);
            bottom: 0; width: 100%; max-width: 480px; z-index: 999;
            background-color: #10243e;
            padding: 0.3rem 0.3rem calc(0.3rem + env(safe-area-inset-bottom));
            box-shadow: 0 -2px 10px rgba(0,0,0,0.2);
        }}
        /* the tab row itself must stay horizontal — overrides the app-wide
           "always stack columns" rule, which only targets normal page content */
        .st-key-bottom_nav div[data-testid="stHorizontalBlock"] {{ flex-direction: row !important; gap: 0 !important; }}
        .st-key-bottom_nav div[data-testid="column"] {{ width: auto !important; flex: 1 1 0 !important; }}

        /* icon stacked above the label, centered, like a native tab bar item —
           target both the stable class and the data-testid, whichever this
           Streamlit build actually renders */
        .st-key-bottom_nav .stPageLink,
        .st-key-bottom_nav a[data-testid="stPageLink"] {{
            display: flex !important; flex-direction: column !important;
            align-items: center !important; justify-content: center !important;
            gap: 0.1rem !important;
            padding: 0.4rem 0.1rem !important;
            margin: 0.15rem !important;
            border-radius: 12px !important;
            text-decoration: none !important;
            font-size: 1.15rem !important;
            line-height: 1.1 !important;
            transition: background-color 0.15s ease;
        }}
        .st-key-bottom_nav .stPageLink p,
        .st-key-bottom_nav a[data-testid="stPageLink"] p {{
            color: #b7c3d6 !important; font-size: 0.66rem !important; font-weight: 600 !important; margin: 0.1rem 0 0 0 !important;
        }}
        /* active tab — highlighted pill + brand-blue label, so it's obvious where you are */
        .st-key-navtab_{current} .stPageLink,
        .st-key-navtab_{current} a[data-testid="stPageLink"] {{
            background-color: rgba(31, 119, 180, 0.28) !important;
        }}
        .st-key-navtab_{current} .stPageLink p,
        .st-key-navtab_{current} a[data-testid="stPageLink"] p {{
            color: #ffffff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = ""):
    subtitle_html = f'<p style="color:#666; margin-top:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 1rem 0; border-bottom: 3px solid #1f77b4; margin-bottom: 1.5rem;">
          <h1 style="margin-bottom:0; color:#10243e;">{title}</h1>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
