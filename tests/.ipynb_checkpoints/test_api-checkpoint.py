from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import src.api as api
from src.db import init_db

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_weather.db"

@pytest.fixture()
def client(tmp_db: Path) -> TestClient:
    # Patch API to use temp DB for tests
    api.DEFAULT_DB = tmp_db

    # Seed DB
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    conn.execute("""
        INSERT INTO weather_observation (station_id, obs_date, max_temp_tenth_c, min_temp_tenth_c, precip_tenth_mm)
        VALUES
          ('STATION1', '1985-01-01', 100,  0,  10),
          ('STATION1', '1985-01-02', NULL, 10, NULL),
          ('STATION2', '1985-01-01', 50,  -50, 0)
        ON CONFLICT(station_id, obs_date) DO UPDATE SET
          max_temp_tenth_c=excluded.max_temp_tenth_c,
          min_temp_tenth_c=excluded.min_temp_tenth_c,
          precip_tenth_mm=excluded.precip_tenth_mm;
    """)
    conn.execute("""
        INSERT INTO weather_yearly_stats (station_id, year, avg_max_temp_c, avg_min_temp_c, total_precip_cm)
        VALUES
          ('STATION1', 1985, 10.0, 1.0, 0.10),
          ('STATION2', 1985, 5.0, -5.0, 0.00)
        ON CONFLICT(station_id, year) DO UPDATE SET
          avg_max_temp_c=excluded.avg_max_temp_c,
          avg_min_temp_c=excluded.avg_min_temp_c,
          total_precip_cm=excluded.total_precip_cm;
    """)
    conn.commit()
    conn.close()

    return TestClient(api.app)

def test_weather_endpoint_basic(client: TestClient):
    r = client.get("/api/weather?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert len(body["results"]) == 2

def test_weather_filter_station_and_date(client: TestClient):
    r = client.get("/api/weather?station_id=STATION1&date_from=1985-01-02&date_to=1985-01-02")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["results"][0]["obs_date"] == "1985-01-02"

def test_stats_endpoint_filter(client: TestClient):
    r = client.get("/api/weather/stats?station_id=STATION2")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["results"][0]["station_id"] == "STATION2"
