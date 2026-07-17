from datetime import datetime

from demo_engine import DemoTemporalDigitalTwinRAG


if __name__ == "__main__":
    engine = DemoTemporalDigitalTwinRAG()
    asset = "Siemens-Turbine-GT01"
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    context = engine.retrieve_context(asset_id=asset, current_timestamp=now, lookback_hours=8)
    response = engine.generate_twin_recommendation(
        prompt=(
            "The turbine exhaust temperature spiked 15% over the past 4 hours. "
            "Based on historical maintenance logs, what component is at risk, and what control-loop parameter should we adjust in MindSphere?"
        ),
        retrieved_context=context,
    )

    print("=== MINDSPHERE TEMPORAL RAG DEMO ===")
    print(f"Asset: {asset}")
    print(f"Retrieval Quality: {context['retrieval_quality']}")
    print("Historical Matches:")
    for item in context["historical_failures"]:
        print(f"  - {item['LOG_ID']} | {item['ERROR_CODE']} | score={item['SEARCH_SCORE']}")
    print("\nRecommendation:\n")
    print(response)
