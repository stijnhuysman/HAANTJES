"""
Shared Twizzit-export loading: use the local file if present (local dev),
otherwise offer an upload widget (needed once deployed, where there's no
local disk to read from). Cached in st.session_state so every page shares
the same upload within one browser session.
"""
import os

import streamlit as st

from src import twizzit_source


def get_twizzit_calendar(default_path: str, own_team_prefix: str):
    """Returns (DataFrame or None, error message or None)."""
    if "twizzit_df" in st.session_state:
        return st.session_state["twizzit_df"], None

    if os.path.exists(default_path):
        try:
            df = twizzit_source.load_twizzit_export(default_path, own_team_prefix)
            st.session_state["twizzit_df"] = df
            return df, None
        except Exception as e:
            return None, str(e)

    uploaded = st.file_uploader(
        "Geen lokaal Twizzit-bestand gevonden — upload de export (CSV) hier",
        type="csv",
        key="twizzit_upload_widget",
    )
    if uploaded is None:
        return None, None

    try:
        df = twizzit_source.load_twizzit_export(uploaded, own_team_prefix)
        st.session_state["twizzit_df"] = df
        return df, None
    except Exception as e:
        return None, str(e)
