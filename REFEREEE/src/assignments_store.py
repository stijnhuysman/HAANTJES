"""
Shared store for player-volunteered referee assignments.

Uses Postgres (via the DATABASE_URL env var, e.g. a free Supabase project)
when set, so assignments survive restarts/redeploys on Streamlit Community
Cloud's free tier (its local disk is NOT persistent). Falls back to a local
SQLite file for local development, where that isn't a concern.
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

_LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "assignments.db"

_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        _engine = create_engine(database_url, pool_pre_ping=True)
    else:
        _LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{_LOCAL_DB_PATH}")

    with _engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS assignments (
                    match_key TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    player_team TEXT NOT NULL,
                    assigned_at TEXT NOT NULL,
                    PRIMARY KEY (match_key, player_name)
                )
                """
            )
        )
    return _engine


def get_assignments() -> pd.DataFrame:
    with _get_engine().begin() as conn:
        return pd.read_sql_query(text("SELECT * FROM assignments"), conn)


def assign(match_key: str, player_name: str, player_team: str) -> None:
    engine = _get_engine()
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO assignments "
                    "(match_key, player_name, player_team, assigned_at) "
                    "VALUES (:mk, :pn, :pt, :at)"
                ),
                {"mk": match_key, "pn": player_name, "pt": player_team, "at": now},
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO assignments (match_key, player_name, player_team, assigned_at)
                    VALUES (:mk, :pn, :pt, :at)
                    ON CONFLICT (match_key, player_name) DO UPDATE
                    SET player_team = EXCLUDED.player_team, assigned_at = EXCLUDED.assigned_at
                    """
                ),
                {"mk": match_key, "pn": player_name, "pt": player_team, "at": now},
            )


def unassign(match_key: str, player_name: str) -> None:
    with _get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM assignments WHERE match_key = :mk AND player_name = :pn"),
            {"mk": match_key, "pn": player_name},
        )
