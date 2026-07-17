select
    log_id::number as log_id,
    asset_id,
    log_date::timestamp_ntz as log_date,
    technician_notes,
    error_code
from {{ source('raw', 'maintenance_logs') }}
