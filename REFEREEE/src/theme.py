"""Shared visual styling — call inject_css() once at the top of every page."""
import streamlit as st


def inject_css():
    st.markdown(
        """
        <style>
        .stApp { background-color: #f5f6f8; }

        h1, h2, h3, h4 { font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; }

        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            padding: 0.5rem 1rem;
        }

        div[data-testid="stMetric"] {
            background-color: white;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        section[data-testid="stSidebar"] {
            background-color: #10243e;
        }
        section[data-testid="stSidebar"] * {
            color: #f0f0f0 !important;
        }
        section[data-testid="stSidebar"] .stButton > button {
            background-color: #1f77b4;
            color: white !important;
            border: none;
        }

        /* mobile: tighter page padding so more content fits without side-scroll */
        @media (max-width: 640px) {
            .block-container { padding: 1rem 0.6rem 2rem 0.6rem; }
            h1 { font-size: 1.5rem; }
            h2 { font-size: 1.2rem; }
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
