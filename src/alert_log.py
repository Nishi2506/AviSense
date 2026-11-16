"""SQLite log of alert episodes (one row per episode, updated while active)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_DB = "outputs/alerts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT,
    camera       TEXT,
    started_at   TEXT,     -- wall-clock start (ISO), if the video start time is known
    start_s      REAL,     -- seconds from the start of the video
    end_s        REAL,
    duration_s   REAL,
    start_frame  INTEGER,
    end_frame    INTEGER,
    peak_score   REAL,
    peak_level   TEXT,
    top_factor   TEXT,
    max_count    INTEGER,
    status       TEXT,     -- 'active' or 'closed'
    logged_at    TEXT DEFAULT (datetime('now', 'localtime'))
)
"""

# Added later; missing from older databases, so they are added on open and are NULL for old rows.
EXTRA_COLUMNS = {
    "max_speed": "REAL",          # fastest bird during the episode (frame diagonals / s)
    "min_dist": "REAL",           # nearest any bird came to a zone (frame diagonals; 0 = inside)
    "c_count": "REAL",            # weighted factor contributions at the episode's peak frame
    "c_speed": "REAL",
    "c_proximity": "REAL",
    "c_flock_size": "REAL",
    "c_time_of_day": "REAL",
}

FIELDS = ["source", "camera", "started_at", "start_s", "end_s", "duration_s", "start_frame",
          "end_frame", "peak_score", "peak_level", "top_factor", "max_count", "status", *EXTRA_COLUMNS]


class AlertLog:
    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute(SCHEMA)
        have = {row[1] for row in self.conn.execute("PRAGMA table_info(alerts)")}
        for name, kind in EXTRA_COLUMNS.items():
            if name not in have:
                self.conn.execute(f"ALTER TABLE alerts ADD COLUMN {name} {kind}")
        self.conn.commit()

    def upsert(self, episode: dict, alert_id: int | None = None) -> int:
        """Insert a new alert, or update the one with `alert_id`. Returns the id."""
        values = [episode.get(f) for f in FIELDS]
        if alert_id is None:
            cur = self.conn.execute(
                f"INSERT INTO alerts ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})", values)
            alert_id = cur.lastrowid
        else:
            self.conn.execute(
                f"UPDATE alerts SET {', '.join(f'{f} = ?' for f in FIELDS)} WHERE id = ?", values + [alert_id])
        self.conn.commit()
        return alert_id

    def recent(self, limit: int = 50) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", self.conn, params=(limit,))

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
