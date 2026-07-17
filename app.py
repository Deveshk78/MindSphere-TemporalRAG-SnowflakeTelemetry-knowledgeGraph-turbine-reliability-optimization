import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from backend_rag import TemporalDigitalTwinRAG
from demo_engine import DemoTemporalDigitalTwinRAG


load_dotenv()

st.set_page_config(
    page_title="MindSphere Temporal RAG Digital Twin",
    page_icon="⚙️",
    layout="wide",
)


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


@st.cache_resource
def get_rag_engine() -> object:
    if os.getenv("DEMO_MODE", "0") == "1":
        return DemoTemporalDigitalTwinRAG()

    connection = {
        "account": _require_env("SNOWFLAKE_ACCOUNT"),
        "user": _require_env("SNOWFLAKE_USER"),
        "password": _require_env("SNOWFLAKE_PASSWORD"),
        "warehouse": _require_env("SNOWFLAKE_WAREHOUSE"),
        "role": _require_env("SNOWFLAKE_ROLE"),
    }
    return TemporalDigitalTwinRAG(connection_parameters=connection)


rag_engine = get_rag_engine()

st.title("Closed-Loop Digital Twin for Siemens MindSphere Assets")
st.caption(
    "Temporal RAG over Snowflake telemetry and maintenance knowledge for turbine reliability optimization"
)

if os.getenv("DEMO_MODE", "0") == "1":
    st.info("DEMO_MODE enabled: running with deterministic synthetic data and offline recommendation engine.")

with st.sidebar:
    st.header("Operational Context")
    assets = rag_engine.get_available_assets()
    selected_asset = st.selectbox("Asset ID", assets, index=0)

    lookback_hours = st.slider("Lookback Window (hours)", min_value=2, max_value=48, value=8)

telemetry_df = rag_engine.get_telemetry_timeseries(selected_asset, lookback_hours=168)

if telemetry_df.empty:
    st.error("No telemetry data found. Run 01_snowflake_setup.sql and 02_temporal_views.sql first.")
    st.stop()

snapshot_min = telemetry_df["HOUR_TS"].min().to_pydatetime()
snapshot_max = telemetry_df["HOUR_TS"].max().to_pydatetime()

with st.sidebar:
    selected_snapshot = st.slider(
        "Operational Snapshot",
        min_value=snapshot_min,
        max_value=snapshot_max,
        value=snapshot_max,
        format="YYYY-MM-DD HH:mm",
    )

chart_df = telemetry_df.set_index("HOUR_TS")[["TEMPERATURE_CURRENT", "VIBRATION_CURRENT", "PRESSURE_CURRENT"]].rename(
    columns={
        "TEMPERATURE_CURRENT": "Temperature",
        "VIBRATION_CURRENT": "Vibration",
        "PRESSURE_CURRENT": "Pressure",
    }
)

latest_snapshot = telemetry_df[telemetry_df["HOUR_TS"] <= pd.Timestamp(selected_snapshot)].tail(1)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_context" not in st.session_state:
    st.session_state.last_context = None

tab_ops, tab_progress, tab_governance = st.tabs(
    ["Twin Operations", "Project Advancement", "Governance & Audit"]
)

with tab_ops:
    st.subheader("Real-Time Metric Trends")
    st.line_chart(chart_df)

    if not latest_snapshot.empty:
        cols = st.columns(4)
        cols[0].metric("Temperature", f"{latest_snapshot.iloc[0]['TEMPERATURE_CURRENT']:.2f} C")
        cols[1].metric("Vibration", f"{latest_snapshot.iloc[0]['VIBRATION_CURRENT']:.2f} mm/s")
        cols[2].metric("Pressure", f"{latest_snapshot.iloc[0]['PRESSURE_CURRENT']:.2f} bar")
        cols[3].metric(
            "Alert State",
            "ALERT" if int(latest_snapshot.iloc[0]["HAS_ANY_ALERT"]) == 1 else "NORMAL",
        )

    st.divider()
    st.subheader("Temporal RAG Assistant")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_prompt = st.chat_input(
        "Ask the twin: e.g., The turbine exhaust temperature spiked 15% over the past 4 hours. "
        "What component is at risk and what control-loop parameter should we adjust?"
    )

    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.spinner("Retrieving temporal context and generating recommendation..."):
            context = rag_engine.retrieve_context(
                asset_id=selected_asset,
                current_timestamp=selected_snapshot,
                lookback_hours=lookback_hours,
            )
            response_text = rag_engine.generate_twin_recommendation(user_prompt, context)
            st.session_state.last_context = context

        st.session_state.chat_history.append({"role": "assistant", "content": response_text})

        with st.chat_message("assistant"):
            st.markdown(response_text)

        with st.expander("Retrieved Temporal Documents", expanded=True):
            st.markdown("### Historical Matches")
            st.dataframe(pd.DataFrame(context["historical_failures"]), use_container_width=True)

            st.markdown("### Combined Chronological Context")
            timeline_df = pd.DataFrame(context["combined_timeline"])
            st.dataframe(timeline_df, use_container_width=True)

