select
    "TIMESTAMP"::timestamp_ntz as event_ts,
    asset_id,
    metric_name,
    metric_value::float as metric_value,
    status
from {{ source('raw', 'raw_telemetry') }}
