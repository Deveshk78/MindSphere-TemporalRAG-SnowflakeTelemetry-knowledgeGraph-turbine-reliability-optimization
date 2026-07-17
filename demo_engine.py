from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional in demo-only runtime.
    pd = None


@dataclass
class DemoTemporalDigitalTwinRAG:
    model_name: str = "llama3-70b"

    def __post_init__(self) -> None:
        self._assets = ["Siemens-Turbine-GT01", "Siemens-Turbine-GT02"]
        self._telemetry = self._generate_telemetry()

    def _generate_telemetry(self) -> List[Dict[str, Any]]:
        end_ts = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start_ts = end_ts - timedelta(hours=168)
        rows: List[Dict[str, Any]] = []
        hour_ix = 0
        current = start_ts
        while current <= end_ts:
            for asset in self._assets:
                temp = 510 + hour_ix * 0.18 + (8 if (hour_ix % 24) in (18, 19) else 0)
                if asset == "Siemens-Turbine-GT01" and hour_ix > 96:
                    temp += (hour_ix - 96) * 0.22
                vib = 3.4 + hour_ix * 0.012 + (0.5 if hour_ix % 12 == 0 else 0)
                pressure = 172 - hour_ix * 0.08 - (0.03 * max(0, hour_ix - 96))
                has_alert = int(temp > 548 or vib > 6.7 or pressure < 150)
                rows.append(
                    {
                        "HOUR_TS": current,
                        "ASSET_ID": asset,
                        "TEMPERATURE_CURRENT": round(temp, 2),
                        "VIBRATION_CURRENT": round(vib, 2),
                        "PRESSURE_CURRENT": round(pressure, 2),
                        "HAS_ANY_ALERT": has_alert,
                    }
                )
            hour_ix += 1
            current = current + timedelta(hours=1)
        return rows

    def get_available_assets(self) -> List[str]:
        return self._assets

    def get_telemetry_timeseries(self, asset_id: str, lookback_hours: int = 96):
        cut = datetime.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=lookback_hours)
        rows = [
            row
            for row in self._telemetry
            if row["ASSET_ID"] == asset_id and row["HOUR_TS"] >= cut
        ]
        rows.sort(key=lambda item: item["HOUR_TS"])
        if pd is None:
            return rows
        return pd.DataFrame(rows)

    def retrieve_context(self, asset_id: str, current_timestamp: datetime, lookback_hours: int) -> Dict[str, Any]:
        start_ts = current_timestamp - timedelta(hours=lookback_hours)
        telemetry_records = [
            row
            for row in self._telemetry
            if row["ASSET_ID"] == asset_id and start_ts <= row["HOUR_TS"] <= current_timestamp
        ]
        telemetry_records.sort(key=lambda item: item["HOUR_TS"])

        historical_failures = [
            {
                "LOG_ID": 1008,
                "ASSET_ID": asset_id,
                "LOG_DATE": (current_timestamp - timedelta(days=4)).isoformat(),
                "ERROR_CODE": "E-SEAL-FRIC",
                "TECHNICIAN_NOTES": "High-temperature friction anomaly confirmed. Stage-2 seal clearance exceeded threshold.",
                "SEARCH_SCORE": 0.91,
            },
            {
                "LOG_ID": 1009,
                "ASSET_ID": asset_id,
                "LOG_DATE": (current_timestamp - timedelta(days=2)).isoformat(),
                "ERROR_CODE": "E-CONTROL-TUNE",
                "TECHNICIAN_NOTES": "Increased governor damping by 6% during peak load to reduce thermal overshoot.",
                "SEARCH_SCORE": 0.86,
            },
        ]

        timeline = [
            {"event_type": "telemetry_state", "event_ts": r["HOUR_TS"], "payload": r}
            for r in telemetry_records[-6:]
        ]
        for h in historical_failures:
            timeline.append({"event_type": "historical_maintenance", "event_ts": h["LOG_DATE"], "payload": h})

        context_text = "\n".join(
            [
                f"Asset: {asset_id}",
                "Chronological context:",
                *[f"- [{item['event_ts']}] ({item['event_type']}) {item['payload']}" for item in timeline],
            ]
        )

        retrieval_quality = {
            "telemetry_points": len(telemetry_records),
            "historical_matches": len(historical_failures),
            "telemetry_coverage_ratio": 1.0,
            "telemetry_sufficiency": 1.0,
            "historical_sufficiency": 1.0,
            "quality_score": 0.95,
            "status": "PASS",
        }

        return {
            "asset_id": asset_id,
            "current_timestamp": current_timestamp,
            "lookback_hours": lookback_hours,
            "telemetry_window": telemetry_records,
            "historical_failures": historical_failures,
            "combined_timeline": timeline,
            "retrieval_quality": retrieval_quality,
            "context_text": context_text,
        }

    def generate_twin_recommendation(self, prompt: str, retrieved_context: Dict[str, Any]) -> str:
        _ = prompt
        risk = "HIGH" if retrieved_context["telemetry_window"] and retrieved_context["telemetry_window"][-1]["HAS_ANY_ALERT"] == 1 else "ELEVATED"
        return (
            "## Risk Assessment\n"
            f"{risk} risk due to rising thermal trend and vibration drift in recent telemetry.\n\n"
            "## Component at Risk\n"
            "Stage-2 seal and adjacent bearing housing are most likely at risk.\n\n"
            "## Immediate Control-Loop Adjustment\n"
            "Increase governor damping by 6%, reduce fuel ramp-rate by 4%, and cap transient load step to 3% per minute.\n\n"
            "## Next 24h Monitoring Plan\n"
            "Track temperature delta every 15 minutes, vibration hourly, and trigger inspection if alerts persist for 2 hours.\n\n"
            "## Maintenance Follow-up\n"
            "Schedule seal-clearance verification and lubrication loop inspection in next maintenance window."
        )

    def get_recent_audit_logs(self, limit: int = 50):
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        rows = []
        for i in range(limit):
            rows.append(
                {
                    "EVENT_TS": now - timedelta(hours=i),
                    "ASSET_ID": "Siemens-Turbine-GT01",
                    "USER_PROMPT": "Demo prompt",
                    "RETRIEVAL_QUALITY_SCORE": 0.9,
                    "SAFETY_STATUS": "PASS" if i % 5 else "BLOCKED",
                    "MODEL_NAME": self.model_name,
                }
            )
        if pd is None:
            return rows
        return pd.DataFrame(rows)