with tab_progress:
    st.subheader("Implementation Progress Dashboard")
    progress_items = [
        ("Snowflake Data Foundation", 100),
        ("Temporal Transformation Views", 100),
        ("Temporal RAG Backend", 100),
        ("dbt Sources/Staging/Marts", 100),
        ("Retrieval + Safety Test Suite", 100),
        ("RBAC + Audit Controls", 100),
        ("Streamlit Twin Cockpit", 100),
    ]
    for label, pct in progress_items:
        st.write(f"{label}: {pct}%")
        st.progress(pct / 100.0)

    st.markdown("### dbt Models in Scope")
    dbt_models_df = pd.DataFrame(
        {
            "Layer": ["sources", "staging", "staging", "staging", "marts", "marts", "marts"],
            "Model": [
                "src_mindsphere_raw.yml",
                "stg_raw_telemetry",
                "stg_maintenance_logs",
                "stg_temporal_state_chunks",
                "fct_temporal_asset_state",
                "dim_latest_asset_health",
                "fct_rag_audit_log",
            ],
            "Status": ["Ready", "Ready", "Ready", "Ready", "Ready", "Ready", "Ready"],
        }
    )
    st.dataframe(dbt_models_df, use_container_width=True)

    st.markdown("### Current Asset Risk Snapshot")
    risk_df = telemetry_df.copy()
    risk_df["RISK"] = risk_df.apply(
        lambda row: "HIGH"
        if int(row["HAS_ANY_ALERT"]) == 1
        else ("ELEVATED" if row["TEMPERATURE_CURRENT"] > risk_df["TEMPERATURE_CURRENT"].quantile(0.8) else "NORMAL"),
        axis=1,
    )
    risk_counts = risk_df.groupby("RISK").size().reset_index(name="count")
    st.bar_chart(risk_counts.set_index("RISK"))

    if st.session_state.last_context:
        st.markdown("### Last Retrieval Quality")
        q = st.session_state.last_context.get("retrieval_quality", {})
        q_cols = st.columns(4)
        q_cols[0].metric("Telemetry Points", q.get("telemetry_points", 0))
        q_cols[1].metric("Historical Matches", q.get("historical_matches", 0))
        q_cols[2].metric("Coverage Ratio", q.get("telemetry_coverage_ratio", 0))
        q_cols[3].metric("Quality Score", q.get("quality_score", 0))

with tab_governance:
    st.subheader("Governance Controls")
    st.markdown(
        "- Role segregation configured: MS_TWIN_ADMIN, MS_TWIN_ENGINEER, MS_TWIN_OPERATOR, MS_TWIN_AUDITOR\n"
        "- Technician notes masking policy enforced for non-privileged roles\n"
        "- Recommendation safety gate blocks unsafe advisories\n"
        "- Audit events persisted for every generated recommendation"
    )

    st.markdown("### Recent Audit Activity")
    audit_df = rag_engine.get_recent_audit_logs(limit=50)
    if audit_df.empty:
        st.info("No audit records available yet. Execute 03_enterprise_governance.sql and run a few chat queries.")
    else:
        st.dataframe(audit_df, use_container_width=True)
        safety_counts = audit_df.groupby("SAFETY_STATUS").size().reset_index(name="count")
        st.bar_chart(safety_counts.set_index("SAFETY_STATUS"))

st.divider()
st.caption(
    f"Snapshot in focus: {datetime.strftime(selected_snapshot, '%Y-%m-%d %H:%M')} | Asset: {selected_asset}"
)
