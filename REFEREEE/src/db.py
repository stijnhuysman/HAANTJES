"""
Shared SQLAlchemy engine for every store module in this app (assignments_store,
vbl_store): Postgres via DATABASE_URL when set (survives restarts/redeploys on
Streamlit Community Cloud's free tier, whose local disk is NOT persistent),
falling back to a local SQLite file for local development.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine

_LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "assignments.db"

_engine = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        _engine = create_engine(database_url, pool_pre_ping=True)
    else:
        _LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{_LOCAL_DB_PATH}")
    return _engine
