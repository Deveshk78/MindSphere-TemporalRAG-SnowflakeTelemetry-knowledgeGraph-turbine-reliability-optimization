from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

try:
    import pandas as pd
except Exception:  # pragma: no cover - fallback for local binary mismatch only.
    pd = None

try:
    from snowflake.snowpark import Session
    from snowflake.snowpark.exceptions import SnowparkSQLException
except Exception:  # pragma: no cover - fallback for local test environment only.
    Session = Any  # type: ignore[misc,assignment]

    class SnowparkSQLException(Exception):
        pass


class TemporalDigitalTwinRAG:
    def __init__(
        self,
        connection_parameters: Dict[str, Any],
        database: str = "MINDSPHERE_TWIN_DB",
        analytics_schema: str = "ANALYTICS",
        model_name: str = "llama3-70b",
        search_service_fqn: str = "ANALYTICS.MAINTENANCE_LOGS_SEARCH",
    ) -> None:
        self.session = Session.builder.configs(connection_parameters).create()
        self.database = database
        self.analytics_schema = analytics_schema
        self.model_name = model_name
        self.search_service_fqn = search_service_fqn

        self.session.sql(f"USE DATABASE {self.database}").collect()
        self.session.sql(f"USE SCHEMA {self.analytics_schema}").collect()

    @classmethod
    def from_env(cls) -> "TemporalDigitalTwinRAG":
        required = {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "role": os.environ["SNOWFLAKE_ROLE"],
        }

        if "SNOWFLAKE_AUTHENTICATOR" in os.environ:
            required["authenticator"] = os.environ["SNOWFLAKE_AUTHENTICATOR"]

        return cls(connection_parameters=required)

    def get_available_assets(self) -> List[str]:
        rows = self.session.sql(
            """
            SELECT DISTINCT ASSET_ID
            FROM RAW.RAW_TELEMETRY
            ORDER BY ASSET_ID
            """
        ).collect()
        return [row["ASSET_ID"] for row in rows]

    def get_telemetry_timeseries(self, asset_id: str, lookback_hours: int = 96) -> pd.DataFrame:
        if pd is None:
            raise RuntimeError("pandas import failed. Install dependencies from requirements.txt.")

        df = self.session.sql(
            """
            SELECT
                HOUR_TS,
                TEMPERATURE_CURRENT,
                VIBRATION_CURRENT,
                PRESSURE_CURRENT,
                HAS_ANY_ALERT
            FROM ANALYTICS.TEMPORAL_STATE_CHUNKS
            WHERE ASSET_ID = ?
              AND HOUR_TS >= DATEADD(HOUR, -?, CURRENT_TIMESTAMP())
            ORDER BY HOUR_TS
            """,
            params=[asset_id, lookback_hours],
        ).to_pandas()

        if not df.empty:
            df["HOUR_TS"] = pd.to_datetime(df["HOUR_TS"])

        return df

    def retrieve_context(
        self,
        asset_id: str,
        current_timestamp: datetime,
        lookback_hours: int,
    ) -> Dict[str, Any]:
        telemetry_rows = self.session.sql(
            """
            SELECT
                HOUR_TS,
                TEMPERATURE_CURRENT,
                TEMPERATURE_MOVING_AVG_4H,
                TEMPERATURE_MOVING_VAR_8H,
                TEMPERATURE_DELTA_1H,
                VIBRATION_CURRENT,
                VIBRATION_MOVING_AVG_4H,
                VIBRATION_MOVING_VAR_8H,
                VIBRATION_DELTA_1H,
                PRESSURE_CURRENT,
                PRESSURE_MOVING_AVG_4H,
                PRESSURE_MOVING_VAR_8H,
                PRESSURE_DELTA_1H,
                HAS_ANY_ALERT
            FROM ANALYTICS.TEMPORAL_STATE_CHUNKS
            WHERE ASSET_ID = ?
              AND HOUR_TS BETWEEN DATEADD(HOUR, -?, ?) AND ?
            ORDER BY HOUR_TS
            """,
            params=[asset_id, lookback_hours, current_timestamp, current_timestamp],
        ).collect()

        telemetry_dicts: List[Dict[str, Any]] = [row.as_dict() for row in telemetry_rows]

        query_text = self._build_retrieval_query_text(asset_id=asset_id, telemetry_dicts=telemetry_dicts)

        historical_matches = self._search_historical_logs(asset_id=asset_id, query_text=query_text)

        combined_timeline: List[Dict[str, Any]] = []

        for row in telemetry_dicts:
            combined_timeline.append(
                {
                    "event_type": "telemetry_state",
                    "event_ts": row["HOUR_TS"],
                    "payload": row,
                }
            )

        for match in historical_matches:
            combined_timeline.append(
                {
                    "event_type": "historical_maintenance",
                    "event_ts": self._coerce_ts(match.get("LOG_DATE") or match.get("log_date")),
                    "payload": match,
                }
            )

        combined_timeline.sort(key=lambda item: self._coerce_ts(item.get("event_ts")))

        context_text = self._build_context_text(asset_id, combined_timeline)
        retrieval_quality = self.evaluate_retrieval_quality(
            telemetry_window=telemetry_dicts,
            historical_failures=historical_matches,
            lookback_hours=lookback_hours,
        )

        return {
            "asset_id": asset_id,
            "current_timestamp": current_timestamp,
            "lookback_hours": lookback_hours,
            "telemetry_window": telemetry_dicts,
            "historical_failures": historical_matches,
            "combined_timeline": combined_timeline,
            "retrieval_quality": retrieval_quality,
            "context_text": context_text,
        }

    def generate_twin_recommendation(self, prompt: str, retrieved_context: Dict[str, Any]) -> str:
        system_instruction = (
            "You are an industrial reliability engineer for Siemens MindSphere digital twins. "
            "Provide actionable, closed-loop recommendations with risk level, suspect component, "
            "control-loop adjustment, and validation steps. Keep recommendations specific and concise."
        )

        composed_prompt = (
            f"SYSTEM INSTRUCTION:\n{system_instruction}\n\n"
            f"TEMPORAL CONTEXT:\n{retrieved_context['context_text']}\n\n"
            f"USER QUESTION:\n{prompt}\n\n"
            "Return a markdown response with sections: "
            "1) Risk Assessment, 2) Component at Risk, 3) Immediate Control-Loop Adjustment, "
            "4) Next 24h Monitoring Plan, 5) Maintenance Follow-up."
        )

        row = self.session.sql(
            """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS RESPONSE
            """,
            params=[self.model_name, composed_prompt],
        ).collect()[0]

        response = row["RESPONSE"]
        if isinstance(response, dict):
            response_text = json.dumps(response, indent=2)
        else:
            response_text = str(response)

        safety = self.evaluate_recommendation_safety(response_text)
        final_response = response_text
        if not safety["is_safe"]:
            final_response = self._build_safety_fallback(response_text, safety)

        self.log_audit_event(
            asset_id=retrieved_context.get("asset_id", "UNKNOWN"),
            prompt=prompt,
            retrieved_context=retrieved_context,
            recommendation=final_response,
            retrieval_quality=retrieved_context.get("retrieval_quality", {}),
            safety_assessment=safety,
        )

        return final_response

    def evaluate_retrieval_quality(
        self,
        telemetry_window: List[Dict[str, Any]],
        historical_failures: List[Dict[str, Any]],
        lookback_hours: int,
    ) -> Dict[str, Any]:
        telemetry_points = len(telemetry_window)
        historical_points = len(historical_failures)
        coverage_ratio = round(min(1.0, telemetry_points / max(1, lookback_hours)), 3)
        telemetry_sufficiency = min(1.0, telemetry_points / max(1.0, lookback_hours * 0.5))
        historical_sufficiency = min(1.0, historical_points / 1.0)
        quality_score = round(
            min(
                1.0,
                (0.45 * telemetry_sufficiency)
                + (0.45 * historical_sufficiency)
                + (0.10 * coverage_ratio),
            ),
            3,
        )
        return {
            "telemetry_points": telemetry_points,
            "historical_matches": historical_points,
            "telemetry_coverage_ratio": coverage_ratio,
            "telemetry_sufficiency": round(telemetry_sufficiency, 3),
            "historical_sufficiency": round(historical_sufficiency, 3),
            "quality_score": quality_score,
            "status": "PASS" if quality_score >= 0.7 else "WARN",
        }

    def evaluate_recommendation_safety(self, recommendation: str) -> Dict[str, Any]:
        required_sections = [
            "Risk Assessment",
            "Component at Risk",
            "Immediate Control-Loop Adjustment",
            "Next 24h Monitoring Plan",
            "Maintenance Follow-up",
        ]
        banned_patterns = [
            "ignore safety interlock",
            "disable alarm",
            "bypass trip",
            "skip verification",
            "run to failure",
        ]

        missing_sections = [s for s in required_sections if s.lower() not in recommendation.lower()]
        banned_hits = [p for p in banned_patterns if p in recommendation.lower()]
        too_short = len(recommendation.strip()) < 180

        violations: List[str] = []
        if missing_sections:
            violations.append("Missing required recommendation sections")
        if banned_hits:
            violations.append("Unsafe operational phrase detected")
        if too_short:
            violations.append("Recommendation too short for operational decision support")

        return {
            "is_safe": len(violations) == 0,
            "missing_sections": missing_sections,
            "banned_hits": banned_hits,
            "violations": violations,
        }

    def get_recent_audit_logs(self, limit: int = 100) -> pd.DataFrame:
        if pd is None:
            raise RuntimeError("pandas import failed. Install dependencies from requirements.txt.")

        try:
            df = self.session.sql(
                """
                SELECT
                    EVENT_TS,
                    ASSET_ID,
                    USER_PROMPT,
                    RETRIEVAL_QUALITY_SCORE,
                    SAFETY_STATUS,
                    MODEL_NAME
                FROM ANALYTICS.RAG_AUDIT_LOG
                ORDER BY EVENT_TS DESC
                LIMIT ?
                """,
                params=[limit],
            ).to_pandas()
            if not df.empty:
                df["EVENT_TS"] = pd.to_datetime(df["EVENT_TS"])
            return df
        except SnowparkSQLException:
            return pd.DataFrame(
                columns=[
                    "EVENT_TS",
                    "ASSET_ID",
                    "USER_PROMPT",
                    "RETRIEVAL_QUALITY_SCORE",
                    "SAFETY_STATUS",
                    "MODEL_NAME",
                ]
            )

    def log_audit_event(
        self,
        asset_id: str,
        prompt: str,
        retrieved_context: Dict[str, Any],
        recommendation: str,
        retrieval_quality: Dict[str, Any],
        safety_assessment: Dict[str, Any],
    ) -> None:
        try:
            self.session.sql(
                """
                INSERT INTO ANALYTICS.RAG_AUDIT_LOG (
                    EVENT_TS,
                    ASSET_ID,
                    USER_PROMPT,
                    RETRIEVED_CONTEXT,
                    RECOMMENDATION_TEXT,
                    RETRIEVAL_QUALITY_SCORE,
                    SAFETY_STATUS,
                    SAFETY_DETAILS,
                    MODEL_NAME
                )
                SELECT
                    CURRENT_TIMESTAMP(),
                    ?,
                    ?,
                    PARSE_JSON(?),
                    ?,
                    ?,
                    ?,
                    PARSE_JSON(?),
                    ?
                """,
                params=[
                    asset_id,
                    prompt,
                    json.dumps(retrieved_context, default=str),
                    recommendation,
                    retrieval_quality.get("quality_score"),
                    "PASS" if safety_assessment.get("is_safe") else "BLOCKED",
                    json.dumps(safety_assessment, default=str),
                    self.model_name,
                ],
            ).collect()
        except SnowparkSQLException:
            # Failing closed on audit insert would stop operations; fallback keeps inference available.
            return

    def _build_retrieval_query_text(
        self,
        asset_id: str,
        telemetry_dicts: List[Dict[str, Any]],
    ) -> str:
        if telemetry_dicts:
            latest = telemetry_dicts[-1]
            return (
                f"Asset {asset_id} temperature {latest['TEMPERATURE_CURRENT']:.2f}C, "
                f"vibration {latest['VIBRATION_CURRENT']:.2f} mm/s, pressure {latest['PRESSURE_CURRENT']:.2f} bar, "
                f"temperature delta {latest['TEMPERATURE_DELTA_1H']:.2f} over 1h. "
                "Find similar historical friction, thermal stress, or rotor rub events and fixes."
            )
        return (
            f"Asset {asset_id} historical failures related to turbine friction, high exhaust temperature, "
            "bearing wear, and control-loop remediation."
        )

    @staticmethod
    def _build_safety_fallback(original_recommendation: str, safety: Dict[str, Any]) -> str:
        violations = ", ".join(safety.get("violations", [])) or "Unknown validation failure"
        return (
            "## Risk Assessment\n"
            "Safety gate blocked direct recommendation release due to policy checks.\n\n"
            "## Component at Risk\n"
            "Potential component remains under review pending safe-response regeneration.\n\n"
            "## Immediate Control-Loop Adjustment\n"
            "Hold current setpoints and keep protective interlocks enabled until reviewed by reliability engineer.\n\n"
            "## Next 24h Monitoring Plan\n"
            "Increase telemetry polling and trigger manual inspection if alert state persists for 2 consecutive hours.\n\n"
            "## Maintenance Follow-up\n"
            f"Validation issue detected: {violations}. Regenerate with stricter constraints before applying changes.\n\n"
            "### Blocked Draft\n"
            f"{original_recommendation}"
        )

    def close(self) -> None:
        self.session.close()

    def _search_historical_logs(self, asset_id: str, query_text: str) -> List[Dict[str, Any]]:
        try:
            row = self.session.sql(
                """
                SELECT PARSE_JSON(
                    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                        ?,
                        OBJECT_CONSTRUCT(
                            'query', ?,
                            'columns', ARRAY_CONSTRUCT('LOG_ID', 'ASSET_ID', 'LOG_DATE', 'ERROR_CODE', 'TECHNICIAN_NOTES'),
                            'filter', OBJECT_CONSTRUCT('@eq', OBJECT_CONSTRUCT('ASSET_ID', ?)),
                            'limit', 6
                        )
                    )
                ) AS SEARCH_RESULT
                """,
                params=[self.search_service_fqn, query_text, asset_id],
            ).collect()[0]

            payload = row["SEARCH_RESULT"]
            if isinstance(payload, str):
                payload = json.loads(payload)

            results = payload.get("results", []) if isinstance(payload, dict) else []
            cleaned = []
            for result in results:
                log_date = result.get("LOG_DATE") or result.get("log_date")
                cleaned.append(
                    {
                        "LOG_ID": result.get("LOG_ID") or result.get("log_id"),
                        "ASSET_ID": result.get("ASSET_ID") or result.get("asset_id"),
                        "LOG_DATE": self._coerce_ts(log_date),
                        "ERROR_CODE": result.get("ERROR_CODE") or result.get("error_code"),
                        "TECHNICIAN_NOTES": result.get("TECHNICIAN_NOTES") or result.get("technician_notes"),
                        "SEARCH_SCORE": result.get("score"),
                    }
                )
            return cleaned
        except SnowparkSQLException:
            # Fallback path uses vector similarity if Cortex Search service is not yet available.
            rows = self.session.sql(
                """
                WITH QUERY_EMBEDDING AS (
                    SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                        'snowflake-arctic-embed-m-v1.5',
                        ?
                    ) AS EMB
                )
                SELECT
                    v.LOG_ID,
                    v.ASSET_ID,
                    v.LOG_DATE,
                    v.ERROR_CODE,
                    v.TECHNICIAN_NOTES,
                    VECTOR_COSINE_SIMILARITY(v.TECHNICIAN_NOTES_VECTOR, q.EMB) AS SEARCH_SCORE
                FROM ANALYTICS.MAINTENANCE_LOG_VECTORS v,
                     QUERY_EMBEDDING q
                WHERE v.ASSET_ID = ?
                ORDER BY SEARCH_SCORE DESC
                LIMIT 6
                """,
                params=[query_text, asset_id],
            ).collect()
            return [row.as_dict() for row in rows]

    @staticmethod
    def _build_context_text(asset_id: str, timeline: List[Dict[str, Any]]) -> str:
        lines = [f"Asset: {asset_id}", "Chronological context:"]
        for item in timeline:
            event_ts = item.get("event_ts")
            event_type = item.get("event_type")
            payload = item.get("payload", {})
            lines.append(f"- [{event_ts}] ({event_type}) {json.dumps(payload, default=str)}")
        return "\n".join(lines)

    @staticmethod
    def _coerce_ts(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.min
        return datetime.min
