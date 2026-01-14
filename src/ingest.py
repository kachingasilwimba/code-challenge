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
  precip_tenth_mm  = excluded.precip_tenth_mm;
"""

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def to_int_or_none(s: str) -> int | None:
    v = int(s)
    return None if v == -9999 else v

def yyyymmdd_to_iso(d: str) -> str:
    # '19850101' -> '1985-01-01'
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"

def ingest_station_file(conn: sqlite3.Connection, file_path: Path, batch_size: int = 5000) -> tuple[int, int]:
    station_id = file_path.stem
    started_at = iso_utc_now()
    cur = conn.cursor()

    # log run start
    cur.execute("INSERT INTO ingest_run (started_at, station_id) VALUES (?, ?)", (started_at, station_id))
    run_id = cur.lastrowid

    rows_seen = 0
    total_changes_before = conn.total_changes
    batch: list[tuple] = []

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) != 4:
                raise ValueError(f"Bad line in {file_path.name}: {line[:120]}")

            d, mx, mn, pr = parts
            batch.append((
                station_id,
                yyyymmdd_to_iso(d),
                to_int_or_none(mx),
                to_int_or_none(mn),
                to_int_or_none(pr),
            ))
            rows_seen += 1

            if len(batch) >= batch_size:
                cur.executemany(UPSERT_SQL, batch)
                batch.clear()

    if batch:
        cur.executemany(UPSERT_SQL, batch)

    conn.commit()
    rows_written = conn.total_changes - total_changes_before

    finished_at = iso_utc_now()
    cur.execute(
        "UPDATE ingest_run SET finished_at=?, rows_seen=?, rows_written=? WHERE run_id=?",
        (finished_at, rows_seen, rows_written, run_id),
    )
    conn.commit()
    return rows_seen, rows_written

def ingest_all(conn: sqlite3.Connection, data_dir: Path) -> tuple[int, int, int]:
    files = sorted(data_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found in {data_dir}")

    start = iso_utc_now()
    logging.info("Ingestion started at %s. Files=%d dir=%s", start, len(files), data_dir)

    total_seen = 0
    total_written = 0

    for i, fp in enumerate(files, 1):
        seen, written = ingest_station_file(conn, fp)
        total_seen += seen
        total_written += written
        if i % 25 == 0 or i == len(files):
            logging.info("[%d/%d] %s seen=%d written=%d", i, len(files), fp.name, seen, written)

    end = iso_utc_now()
    logging.info("Ingestion finished at %s. Total seen=%d total written=%d", end, total_seen, total_written)
    return len(files), total_seen, total_written

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Path to wx_data directory")
    parser.add_argument("--db", default="weather.db", help="SQLite db path (default: weather.db)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    data_dir = Path(args.data_dir)
    conn = connect(args.db)
    init_db(conn)

    ingest_all(conn, data_dir)

if __name__ == "__main__":
    main()
