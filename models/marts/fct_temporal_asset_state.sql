with temporal as (
    select *
    from {{ ref('stg_temporal_state_chunks') }}
)

select
    hour_ts,
    asset_id,
    temperature_current,
    temperature_moving_avg_4h,
    temperature_moving_var_8h,
    temperature_delta_1h,
    vibration_current,
    vibration_moving_avg_4h,
    vibration_moving_var_8h,
    vibration_delta_1h,
    pressure_current,
    pressure_moving_avg_4h,
    pressure_moving_var_8h,
    pressure_delta_1h,
    has_any_alert,
    nearest_prior_log_id,
    nearest_prior_log_date,
    nearest_prior_error_code,
    nearest_prior_technician_notes,
    case
        when has_any_alert = 1 then 'HIGH'
        when temperature_delta_1h > 3 or vibration_delta_1h > 0.25 then 'ELEVATED'
        else 'NORMAL'
    end as inferred_risk_band,
    temporal_state_payload
from temporal
