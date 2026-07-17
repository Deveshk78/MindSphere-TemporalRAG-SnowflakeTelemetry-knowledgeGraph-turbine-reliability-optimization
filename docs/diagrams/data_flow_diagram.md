# Data Flow Diagram

```mermaid
flowchart TD
    T1[Telemetry Metrics: temp/vibration/pressure] --> T2[RAW.RAW_TELEMETRY]
    M1[Technician Notes + Error Codes] --> M2[RAW.MAINTENANCE_LOGS]
    T2 --> T3[ANALYTICS.TELEMETRY_HOURLY_METRICS]
    T3 --> T4[ANALYTICS.TEMPORAL_STATE_CHUNKS]
    M2 --> M3[ANALYTICS.MAINTENANCE_LOG_VECTORS]
    M2 --> M4[ANALYTICS.MAINTENANCE_LOGS_SEARCH]
    T4 --> R1[retrieve_context()]
    M4 --> R1
    M3 --> R1
    R1 --> R2[Combined Temporal Context]
    R2 --> R3[generate_twin_recommendation()]
    R3 --> R4[Safety Validation]
    R4 --> R5[ANALYTICS.RAG_AUDIT_LOG]
    R4 --> U1[Streamlit Response + Evidence Tables]
```
