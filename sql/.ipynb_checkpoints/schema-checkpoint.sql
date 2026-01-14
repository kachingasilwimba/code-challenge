-- ============================================
-- Weather data schema
-- ============================================
-- Notes:
--  - Raw data is ingested from wx_data/*.txt files.
--  - Missing values in the raw files (-9999) should be converted to NULL in ingestion.
--  - We store temperatures and precipitation in the same units provided by the source
--    to avoid rounding/float issues during ingestion.
-- ============================================


-- ------------------------------------------------
-- Table: weather_observation
-- One row per (station_id, date).
-- station_id is derived from the input filename.
-- obs_date is stored as ISO date text: 'YYYY-MM-DD' for easy filtering and sorting.
--
-- Units (raw):
--   - max_temp_tenth_c: max temperature in tenths of degrees Celsius
--   - min_temp_tenth_c: min temperature in tenths of degrees Celsius
--   - precip_tenth_mm: precipitation in tenths of millimeters
-- ------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_observation (
  station_id TEXT NOT NULL,                 
  obs_date   TEXT NOT NULL,                 

  max_temp_tenth_c INTEGER NULL,            
  min_temp_tenth_c INTEGER NULL,           
  precip_tenth_mm  INTEGER NULL,            

  -- Composite primary key ensures uniqueness: no duplicate rows for the same station/day.
  PRIMARY KEY (station_id, obs_date)
);

-- Index to speed up date-range queries and pagination across dates.
CREATE INDEX IF NOT EXISTS idx_weather_obs_date
  ON weather_observation (obs_date);

-- Index to speed up queries that filter by station and then by date range.
CREATE INDEX IF NOT EXISTS idx_weather_obs_station_date
  ON weather_observation (station_id, obs_date);


-- ------------------------------------------------
-- Table: ingest_run
-- Tracks ingestion runs for auditing and debugging.
-- Useful for confirming:
--   - start/end times
--   - how many rows were read from files (rows_seen)
--   - how many rows were inserted/updated (rows_written)
-- ------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        INTEGER PRIMARY KEY AUTOINCREMENT,  
  started_at    TEXT NOT NULL,                      
  finished_at   TEXT NULL,                          

  station_id    TEXT NULL,                          
  rows_seen     INTEGER NOT NULL DEFAULT 0,         
  rows_written  INTEGER NOT NULL DEFAULT 0           
);


-- ------------------------------------------------
-- Table: weather_yearly_stats
-- Stores derived statistics per station per year.
--
-- Units (derived):
--   - avg_max_temp_c: average daily max temperature in degrees Celsius 
--   - avg_min_temp_c: average daily min temperature in degrees Celsius
--   - total_precip_cm: total accumulated precipitation in centimeters (cm)
--
-- NULL handling:
--   - If a station-year has no valid measurements for a metric, that metric should be NULL.
-- ------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_yearly_stats (
  station_id TEXT NOT NULL,                 -- weather station identifier
  year       INTEGER NOT NULL,              -- 4-digit year extracted from obs_date

  avg_max_temp_c  REAL NULL,                -- AVG(max_temp_tenth_c)/10.0
  avg_min_temp_c  REAL NULL,                -- AVG(min_temp_tenth_c)/10.0
  total_precip_cm REAL NULL,                -- SUM(precip_tenth_mm)/100.0 (0.1mm -> 0.01cm)

  -- Composite primary key: one stats row per station per year.
  PRIMARY KEY (station_id, year)
);

-- Index to speed up stats queries by station and/or year.
CREATE INDEX IF NOT EXISTS idx_stats_station_year
  ON weather_yearly_stats (station_id, year);
