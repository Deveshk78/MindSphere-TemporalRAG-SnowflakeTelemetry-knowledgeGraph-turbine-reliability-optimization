# Risk Management Document

## Risk register summary

### 1. Model hallucination risk
- Impact: Incorrect control recommendations.
- Mitigation: Temporal grounding + mandatory response schema + safety gate +
  blocked fallback output.

### 2. Sensitive data exposure risk
- Impact: Unauthorized visibility of technician notes.
- Mitigation: Role-based access model and masking policy.

### 3. Retrieval quality degradation risk
- Impact: Weak historical context and lower recommendation reliability.
- Mitigation: Retrieval quality scoring and warning thresholds.

### 4. Runtime dependency fragility risk
- Impact: Local environment failures due to package ABI mismatch.
- Mitigation: Demo engine resilience path and deterministic offline mode.

### 5. Auditability gaps risk
- Impact: Incomplete compliance evidence trail.
- Mitigation: Persistent recommendation audit log and daily safety aggregation view.

## Ongoing controls
- Scheduled test execution
- Governance SQL validation in deployment pipeline
- Periodic review of safety policy patterns and blocked-output logs
