-- Я создаю только собственную новую БД, чужой файл не присваиваю.
CREATE TABLE app_meta (application VARCHAR PRIMARY KEY, schema_version INTEGER NOT NULL);
INSERT INTO app_meta VALUES ('duckdb-meter-rollups', 1);
CREATE TABLE ingest_batch (
    batch_id VARCHAR PRIMARY KEY,
    input_sha256 VARCHAR NOT NULL,
    input_rows INTEGER NOT NULL,
    new_events INTEGER NOT NULL,
    duplicate_rows INTEGER NOT NULL,
    committed_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);
CREATE TABLE meter_event (
    event_id VARCHAR PRIMARY KEY,
    site_id VARCHAR NOT NULL,
    meter_id VARCHAR NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    energy_wh BIGINT NOT NULL CHECK (energy_wh BETWEEN 0 AND 1000000000),
    first_batch_id VARCHAR NOT NULL REFERENCES ingest_batch(batch_id)
);
-- Я явно задаю окно ROWS, чтобы накопительный итог рос по одному часовому bucket.
CREATE VIEW hourly_usage AS
WITH hourly AS (
    SELECT site_id, date_trunc('hour', occurred_at) AS hour_utc,
           count(*) AS event_count, count(DISTINCT meter_id) AS meter_count,
           sum(energy_wh) AS energy_wh
    FROM meter_event GROUP BY site_id, date_trunc('hour', occurred_at)
)
SELECT *, sum(energy_wh) OVER (
    PARTITION BY site_id, CAST(hour_utc AS DATE) ORDER BY hour_utc
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
) AS day_cumulative_wh FROM hourly;
