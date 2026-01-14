from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
import sqlite3
from .db import connect, init_db


def iso_utc_now() -> str:
    """
    Return the current time in ISO 8601 format (UTC), seconds precision.
    Useful for consistent logging timestamps.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------
# SQL to compute and store yearly stats
# ------------------------------------------------------------
# Key points:
# - Year is extracted from obs_date, which is stored as 'YYYY-MM-DD' text.
#   substr(obs_date, 1, 4) -> 'YYYY'
# - Unit conversions:
#   * max_temp_tenth_c / 10.0  -> degrees Celsius
#   * min_temp_tenth_c / 10.0  -> degrees Celsius
#   * precip_tenth_mm / 100.0  -> centimeters
STATS_UPSERT_SQL = """
INSERT INTO weather_yearly_stats (
  station_id, year, avg_max_temp_c, avg_min_temp_c, total_precip_cm
)
SELECT
  station_id,
  CAST(substr(obs_date, 1, 4) AS INTEGER) AS year,

  -- Temperatures stored in tenths of °C -> convert to °C
  ROUND(AVG(max_temp_tenth_c) / 10.0, 2) AS avg_max_temp_c,
  ROUND(AVG(min_temp_tenth_c) / 10.0, 2) AS avg_min_temp_c,

  -- Precip stored in tenths of mm -> convert to cm
  ROUND(SUM(precip_tenth_mm) / 100.0, 2) AS total_precip_cm

FROM weather_observation
GROUP BY station_id, CAST(substr(obs_date, 1, 4) AS INTEGER)

ON CONFLICT(station_id, year) DO UPDATE SET
  avg_max_temp_c  = excluded.avg_max_temp_c,
  avg_min_temp_c  = excluded.avg_min_temp_c,
  total_precip_cm = excluded.total_precip_cm;
"""


def calculate_and_store(conn: sqlite3.Connection) -> int:
    """
    Calculate yearly station statistics and store them in weather_yearly_stats.

    Returns:
        int: number of rows inserted/updated (as measured by SQLite total_changes).
    """
    start = iso_utc_now()
    logging.info("Stats calc started at %s", start)

    #---------- total_changes counts inserts + updates; we snapshot before and after
    before = conn.total_changes

    #---------- Execute as a single SQL statement
    conn.execute(STATS_UPSERT_SQL)
    conn.commit()

    changed = conn.total_changes - before

    end = iso_utc_now()
    logging.info("Stats calc finished at %s. Rows inserted/updated=%d", end, changed)
    return changed


def main() -> None:
    """
    CLI entry point.

    Example:
        python -m src.calc_stats --db weather.db
    """
    parser = argparse.ArgumentParser(description="Compute yearly weather stats per station.")
    parser.add_argument("--db", default="weather.db", help="Path to SQLite database file")
    args = parser.parse_args()

    #---------- Basic structured logging for interview-style visibility
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    #---------- Connect to SQLite and ensure schema exists
    conn = connect(args.db)
    init_db(conn)

    #---------- Compute and store stats
    calculate_and_store(conn)


if __name__ == "__main__":
    main()
