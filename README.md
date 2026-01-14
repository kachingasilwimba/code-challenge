# Weather Data Engineering Coding Exercise (SQLite + FastAPI)

This repository contains my solution to the weather data engineering coding exercise.

It implements:

- **Problem 1 – Data Modeling:** SQLite schema for raw observations, ingestion audit, and yearly stats  
- **Problem 2 – Ingestion:** Script to ingest raw station text files into SQLite with duplicate protection and logging  
- **Problem 3 – Data Analysis:** Script to compute yearly station statistics and store results in the database  
- **Problem 4 – REST API:** FastAPI service exposing raw observations and yearly stats with filtering, pagination, and Swagger/OpenAPI docs  
- **Unit tests:** Basic tests for the API endpoints using `pytest`

----
## Quickstart 
**Setup:**
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
