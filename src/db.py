from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS weather_observation (
  station_id TEXT NOT NULL,
  obs_date   TEXT NOT NULL,
  max_temp_tenth_c INTEGER NULL,
  min_temp_tenth_c INTEGER NULL,
  precip_tenth_mm  INTEGER NULL,
  PRIMARY KEY (station_id, obs_date)
);

CREATE INDEX IF NOT EXISTS idx_weather_obs_date
  ON weather_observation (obs_date);

CREATE INDEX IF NOT EXISTS idx_weather_obs_station_date
  ON weather_observation (station_id, obs_date);

CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at    TEXT NOT NULL,
  finished_at   TEXT NULL,
  station_id    TEXT NULL,
  rows_seen     INTEGER NOT NULL DEFAULT 0,
  rows_written  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weather_yearly_stats (
  station_id TEXT NOT NULL,
  year       INTEGER NOT NULL,
  avg_max_temp_c  REAL NULL,
  avg_min_temp_c  REAL NULL,
  total_precip_cm REAL NULL,
  PRIMARY KEY (station_id, year)
);

CREATE INDEX IF NOT EXISTS idx_stats_station_year
  ON weather_yearly_stats (station_id, year);
"""

def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
