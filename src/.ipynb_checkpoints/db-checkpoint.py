from __future__ import annotations

import sqlite3
from pathlib import Path

#--------- SQL schema (tables + indexes)
SCHEMA_SQL = """
-- Daily weather data (one row per station per day)
CREATE TABLE IF NOT EXISTS weather_observation (
  station_id TEXT NOT NULL,          -- station id (from filename)
  obs_date   TEXT NOT NULL,          -- date 'YYYY-MM-DD'
  max_temp_tenth_c INTEGER NULL,     -- max temp (0.1°C); NULL if missing
  min_temp_tenth_c INTEGER NULL,     -- min temp (0.1°C); NULL if missing
  precip_tenth_mm  INTEGER NULL,     -- precip (0.1 mm); NULL if missing
  PRIMARY KEY (station_id, obs_date) -- prevents duplicates
);

-- Speeds up date range queries
CREATE INDEX IF NOT EXISTS idx_weather_obs_date
  ON weather_observation (obs_date);

-- Speeds up station + date queries
CREATE INDEX IF NOT EXISTS idx_weather_obs_station_date
  ON weather_observation (station_id, obs_date);

-- Tracks ingestion runs (start/end + counts)
CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at    TEXT NOT NULL,
  finished_at   TEXT NULL,
  station_id    TEXT NULL,
  rows_seen     INTEGER NOT NULL DEFAULT 0,
  rows_written  INTEGER NOT NULL DEFAULT 0
);

-- Yearly stats (one row per station per year)
CREATE TABLE IF NOT EXISTS weather_yearly_stats (
  station_id TEXT NOT NULL,
  year       INTEGER NOT NULL,
  avg_max_temp_c  REAL NULL,         -- °C
  avg_min_temp_c  REAL NULL,         -- °C
  total_precip_cm REAL NULL,         -- cm
  PRIMARY KEY (station_id, year)
);

-- Speeds up stats filtering
CREATE INDEX IF NOT EXISTS idx_stats_station_year
  ON weather_yearly_stats (station_id, year);
"""

def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection and set a few performance pragmas."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    """Create tables/indexes if they don't exist."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
