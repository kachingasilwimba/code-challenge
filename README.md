# Weather Data Engineering Coding Exercise

This repository contains the weather data engineering coding exercise implementations:

- **Problem 1 – Data Modeling:** SQLite schema for raw observations, ingestion audit, and yearly stats  
- **Problem 2 – Ingestion:** Script to ingest raw station text files into SQLite with duplicate protection and logging  
- **Problem 3 – Data Analysis:** Script to compute yearly station statistics and store results in the database  
- **Problem 4 – REST API:** FastAPI service exposing raw observations and yearly stats with filtering, pagination, and Swagger/OpenAPI docs  
- **Unit tests:** Basic tests for the API endpoints using `pytest`

## Extra: Stats Plots (Optional)

In addition to the required JSON endpoints, the API includes an optional PNG plot endpoint for quick visualization.

### Endpoint
`GET /api/weather/plot`

### Query Parameters
- `station_id` (required): Station ID (e.g., `USC00110072`)
- `granularity` (optional): `monthly` (default), `yearly`, or `daily`
- `metric` (optional): `temperature` (default), `precip`, or `both`
- `date_from` / `date_to` (optional): `YYYY-MM-DD`
  - Required when `granularity=daily` (to avoid plotting too many points)
- `max_points` (optional): used only for `granularity=daily` (default `2000`) to downsample large ranges

----
## Quickstart 

**Setup:**

``git clone git@github.com:kachingasilwimba/code-challenge.git``

``pip install -r requirements.txt``

**Initialize + Ingest (Problem 2):**
``python -m src.ingest --data-dir ./wx_data --db weather.db``

**Compute yearly stats (Problem 3):**
``python -m src.calc_stats --db weather.db``

**Run API (Problem 4):**
``WEATHER_DB_PATH="$(pwd)/weather.db" uvicorn src.api:app --reload --port 8000``

**API Docs:**
``http://127.0.0.1:8000/docs``

**Run tests:**
``pytest -q``
