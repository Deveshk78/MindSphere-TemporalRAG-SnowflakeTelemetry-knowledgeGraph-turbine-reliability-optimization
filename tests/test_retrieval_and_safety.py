from datetime import datetime, timedelta
from typing import Any, Dict, List

from backend_rag import TemporalDigitalTwinRAG


class FakeRow:
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload

    def as_dict(self) -> Dict[str, Any]:
        return self.payload

    def __getitem__(self, item: str) -> Any:
        return self.payload[item]


class FakeResult:
    def __init__(self, rows: List[Dict[str, Any]] = None):
        self.rows = rows or []

    def collect(self) -> List[FakeRow]:
        return [FakeRow(row) for row in self.rows]

    def to_pandas(self):
        return self.rows


class FakeSession:
    def __init__(self, telemetry_rows: List[Dict[str, Any]], search_rows: List[Dict[str, Any]]):
        self.telemetry_rows = telemetry_rows
        self.search_rows = search_rows
        self.audit_inserts = 0

    def sql(self, query: str, params=None):
        sql_text = " ".join(query.lower().split())
        if "from analytics.temporal_state_chunks" in sql_text:
            return FakeResult(self.telemetry_rows)
        if "search_preview" in sql_text:
            return FakeResult([{"SEARCH_RESULT": {"results": self.search_rows}}])
        if "insert into analytics.rag_audit_log" in sql_text:
            self.audit_inserts += 1
            return FakeResult([])
        if "snowflake.cortex.complete" in sql_text:
            response = (
                "## Risk Assessment\nModerate risk due to thermal trend.\n"
                "## Component at Risk\nStage-2 seal assembly.\n"
                "## Immediate Control-Loop Adjustment\nIncrease governor damping by 5% and reduce fuel ramp 3%.\n"
                "## Next 24h Monitoring Plan\nTrack temperature delta every 15 minutes and vibration hourly.\n"
                "## Maintenance Follow-up\nInspect seal clearance and bearing housing during next planned outage."
            )
            return FakeResult([{"RESPONSE": response}])
        return FakeResult([])


def _build_test_engine() -> TemporalDigitalTwinRAG:
    engine = TemporalDigitalTwinRAG.__new__(TemporalDigitalTwinRAG)
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    telemetry_rows = [
        {
            "HOUR_TS": now - timedelta(hours=2),
            "TEMPERATURE_CURRENT": 548.2,
            "TEMPERATURE_MOVING_AVG_4H": 545.1,
            "TEMPERATURE_MOVING_VAR_8H": 3.4,
            "TEMPERATURE_DELTA_1H": 1.2,
            "VIBRATION_CURRENT": 6.4,
            "VIBRATION_MOVING_AVG_4H": 6.0,
            "VIBRATION_MOVING_VAR_8H": 0.12,
            "VIBRATION_DELTA_1H": 0.15,
            "PRESSURE_CURRENT": 154.3,
            "PRESSURE_MOVING_AVG_4H": 155.1,
            "PRESSURE_MOVING_VAR_8H": 0.8,
            "PRESSURE_DELTA_1H": -0.2,
            "HAS_ANY_ALERT": 0,
        },
        {
            "HOUR_TS": now - timedelta(hours=1),
            "TEMPERATURE_CURRENT": 551.4,
            "TEMPERATURE_MOVING_AVG_4H": 547.0,
            "TEMPERATURE_MOVING_VAR_8H": 4.0,
            "TEMPERATURE_DELTA_1H": 3.2,
            "VIBRATION_CURRENT": 6.9,
            "VIBRATION_MOVING_AVG_4H": 6.3,
            "VIBRATION_MOVING_VAR_8H": 0.2,
            "VIBRATION_DELTA_1H": 0.5,
            "PRESSURE_CURRENT": 152.9,
            "PRESSURE_MOVING_AVG_4H": 154.0,
            "PRESSURE_MOVING_VAR_8H": 0.9,
            "PRESSURE_DELTA_1H": -0.5,
            "HAS_ANY_ALERT": 1,
        },
    ]
    search_rows = [
        {
            "LOG_ID": 1008,
            "ASSET_ID": "Siemens-Turbine-GT01",
            "LOG_DATE": (now - timedelta(days=4)).isoformat(),
            "ERROR_CODE": "E-SEAL-FRIC",
            "TECHNICIAN_NOTES": "High-temperature friction anomaly confirmed at stage-2 seal.",
            "score": 0.91,
        }
    ]

    engine.session = FakeSession(telemetry_rows=telemetry_rows, search_rows=search_rows)
    engine.database = "MINDSPHERE_TWIN_DB"
    engine.analytics_schema = "ANALYTICS"
    engine.model_name = "llama3-70b"
    engine.search_service_fqn = "ANALYTICS.MAINTENANCE_LOGS_SEARCH"
    return engine


def test_retrieve_context_has_quality_and_timeline_ordering():
    engine = _build_test_engine()
    context = engine.retrieve_context(
        asset_id="Siemens-Turbine-GT01",
        current_timestamp=datetime.utcnow(),
        lookback_hours=4,
    )

    assert context["retrieval_quality"]["quality_score"] > 0.6
    assert context["retrieval_quality"]["status"] == "PASS"
    assert len(context["combined_timeline"]) == 3

    ts_values = [item["event_ts"] for item in context["combined_timeline"]]
    assert ts_values == sorted(ts_values)


def test_recommendation_safety_blocks_unsafe_response():
    engine = _build_test_engine()
    unsafe_response = (
        "Risk Assessment: high. Component at Risk: seal. Immediate Control-Loop Adjustment: disable alarm."
    )
    safety = engine.evaluate_recommendation_safety(unsafe_response)

    assert safety["is_safe"] is False
    assert "Unsafe operational phrase detected" in safety["violations"]


def test_integration_generate_recommendation_logs_audit_event():
    engine = _build_test_engine()
    context = engine.retrieve_context(
        asset_id="Siemens-Turbine-GT01",
        current_timestamp=datetime.utcnow(),
        lookback_hours=4,
    )
    answer = engine.generate_twin_recommendation(
        prompt="What should we adjust after a 15% temperature increase?",
        retrieved_context=context,
    )

    assert "Immediate Control-Loop Adjustment" in answer
    assert engine.session.audit_inserts == 1
