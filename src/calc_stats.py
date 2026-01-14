from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
import sqlite3

from .db import connect, init_db

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

STATS_UPSERT_SQL = """
INSERT INTO weather_yearly_stats (
  station_id, year, avg_max_temp_c, avg_min_temp_c, total_precip_cm
)
SELECT
  station_id,
  CAST(substr(obs_date, 1, 4) AS INTEGER) AS year,
  ROUND(AVG(max_temp_tenth_c) / 10.0, 2) AS avg_max_temp_c,
  ROUND(AVG(min_temp_tenth_c) / 10.0, 2) AS avg_min_temp_c,
  ROUND(SUM(precip_tenth_mm) / 100.0, 2) AS total_precip_cm
FROM weather_observation
GROUP BY station_id, CAST(substr(obs_date, 1, 4) AS INTEGER)
ON CONFLICT(station_id, year) DO UPDATE SET
  avg_max_temp_c  = excluded.avg_max_temp_c,
  avg_min_temp_c  = excluded.avg_min_temp_c,
  total_precip_cm = excluded.total_precip_cm;
"""

def calculate_and_store(conn: sqlite3.Connection) -> int:
    start = iso_utc_now()
    logging.info("Stats calc started at %s", start)

    before = conn.total_changes
    conn.execute(STATS_UPSERT_SQL)
    conn.commit()
    changed = conn.total_changes - before

    end = iso_utc_now()
    logging.info("Stats calc finished at %s. Rows inserted/updated=%d", end, changed)
    return changed

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="weather.db")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = connect(args.db)
    init_db(conn)
    calculate_and_store(conn)

if __name__ == "__main__":
    main()
