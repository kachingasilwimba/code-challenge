from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from .db import connect, init_db

UPSERT_SQL = """
INSERT INTO weather_observation (
  station_id, obs_date, max_temp_tenth_c, min_temp_tenth_c, precip_tenth_mm
)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(station_id, obs_date) DO UPDATE SET
  max_temp_tenth_c = excluded.max_temp_tenth_c,
  min_temp_tenth_c = excluded.min_temp_tenth_c,
  precip_tenth_mm  = excluded.precip_tenth_mm
WHERE
  weather_observation.max_temp_tenth_c IS NOT excluded.max_temp_tenth_c
  OR weather_observation.min_temp_tenth_c IS NOT excluded.min_temp_tenth_c
  OR weather_observation.precip_tenth_mm  IS NOT excluded.precip_tenth_mm;
"""

def iso_utc_now() -> str:
    """
    Return current time in ISO format (UTC), seconds precision.
    Used for consistent logging + ingest_run timestamps.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_int_or_none(s: str) -> int | None:
    """
    Convert a numeric string from the file into an int, but translate the
    missing-value sentinel (-9999) into None (NULL in SQLite).
    """
    v = int(s)
    return None if v == -9999 else v


def yyyymmdd_to_iso(d: str) -> str:
    """
    Convert raw date string from file:
      '19850101' -> '1985-01-01'
    Storing ISO date text keeps filtering/sorting simple in SQLite.
    """
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def ingest_station_file(
    conn: sqlite3.Connection,
    file_path: Path,
    batch_size: int = 5000,
) -> tuple[int, int]:
    """
    Ingest one station file into weather_observation.

    Args:
        conn: open sqlite3 connection
        file_path: path to a single station .txt file
        batch_size: number of rows to insert per executemany batch

    Returns:
        (rows_seen, rows_written)
        - rows_seen: number of valid lines parsed
        - rows_written: number of inserts/updates applied
    """
    station_id = file_path.stem 
    started_at = iso_utc_now()
    cur = conn.cursor()

    #---------- Insert an ingestion-run record so we can audit per-file results
    cur.execute(
        "INSERT INTO ingest_run (started_at, station_id) VALUES (?, ?)",
        (started_at, station_id),
    )
    run_id = cur.lastrowid

    rows_seen = 0
    total_changes_before = conn.total_changes
    batch: list[tuple] = []

    #---------- Read and parse the file line-by-line
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                #---------- Skip blank lines safely
                continue

            parts = line.split("\t")
            if len(parts) != 4:
                raise ValueError(f"Bad line in {file_path.name}: {line[:120]}")

            d, mx, mn, pr = parts

            # Build a row tuple, converting:
            #  - date YYYYMMDD -> ISO YYYY-MM-DD
            #  - -9999 -> None (NULL)
            batch.append(
                (
                    station_id,
                    yyyymmdd_to_iso(d),
                    to_int_or_none(mx),
                    to_int_or_none(mn),
                    to_int_or_none(pr),
                )
            )
            rows_seen += 1

            #---------- Insert in batches for performance
            if len(batch) >= batch_size:
                cur.executemany(UPSERT_SQL, batch)
                batch.clear()

    #---------- Insert any remaining rows not flushed in the loop
    if batch:
        cur.executemany(UPSERT_SQL, batch)

    conn.commit()

    #---------- SQLite total_changes counts inserts + updates (within this connection)
    rows_written = conn.total_changes - total_changes_before

    #---------- Finalize ingest_run row with end time + counts
    finished_at = iso_utc_now()
    cur.execute(
        "UPDATE ingest_run SET finished_at=?, rows_seen=?, rows_written=? WHERE run_id=?",
        (finished_at, rows_seen, rows_written, run_id),
    )
    conn.commit()

    return rows_seen, rows_written


def ingest_all(conn: sqlite3.Connection, data_dir: Path) -> tuple[int, int, int]:
    """
    Ingest all station files in a directory.

    Args:
        conn: open sqlite3 connection
        data_dir: directory containing station .txt files (wx_data)

    Returns:
        (num_files, total_seen, total_written)
    """
    files = sorted(data_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found in {data_dir}")

    start = iso_utc_now()
    logging.info(
        "Ingestion started at %s. Files=%d dir=%s",
        start,
        len(files),
        data_dir,
    )

    total_seen = 0
    total_written = 0

    #---------- Loop through all station files
    for i, fp in enumerate(files, 1):
        seen, written = ingest_station_file(conn, fp)
        total_seen += seen
        total_written += written

        #---------- Progress logs every 25 files (and at the end)
        if i % 25 == 0 or i == len(files):
            logging.info(
                "[%d/%d] %s seen=%d written=%d",
                i,
                len(files),
                fp.name,
                seen,
                written,
            )

    end = iso_utc_now()
    logging.info(
        "Ingestion finished at %s. Total seen=%d total written=%d",
        end,
        total_seen,
        total_written,
    )

    return len(files), total_seen, total_written


def main() -> None:
    """
    CLI entry point.
    """
    parser = argparse.ArgumentParser(description="Ingest weather station files into SQLite.")
    parser.add_argument("--data-dir", required=True, help="Path to wx_data directory")
    parser.add_argument("--db", default="weather.db", help="SQLite db path (default: weather.db)")
    args = parser.parse_args()

    #---------- Basic structured logging for interview-style visibility
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    data_dir = Path(args.data_dir)

    #---------- Connect + ensure schema exists
    conn = connect(args.db)
    init_db(conn)

    #---------- Ingest all files in the directory
    ingest_all(conn, data_dir)


if __name__ == "__main__":
    main()
