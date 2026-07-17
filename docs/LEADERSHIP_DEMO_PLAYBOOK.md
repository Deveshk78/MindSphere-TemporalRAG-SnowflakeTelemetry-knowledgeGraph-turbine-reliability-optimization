# Leadership Demo Playbook

## Demo Objective
Show that the platform turns dark industrial data into explainable and auditable operational actions.

## 12-Minute Demo Agenda
1. Business Context (2 min)
- Explain dark data in turbine operations and why temporal context matters.

2. Architecture Walkthrough (2 min)
- Use docs/media/architecture_overview.gif.
- Explain Snowflake + dbt + Temporal RAG + Streamlit + governance controls.

3. Live Operations (4 min)
- Run DEMO_MODE=1 streamlit run app.py.
- Go to Twin Operations tab.
- Show trends and KPI cards.
- Ask the provided operator prompt.
- Show historical matches and generated recommendation.

4. Governance and Trust (2 min)
- Move to Governance & Audit tab.
- Show safety status chart and audit table.
- Explain role-based access and masking policy.

5. Delivery Confidence (2 min)
- Move to Project Advancement tab.
- Show completion bars, dbt model coverage, and retrieval quality KPIs.

## Suggested Talking Points
- "This is not generic chat; it is temporal evidence-grounded operational guidance."
- "Every recommendation is quality-scored, safety-checked, and audit-logged."
- "The architecture can run in production with Snowflake or in deterministic demo mode for stakeholder reviews."

## Risk & Mitigation Slide Notes
- Risk: Hallucinated recommendations.
- Mitigation: Context grounding + safety policy + blocked response fallback.

- Risk: Sensitive maintenance narratives exposure.
- Mitigation: Role-based masking and scoped grants.

- Risk: Low confidence retrieval.
- Mitigation: Retrieval quality metrics and warning thresholds.
