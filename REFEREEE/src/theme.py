"""Shared visual styling and the app's single header bar — call inject_css() at
the top of every page, then header_bar(player_name, teams) once logged in."""
import base64
from pathlib import Path

import streamlit as st

_LOGO_PATH = Path(__file__).resolve().parent.parent / "logo_haantjes.jpg"
_logo_data_uri_cache = None


def logo_data_uri() -> str | None:
    """Base64 data URI for the club logo — embedded inline so the header row
    doesn't depend on static-file-serving being correctly configured."""
    global _logo_data_uri_cache
    if _logo_data_uri_cache is None and _LOGO_PATH.exists():
        b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        _logo_data_uri_cache = f"data:image/jpeg;base64,{b64}"
    return _logo_data_uri_cache


def avatar_html(photo_url: str | None, size: int = 64) -> str:
    if photo_url:
        return (
            f'<img src="{photo_url}" style="width:{size}px;height:{size}px;border-radius:50%;'
            f'object-fit:cover;border:3px solid #1f77b4;display:block;" />'
        )
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#e8edf3;'
        f'display:flex;align-items:center;justify-content:center;font-size:{size * 0.45}px;">🙂</div>'
    )


def team_chips_html(teams) -> str:
    if not teams:
        return '<span style="color:#c0392b;font-size:0.82rem;">Geen wedstrijden gevonden voor je team(en)</span>'
    return "".join(
        f'<span style="display:inline-block;background:#eef4fb;color:#1f77b4;border-radius:999px;'
        f'padding:0.2rem 0.7rem;font-size:0.78rem;font-weight:600;margin:0.15rem 0.3rem 0 0;">{t}</span>'
        for t in teams
    )


def header_bar(player_name: str, teams):
    """The app's single main header: club logo on the left, player name + team
    chips beside it — one compact row instead of the logo/profile-card/page-title
    that used to be spread across three separate spots."""
    logo = logo_data_uri()
    logo_html = (
        f'<img src="{logo}" style="width:52px;height:52px;object-fit:contain;flex-shrink:0;" />' if logo else ""
    )
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:0.7rem; margin: 0.2rem 0 1rem 0; padding-right: 5.5rem;">
            {logo_html}
            <div>
                <div style="font-weight:700; color:#10243e; font-size:1.1rem; line-height:1.2;">{player_name}</div>
                <div style="margin-top:0.2rem;">{team_chips_html(teams)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    """Always renders the phone-app layout — a fixed, phone-width column —
    regardless of the viewport/device. There is deliberately no "desktop view":
    on a wide monitor this just shows the same narrow app column centered on
    the page. No sidebar and no Streamlit chrome — header_bar() + st.tabs()
    are the app's only navigation."""
    st.markdown(
        """
        <style>
        /* also set on html/body, not just .stApp — otherwise iOS's rubber-band
           overscroll bounce flashes white behind the app for a frame */
        html, body { background-color: #f5f6f8; }
        .stApp { background-color: #f5f6f8; }

        h1, h2, h3, h4 { font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; }

        /* hide all of Streamlit's default chrome — no sidebar toggle needed
           since there's no sidebar, and this should read as an app, not a
           data notebook */
        #MainMenu, footer { visibility: hidden; height: 0; }
        header[data-testid="stHeader"] { display: none; }
        section[data-testid="stSidebar"],
        [data-testid^="stSidebar"] { display: none !important; }

        /* fixed phone-width column, centered, on every screen size — tuned to still
           breathe on a narrow iPhone SE (375px) viewport */
        .block-container {
            max-width: 480px;
            margin: 0 auto;
            padding: 0.9rem 0.7rem 2rem 0.7rem;
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

        /* tabs: bigger, evenly spaced, thumb-friendly tap targets */
        button[data-baseweb="tab"] { font-size: 0.85rem; font-weight: 600; padding: 0.6rem 0.4rem; }

        /* the tab bar itself stays reachable while scrolling a long card list —
           the actual navigation, so it's the one thing that stays put (the header
           above it is just identity info you already know, so it's fine for that
           to scroll away) */
        div[data-baseweb="tab-list"] {
            position: sticky; top: 0; z-index: 100;
            background-color: #f5f6f8;
            padding-top: 0.3rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }
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
