from __future__ import annotations

from fastapi import FastAPI, Query, Depends, HTTPException
from pydantic import BaseModel
import sqlite3
import os
from pathlib import Path
from typing import Optional
from .db import connect, init_db

## Plot
from fastapi.responses import StreamingResponse
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import Literal
from datetime import date, timedelta


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

# ------------------------------------------------------------
# Endpoint: /api/weather/stats/plots
# Returns computed yearly statistics.
# Filters:
#  - station_id
#  - year
# Pagination:
#  - limit, offset
# ------------------------------------------------------------
@app.get("/api/weather/plot")
def plot_weather(
    station_id: str = Query(..., description="Station ID (required)"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (required for daily)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (required for daily)"),
    granularity: Literal["monthly", "yearly", "daily"] = Query(
        "monthly", description="monthly (fast), yearly (fast), daily (slow unless range is small)"
    ),
    metric: Literal["temperature", "precip", "both"] = Query(
        "temperature", description="temperature, precip, or both (precip uses right axis)"
    ),
    max_points: int = Query(2000, ge=100, le=20000, description="Only used for daily plots"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """
    Returns a PNG plot.

    Performance choices:
      - Default granularity is monthly (fast).
      - yearly is very fast.
      - daily requires date_from & date_to and is downsampled to max_points.
    """

    #------------ Helper to build optional date filters
    where = ["station_id = ?"]
    params: list = [station_id]

    #------------ For daily, require a date range so we don't plot millions of points
    if granularity == "daily":
        if not date_from or not date_to:
            raise HTTPException(status_code=400, detail="date_from and date_to are required for granularity=daily")
    else:
        # If user doesn't provide dates for monthly/yearly, optionally default to "all time".
        # If you prefer a default window, uncomment below:
        # if not date_from or not date_to:
        #     end = date.today()
        #     start = end - timedelta(days=365 * 5)
        #     date_from = start.isoformat()
        #     date_to = end.isoformat()
        pass

    if date_from:
        where.append("obs_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("obs_date <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where)

    if granularity == "daily":
        rows = conn.execute(
            f"""
            SELECT obs_date AS period,
                   max_temp_tenth_c,
                   min_temp_tenth_c,
                   precip_tenth_mm
            FROM weather_observation
            WHERE {where_sql}
            ORDER BY obs_date
            """,
            params,
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No data found for given filters")

        n = len(rows)
        step = max(1, n // max_points)
        rows = rows[::step]

        periods = [r["period"] for r in rows]
        tmax = [(r["max_temp_tenth_c"] / 10.0) if r["max_temp_tenth_c"] is not None else None for r in rows]
        tmin = [(r["min_temp_tenth_c"] / 10.0) if r["min_temp_tenth_c"] is not None else None for r in rows]
        precip = [(r["precip_tenth_mm"] / 100.0) if r["precip_tenth_mm"] is not None else None for r in rows]  # cm

        title_suffix = f"Daily (downsample step={step})"

    elif granularity == "monthly":
        rows = conn.execute(
            f"""
            SELECT substr(obs_date, 1, 7) AS period,         -- YYYY-MM
                   AVG(max_temp_tenth_c)/10.0 AS avg_tmax_c,
                   AVG(min_temp_tenth_c)/10.0 AS avg_tmin_c,
                   SUM(precip_tenth_mm)/100.0 AS total_precip_cm
            FROM weather_observation
            WHERE {where_sql}
            GROUP BY substr(obs_date, 1, 7)
            ORDER BY period
            """,
            params,
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No data found for given filters")

        periods = [r["period"] for r in rows]
        tmax = [r["avg_tmax_c"] for r in rows]
        tmin = [r["avg_tmin_c"] for r in rows]
        precip = [r["total_precip_cm"] for r in rows]

        title_suffix = "Monthly"

    else:  #------------ yearly
        rows = conn.execute(
            f"""
            SELECT substr(obs_date, 1, 4) AS period,         -- YYYY
                   AVG(max_temp_tenth_c)/10.0 AS avg_tmax_c,
                   AVG(min_temp_tenth_c)/10.0 AS avg_tmin_c,
                   SUM(precip_tenth_mm)/100.0 AS total_precip_cm
            FROM weather_observation
            WHERE {where_sql}
            GROUP BY substr(obs_date, 1, 4)
            ORDER BY period
            """,
            params,
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No data found for given filters")

        periods = [r["period"] for r in rows]
        tmax = [r["avg_tmax_c"] for r in rows]
        tmin = [r["avg_tmin_c"] for r in rows]
        precip = [r["total_precip_cm"] for r in rows]

        title_suffix = "Yearly"

    fig, ax1 = plt.subplots()

    if metric in ("temperature", "both"):
        ax1.plot(periods, tmax, label="Tmax (°C)",linewidth=3,marker ="o",markersize=6)
        ax1.plot(periods, tmin, label="Tmin (°C)",linestyle='dashdot', linewidth=3)
        ax1.set_ylabel("Temperature (°C)")

    ax2 = None
    if metric in ("precip", "both"):
        ax2 = ax1.twinx()
        ax2.plot(periods, precip, label="Precip (cm)")
        ax2.set_ylabel("Precipitation (cm)")

    ax1.set_title(f"Station {station_id} — {title_suffix}")
    ax1.set_xlabel("Period")
    ax1.minorticks_on()

    if len(periods) > 12:
        tick_step = max(1, len(periods) // 10)
        ax1.set_xticks(ax1.get_xticks()[::1])
    fig.autofmt_xdate()

    handles, labels = ax1.get_legend_handles_labels()
    if ax2 is not None:
        h2, l2 = ax2.get_legend_handles_labels()
        handles += h2
        labels += l2
    ax1.legend(handles, labels, loc="best")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
