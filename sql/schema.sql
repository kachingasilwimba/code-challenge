CREATE TABLE IF NOT EXISTS weather_observation (
  station_id TEXT NOT NULL,
  obs_date   TEXT NOT NULL,          -- ISO date: 'YYYY-MM-DD'
  max_temp_tenth_c INTEGER NULL,
  min_temp_tenth_c INTEGER NULL,
  precip_tenth_mm  INTEGER NULL,
  PRIMARY KEY (station_id, obs_date)
);

CREATE INDEX IF NOT EXISTS idx_weather_obs_date
  ON weather_observation (obs_date);

CREATE INDEX IF NOT EXISTS idx_weather_obs_station_date
  ON weather_observation (station_id, obs_date);
  
  
CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at    TEXT NOT NULL,
  finished_at   TEXT NULL,
  station_id    TEXT NULL,
  rows_seen     INTEGER NOT NULL DEFAULT 0,
  rows_written  INTEGER NOT NULL DEFAULT 0
);


CREATE TABLE IF NOT EXISTS weather_yearly_stats (
  station_id TEXT NOT NULL,
  year       INTEGER NOT NULL,
  avg_max_temp_c  REAL NULL,
  avg_min_temp_c  REAL NULL,
  total_precip_cm REAL NULL,
  PRIMARY KEY (station_id, year)
);

CREATE INDEX IF NOT EXISTS idx_stats_station_year
  ON weather_yearly_stats (station_id, year);

