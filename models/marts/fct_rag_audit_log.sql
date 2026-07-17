select
    event_ts::timestamp_ntz as event_ts,
    asset_id,
    user_prompt,
    recommendation_text,
    retrieval_quality_score::float as retrieval_quality_score,
    safety_status,
    model_name,
    requestor_role,
    requestor_user
from {{ source('analytics', 'rag_audit_log') }}
