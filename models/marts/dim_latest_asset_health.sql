with ranked as (
    select
        hour_ts,
        asset_id,
        temperature_current,
        vibration_current,
        pressure_current,
        has_any_alert,
        inferred_risk_band,
        row_number() over (partition by asset_id order by hour_ts desc) as rn
    from {{ ref('fct_temporal_asset_state') }}
)

select
    hour_ts as latest_hour_ts,
    asset_id,
    temperature_current,
    vibration_current,
    pressure_current,
    has_any_alert,
    inferred_risk_band
from ranked
where rn = 1
