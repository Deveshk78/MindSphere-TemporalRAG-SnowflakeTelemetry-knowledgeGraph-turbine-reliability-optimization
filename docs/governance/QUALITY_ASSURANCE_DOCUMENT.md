# Quality Assurance Document

## Quality objectives
- Ensure recommendation outputs are structured, actionable, and safe.
- Ensure temporal retrieval context is complete and chronologically coherent.
- Ensure platform demo and UI paths execute without cloud lock-in.

## Quality controls implemented
1. Unit and integration tests
- Retrieval quality scoring behavior
- Safety policy violation detection
- Audit event insertion verification

2. Runtime safety checks
- Required section validation in recommendations
- Banned unsafe phrase detection
- Safe fallback response on policy failure

3. Data quality controls
- dbt schema tests for key model fields
- Temporal transformation consistency via view definitions

4. Operational validation
- Demo runner output verification
- Streamlit startup and tab-level data rendering checks

## Acceptance criteria
- Test suite passes.
- Demo runner executes with quality score and structured recommendation output.
- UI loads in demo mode and shows operations/progress/governance tabs.
