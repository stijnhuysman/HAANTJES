"""
Persisted snapshot of the Basketbal Vlaanderen (VBL) season calendar.

Basketbal Vlaanderen is the only source allowed to overwrite referee
assignments in this app, so its data is synced once daily (sync_vbl.py, run by
the GitHub Actions workflow) into this table instead of being fetched live from
the VBL API on every page load. The app reads this snapshot via load_calendar().
"""
from datetime import datetime, timezone

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
                    CREATE TABLE IF NOT EXISTS vbl_calendar (
                        wedguid TEXT PRIMARY KEY,
                        dt TEXT,
                        thuisploeg TEXT,
                        tegenstander TEXT,
                        locatie TEXT,
                        reeks TEXT,
                        agegroup TEXT,
                        own_team_code TEXT,
                        is_home BOOLEAN,
                        ref1 TEXT,
                        ref2 TEXT,
                        uitslag TEXT,
                        synced_at TEXT NOT NULL
                    )
                    """
                )
            )
        _initialized = True
    return engine


def upsert_calendar(calendar_df: pd.DataFrame) -> int:
    """Adds/updates every match from this fetch — never deletes a row. Never
    wipes stored history: toewijzingen are keyed to wedguid, so a match that
    silently drops out of VBL's response (a bad fetch, a trimmed season list)
    must not make its row — and with it, its assignment — disappear from the
    app. Returns how many rows were written (0 if the fetch was empty and
    nothing happened)."""
    if calendar_df.empty:
        return 0

    engine = _get_engine()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [
        {
            "wedguid": r["wedguid"],
            "dt": r["DT"].isoformat() if pd.notna(r["DT"]) else None,
            "thuisploeg": r["thuisploeg"],
            "tegenstander": r["tegenstander"],
            "locatie": r["locatie"],
            "reeks": r["reeks"],
            "agegroup": None if r["agegroup"] is None else str(r["agegroup"]),
            "own_team_code": r["ownTeamCode"],
            "is_home": bool(r["isHome"]),
            "ref1": r["ref1"],
            "ref2": r["ref2"],
            "uitslag": r["uitslag"],
            "synced_at": now,
        }
        for _, r in calendar_df.iterrows()
    ]

    if engine.dialect.name == "sqlite":
        upsert_sql = """
            INSERT OR REPLACE INTO vbl_calendar
                (wedguid, dt, thuisploeg, tegenstander, locatie, reeks, agegroup,
                 own_team_code, is_home, ref1, ref2, uitslag, synced_at)
            VALUES
                (:wedguid, :dt, :thuisploeg, :tegenstander, :locatie, :reeks, :agegroup,
                 :own_team_code, :is_home, :ref1, :ref2, :uitslag, :synced_at)
        """
    else:
        upsert_sql = """
            INSERT INTO vbl_calendar
                (wedguid, dt, thuisploeg, tegenstander, locatie, reeks, agegroup,
                 own_team_code, is_home, ref1, ref2, uitslag, synced_at)
            VALUES
                (:wedguid, :dt, :thuisploeg, :tegenstander, :locatie, :reeks, :agegroup,
                 :own_team_code, :is_home, :ref1, :ref2, :uitslag, :synced_at)
            ON CONFLICT (wedguid) DO UPDATE SET
                dt = EXCLUDED.dt, thuisploeg = EXCLUDED.thuisploeg, tegenstander = EXCLUDED.tegenstander,
                locatie = EXCLUDED.locatie, reeks = EXCLUDED.reeks, agegroup = EXCLUDED.agegroup,
                own_team_code = EXCLUDED.own_team_code, is_home = EXCLUDED.is_home,
                ref1 = EXCLUDED.ref1, ref2 = EXCLUDED.ref2, uitslag = EXCLUDED.uitslag,
                synced_at = EXCLUDED.synced_at
        """

    with engine.begin() as conn:
        conn.execute(text(upsert_sql), rows)
    return len(rows)


def load_calendar() -> pd.DataFrame:
    """Last-synced VBL calendar, in the same column shape as
    vbl_source.get_club_calendar() — empty DataFrame if never synced yet."""
    engine = _get_engine()
    with engine.begin() as conn:
        df = pd.read_sql_query(text("SELECT * FROM vbl_calendar"), conn)
    if df.empty:
        return df

    df = df.rename(columns={"dt": "DT", "own_team_code": "ownTeamCode", "is_home": "isHome"})
    df["DT"] = pd.to_datetime(df["DT"])
    df["isHome"] = df["isHome"].astype(bool)
    return df[
        [
            "wedguid", "DT", "thuisploeg", "tegenstander", "locatie", "reeks",
            "agegroup", "ownTeamCode", "isHome", "ref1", "ref2", "uitslag",
        ]
    ].sort_values("DT").reset_index(drop=True)


def last_synced_at():
    """ISO timestamp of the most recent successful sync, or None if never synced."""
    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT MAX(synced_at) FROM vbl_calendar")).fetchone()
    return row[0] if row and row[0] else None
