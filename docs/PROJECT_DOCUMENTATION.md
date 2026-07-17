# MindSphere Temporal RAG Digital Twin Documentation

## 1. Executive Summary
This project is a production-oriented Temporal Retrieval-Augmented Generation (RAG) platform for Siemens MindSphere / Insights Hub use cases in power and aerospace operations.
It combines time-series asset telemetry and unstructured maintenance logs to generate closed-loop recommendations for reliability engineers and operators.

## 2. Scope Implemented In This Build
- Snowflake warehouse setup with RAW and ANALYTICS schemas.
- Synthetic 30-day turbine telemetry and maintenance logs.
- Temporal state engine (hourly metrics, moving averages, variance, deltas).
- Cortex semantic retrieval with vector fallback.
- LLM-driven recommendation generation with safety validation.
- Enterprise controls: RBAC roles, masking policy, and audit log model.
- dbt sources, staging, and marts models.
- Streamlit leadership-ready cockpit with operations, progress, and governance tabs.
- Unit/integration tests for retrieval quality and safety behavior.

## 3. Repository Layout
- 01_snowflake_setup.sql
- 02_temporal_views.sql
- 03_enterprise_governance.sql
- backend_rag.py
- app.py
- demo_engine.py
- demo_runner.py
- dbt_project.yml
- models/
- tests/
- docs/

## 4. Chat-Based Build Notes (Implementation Comments)
- Added robust retrieval path: Cortex Search first, vector similarity fallback.
- Added recommendation safety guardrails to prevent unsafe advice release.
- Added enterprise audit insert on each recommendation event.
- Added dbt semantic layers: source -> staging -> marts.
- Added governance controls including roles and data masking for technician notes.
- Added offline demo mode for environments without Snowflake credentials.

## 5. Architecture Diagram
See docs/diagrams/architecture_diagram.md and docs/media/architecture_diagram.png.

## 6. Data Flow Diagram
See docs/diagrams/data_flow_diagram.md and docs/media/data_flow_diagram.png.

## 7. Call Flow Diagram
See docs/diagrams/call_flow_diagram.md and docs/media/call_flow_diagram.png.

## 8. Visual Media Bundle
See docs/VISUAL_ASSETS.md for all generated PNG and GIF assets, including the product icon.

## 9. Security, Compliance, and Audit
- Role model: MS_TWIN_ADMIN, MS_TWIN_ENGINEER, MS_TWIN_OPERATOR, MS_TWIN_AUDITOR.
- Column-level masking policy on RAW.MAINTENANCE_LOGS.TECHNICIAN_NOTES.
- RAG audit capture in ANALYTICS.RAG_AUDIT_LOG.
- Audit analytic view AUDIT.RAG_SAFETY_AUDIT_DAILY.

## 10. Running The Project
### 10.1 Production Path (Snowflake Connected)
1. Execute 01_snowflake_setup.sql.
2. Execute 02_temporal_views.sql.
3. Execute 03_enterprise_governance.sql.
4. Set environment variables:
   - SNOWFLAKE_ACCOUNT
   - SNOWFLAKE_USER
   - SNOWFLAKE_PASSWORD
   - SNOWFLAKE_WAREHOUSE
   - SNOWFLAKE_ROLE
5. Start app: python3 -m streamlit run app.py

### 10.2 Demo Path (No Cloud Dependency)
1. Run: python3 demo_runner.py
2. Start UI in demo mode: DEMO_MODE=1 python3 -m streamlit run app.py

### 10.3 Verified Demo Execution (This Workspace)
- CLI demo command executed successfully: python3 demo_runner.py
- Streamlit startup verified in demo mode on Local URL http://localhost:8510

## 11. Leadership Demo Script
See docs/LEADERSHIP_DEMO_PLAYBOOK.md for a timed talk-track and talking points.
