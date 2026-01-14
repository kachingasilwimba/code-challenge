from __future__ import annotations

from fastapi import FastAPI, Query, Depends
from pydantic import BaseModel
import sqlite3
import os
from pathlib import Path
from typing import Optional
from .db import connect, init_db


# ------------------------------------------------------------
# Database path configuration
# ------------------------------------------------------------
DEFAULT_DB = Path(os.environ.get("WEATHER_DB_PATH", "weather.db"))


# ------------------------------------------------------------
# FastAPI application instance
# ------------------------------------------------------------
# OpenAPI/Swagger endpoints are automatically provided by FastAPI:
# - Swagger UI: /docs
# - OpenAPI JSON: /openapi.json
app = FastAPI(title="Weather API", version="1.0.0")


# ------------------------------------------------------------
# Dependency: get a database connection for each request
# ------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    """
    Create and return a SQLite database connection for the current request.

    We also call init_db() here so the app is self-initializing:
    - If the DB file doesn't exist, it will be created.
    - If tables/indexes are missing, they will be created.

    Note: In a larger production service, you'd typically use a connection pool
    and close connections after each request. For SQLite + this exercise, this
    is acceptable and keeps setup simple.
    """
    conn = connect(DEFAULT_DB)
    init_db(conn)
    return conn


# ------------------------------------------------------------
# Pydantic models (schemas) for output rows
# ------------------------------------------------------------
class WeatherRow(BaseModel):
    """
    Represents one daily weather observation row from weather_observation.

    Units are stored in "raw" units from the input files:
    - max_temp_tenth_c: tenths of degrees Celsius
    - min_temp_tenth_c: tenths of degrees Celsius
    - precip_tenth_mm: tenths of millimeters

    Missing values are stored as NULL in the DB and appear as None in Python.
    """
    station_id: str
    obs_date: str
    max_temp_tenth_c: Optional[int] = None
    min_temp_tenth_c: Optional[int] = None
    precip_tenth_mm: Optional[int] = None


class StatsRow(BaseModel):
    """
    Represents one yearly stats row from weather_yearly_stats.

    Units are derived:
    - avg_max_temp_c: degrees Celsius (°C)
    - avg_min_temp_c: degrees Celsius (°C)
    - total_precip_cm: centimeters (cm)

    Missing stats are returned as None (NULL in the DB).
    """
    station_id: str
    year: int
    avg_max_temp_c: Optional[float] = None
    avg_min_temp_c: Optional[float] = None
    total_precip_cm: Optional[float] = None


# ------------------------------------------------------------
# Pagination helper
# ------------------------------------------------------------
def paginate(limit: int, offset: int) -> tuple[int, int]:
    """
    Enforce safe bounds on pagination parameters.

    - limit: number of records to return (cap at 1000)
    - offset: number of records to skip (must be >= 0)
    """
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    return limit, offset


# ------------------------------------------------------------
# Endpoint: /api/weather
# Returns ingested daily observations.
# Filters:
#  - station_id
#  - date_from (YYYY-MM-DD)
#  - date_to (YYYY-MM-DD)
# Pagination:
#  - limit, offset
# ------------------------------------------------------------
@app.get("/api/weather")
def get_weather(
    station_id: Optional[str] = Query(default=None, description="Station ID (e.g., USC00110072)"),
    date_from: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Records to skip (pagination offset)"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    #--------- Normalize pagination inputs
    limit, offset = paginate(limit, offset)

    #--------- Build WHERE clauses dynamically
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

    #--------- Count query
    count_sql = f"SELECT COUNT(*) AS n FROM weather_observation {where_sql}"
    total = conn.execute(count_sql, params).fetchone()["n"]

    #--------- Data query
    data_sql = f"""
      SELECT station_id, obs_date, max_temp_tenth_c, min_temp_tenth_c, precip_tenth_mm
      FROM weather_observation
      {where_sql}
      ORDER BY station_id, obs_date
      LIMIT ? OFFSET ?
    """
    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

    #--------- Convert sqlite3.Row -> dict -> pydantic model -> dict for JSON response
    results = [WeatherRow(**dict(r)).model_dump() for r in rows]

    return {"count": total, "limit": limit, "offset": offset, "results": results}


# ------------------------------------------------------------
# Endpoint: /api/weather/stats
# Returns computed yearly statistics.
# Filters:
#  - station_id
#  - year
# Pagination:
#  - limit, offset
# ------------------------------------------------------------
@app.get("/api/weather/stats")
def get_stats(
    station_id: Optional[str] = Query(default=None, description="Station ID (e.g., USC00110072)"),
    year: Optional[int] = Query(default=None, description="4-digit year (e.g., 1985)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Records to skip (pagination offset)"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    #--------- Normalize pagination inputs
    limit, offset = paginate(limit, offset)

    #--------- Build WHERE clauses dynamically
    where = []
    params = []

    if station_id:
        where.append("station_id = ?")
        params.append(station_id)

    if year is not None:
        where.append("year = ?")
        params.append(year)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    #--------- Count query for pagination metadata
    count_sql = f"SELECT COUNT(*) AS n FROM weather_yearly_stats {where_sql}"
    total = conn.execute(count_sql, params).fetchone()["n"]

    #--------- Data query
    data_sql = f"""
      SELECT station_id, year, avg_max_temp_c, avg_min_temp_c, total_precip_cm
      FROM weather_yearly_stats
      {where_sql}
      ORDER BY station_id, year
      LIMIT ? OFFSET ?
    """
    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

    #--------- Convert sqlite3.Row -> dict -> pydantic model -> dict for JSON response
    results = [StatsRow(**dict(r)).model_dump() for r in rows]

    return {"count": total, "limit": limit, "offset": offset, "results": results}
