"""
Shared store for player-volunteered referee assignments. Uses the shared
engine from src/db.py (Postgres via DATABASE_URL, or local SQLite fallback).
"""
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from src.db import get_engine

_initialized = False


def _get_engine():
    global _initialized
    engine = get_engine()
    if not _initialized:
        with engine.begin() as conn:
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
        _initialized = True
    return engine


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
