# code-challenge-solutions

## Setup
pip install -r requirements.txt

## Initialize + Ingest
python -m src.ingest --data-dir ./wx_data --db weather.db

## Compute yearly stats
python -m src.calc_stats --db weather.db

## Run API
uvicorn src.api:app --reload

## API Docs
http://127.0.0.1:8000/docs

## Run tests
pytest -q
