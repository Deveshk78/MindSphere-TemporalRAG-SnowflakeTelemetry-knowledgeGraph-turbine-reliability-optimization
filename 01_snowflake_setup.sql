CREATE OR REPLACE DATABASE MINDSPHERE_TWIN_DB;
USE DATABASE MINDSPHERE_TWIN_DB;

CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

CREATE OR REPLACE TABLE RAW.RAW_TELEMETRY (
    "TIMESTAMP" TIMESTAMP_NTZ NOT NULL,
    ASSET_ID STRING NOT NULL,
    METRIC_NAME STRING NOT NULL,
    METRIC_VALUE FLOAT NOT NULL,
    STATUS STRING NOT NULL
);

CREATE OR REPLACE TABLE RAW.MAINTENANCE_LOGS (
    LOG_ID NUMBER AUTOINCREMENT START 1001 INCREMENT 1,
    ASSET_ID STRING NOT NULL,
    LOG_DATE TIMESTAMP_NTZ NOT NULL,
    TECHNICIAN_NOTES STRING NOT NULL,
    ERROR_CODE STRING NOT NULL
);

TRUNCATE TABLE RAW.RAW_TELEMETRY;
TRUNCATE TABLE RAW.MAINTENANCE_LOGS;

INSERT INTO RAW.RAW_TELEMETRY ("TIMESTAMP", ASSET_ID, METRIC_NAME, METRIC_VALUE, STATUS)
WITH time_axis AS (
    SELECT
        seq4() AS hour_ix,
        DATEADD(HOUR, seq4(), DATEADD(DAY, -30, DATE_TRUNC('HOUR', CURRENT_TIMESTAMP()))) AS ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24 * 30))
),
assets AS (
    SELECT column1 AS asset_id
    FROM VALUES
        ('Siemens-Turbine-GT01'),
        ('Siemens-Turbine-GT02')
),
metrics AS (
    SELECT column1 AS metric_name
    FROM VALUES
        ('temperature'),
        ('vibration'),
        ('pressure')
),
base AS (
    SELECT
        t.hour_ix,
        t.ts,
        a.asset_id,
        m.metric_name,
        CASE
            WHEN m.metric_name = 'temperature' THEN
                505
                + (t.hour_ix / 24.0) * 0.55
                + IFF(a.asset_id = 'Siemens-Turbine-GT01' AND t.hour_ix >= 24 * 20, (t.hour_ix - 24 * 20) * 0.23, 0)
                + IFF(MOD(t.hour_ix, 18) = 0, 7.5, 0)
                + UNIFORM(-2.5, 2.5, RANDOM())
            WHEN m.metric_name = 'vibration' THEN
                3.6
                + (t.hour_ix / 24.0) * 0.04
                + IFF(a.asset_id = 'Siemens-Turbine-GT01' AND t.hour_ix >= 24 * 22, (t.hour_ix - 24 * 22) * 0.012, 0)
                + IFF(MOD(t.hour_ix, 12) = 0, 0.45, 0)
                + UNIFORM(-0.2, 0.2, RANDOM())
            ELSE
                172
                - (t.hour_ix / 24.0) * 0.18
                - IFF(a.asset_id = 'Siemens-Turbine-GT01' AND t.hour_ix >= 24 * 22, (t.hour_ix - 24 * 22) * 0.05, 0)
                + UNIFORM(-0.9, 0.9, RANDOM())
        END AS metric_value
    FROM time_axis t
    CROSS JOIN assets a
    CROSS JOIN metrics m
)
SELECT
    ts AS "TIMESTAMP",
    asset_id,
    metric_name,
    ROUND(metric_value, 4) AS metric_value,
    CASE
        WHEN metric_name = 'temperature' AND metric_value >= 565 THEN 'ALERT'
        WHEN metric_name = 'temperature' AND metric_value >= 548 THEN 'WARN'
        WHEN metric_name = 'vibration' AND metric_value >= 8 THEN 'ALERT'
        WHEN metric_name = 'vibration' AND metric_value >= 6.7 THEN 'WARN'
        WHEN metric_name = 'pressure' AND metric_value <= 140 THEN 'ALERT'
        WHEN metric_name = 'pressure' AND metric_value <= 150 THEN 'WARN'
        ELSE 'NORMAL'
    END AS status
FROM base;

INSERT INTO RAW.MAINTENANCE_LOGS (ASSET_ID, LOG_DATE, TECHNICIAN_NOTES, ERROR_CODE)
SELECT * FROM VALUES
    ('Siemens-Turbine-GT01', DATEADD(DAY, -28, CURRENT_TIMESTAMP()), 'Routine inspection completed. Slight discoloration observed at exhaust diffuser. No immediate control action required.', 'NONE'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -24, CURRENT_TIMESTAMP()), 'Exhaust thermocouple drift detected. Calibrated sensor pair T3 and T4; minor deviation remains under tolerance.', 'E-TEMP-CAL'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -19, CURRENT_TIMESTAMP()), 'Vibration trend increased during high-load dispatch. Detected early-stage bearing cage wear on turbine side.', 'E-VIB-BRG'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -15, CURRENT_TIMESTAMP()), 'Inspected lubrication loop. Oil viscosity slightly below seasonal nominal band; replenished and restored pressure.', 'E-LUBE-VISC'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -11, CURRENT_TIMESTAMP()), 'Combustor liner hotspot pattern intensified. Recommended reducing fuel ramp rate and adjusting inlet guide vane schedule.', 'E-COMB-HOT'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -8, CURRENT_TIMESTAMP()), 'Rotor rub signatures observed with concurrent exhaust temperature rise. Friction at stage-2 seal likely under transient loads.', 'E-ROTOR-RUB'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -4, CURRENT_TIMESTAMP()), 'High-temperature friction anomaly confirmed. Stage-2 seal clearance exceeded allowable threshold; emergency correction applied.', 'E-SEAL-FRIC'),
    ('Siemens-Turbine-GT01', DATEADD(DAY, -2, CURRENT_TIMESTAMP()), 'Post-maintenance validation successful; recommend closed-loop governor damping increase by 6 percent during peak demand.', 'E-CONTROL-TUNE'),
    ('Siemens-Turbine-GT02', DATEADD(DAY, -10, CURRENT_TIMESTAMP()), 'Baseline maintenance log for sister unit. No anomalous friction behavior detected.', 'NONE');

CREATE OR REPLACE TABLE ANALYTICS.MAINTENANCE_LOG_VECTORS AS
SELECT
    LOG_ID,
    ASSET_ID,
    LOG_DATE,
    TECHNICIAN_NOTES,
    ERROR_CODE,
    SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m-v1.5', TECHNICIAN_NOTES) AS TECHNICIAN_NOTES_VECTOR
FROM RAW.MAINTENANCE_LOGS;

SET ACTIVE_WAREHOUSE = (SELECT CURRENT_WAREHOUSE());

CREATE OR REPLACE CORTEX SEARCH SERVICE ANALYTICS.MAINTENANCE_LOGS_SEARCH
ON TECHNICIAN_NOTES
ATTRIBUTES ASSET_ID, LOG_DATE, ERROR_CODE
WAREHOUSE = IDENTIFIER($ACTIVE_WAREHOUSE)
TARGET_LAG = '5 MINUTES'
AS
SELECT
    LOG_ID,
    ASSET_ID,
    LOG_DATE,
    TECHNICIAN_NOTES,
    ERROR_CODE
FROM RAW.MAINTENANCE_LOGS;
