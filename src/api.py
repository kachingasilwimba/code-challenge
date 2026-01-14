from __future__ import annotations

from fastapi import FastAPI, Query, Depends
from pydantic import BaseModel
import sqlite3
from pathlib import Path
from typing import Optional

from .db import connect, init_db

DEFAULT_DB = Path("weather.db")

app = FastAPI(title="Weather API", version="1.0.0")

def get_conn() -> sqlite3.Connection:
    conn = connect(DEFAULT_DB)
    init_db(conn)
    return conn

class WeatherRow(BaseModel):
    station_id: str
    obs_date: str
    max_temp_tenth_c: Optional[int] = None
    min_temp_tenth_c: Optional[int] = None
    precip_tenth_mm: Optional[int] = None

class StatsRow(BaseModel):
    station_id: str
    year: int
    avg_max_temp_c: Optional[float] = None
    avg_min_temp_c: Optional[float] = None
    total_precip_cm: Optional[float] = None

def paginate(limit: int, offset: int) -> tuple[int, int]:
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    return limit, offset

@app.get("/api/weather")
def get_weather(
    station_id: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_conn),
):
    limit, offset = paginate(limit, offset)

    where = []
    params = []

    if station_id:
        where.append("station_id = ?")
        params.append(station_id)
    if date_from:
        where.append("obs_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("obs_date <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_sql = f"SELECT COUNT(*) AS n FROM weather_observation {where_sql}"
    total = conn.execute(count_sql, params).fetchone()["n"]

    data_sql = f"""
      SELECT station_id, obs_date, max_temp_tenth_c, min_temp_tenth_c, precip_tenth_mm
      FROM weather_observation
      {where_sql}
      ORDER BY station_id, obs_date
      LIMIT ? OFFSET ?
    """
    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
    results = [WeatherRow(**dict(r)).model_dump() for r in rows]

    return {"count": total, "limit": limit, "offset": offset, "results": results}

@app.get("/api/weather/stats")
def get_stats(
    station_id: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_conn),
):
    limit, offset = paginate(limit, offset)

    where = []
    params = []

    if station_id:
        where.append("station_id = ?")
        params.append(station_id)
    if year is not None:
        where.append("year = ?")
        params.append(year)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_sql = f"SELECT COUNT(*) AS n FROM weather_yearly_stats {where_sql}"
    total = conn.execute(count_sql, params).fetchone()["n"]

    data_sql = f"""
      SELECT station_id, year, avg_max_temp_c, avg_min_temp_c, total_precip_cm
      FROM weather_yearly_stats
      {where_sql}
      ORDER BY station_id, year
      LIMIT ? OFFSET ?
    """
    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
    results = [StatsRow(**dict(r)).model_dump() for r in rows]

    return {"count": total, "limit": limit, "offset": offset, "results": results}
