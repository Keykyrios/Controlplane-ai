"""
Demo Scenario 3: Same Output, Different Tier → EDIT (not BLOCK)
================================================================
The same moderate-risk response routed differently under Tier A
vs the Tier C/EU version in Scenario 2.

This demonstrates:
- Same z_t signal, different routing via jurisdiction-aware tropical policy
- Tier A (customer-facing) has looser α → editable errors pass
- The syndrome decoder identifies correctable assertions
- Edit action + syndrome localizes the specific fix needed

Whitepaper: Table 3 (tier-specific α), Section 14.1
"""

import asyncio
import json
import httpx

ORCHESTRATOR = "http://localhost:8000"


async def run():
    print("=" * 60)
    print("  SCENARIO 3: Moderate Risk, Tier A → EDIT (not BLOCK)")
    print("=" * 60)

    payload = {
        "session_id": "demo-sess-003",
        "response_id": "demo-resp-003",
        "response_text": (
            "I think the quarterly revenue was approximately $12.3 million, "
            "though I'm not entirely certain about the exact figure. The growth "
            "rate seems to be around 15% year-over-year based on the data I recall. "
            "The operating margin appears to be healthy but I'd recommend checking "
            "the official report for precise numbers."
        ),
        "prompt_text": "What was our Q2 revenue?",
        "grounding_context": (
            "Q2 2026 Revenue Report: Total revenue $12.8M. "
            "YoY growth: 18.2%. Operating margin: 19.1%. "
            "Net income: $2.4M."
        ),
        "tier": "A",
        "jurisdiction": "US-generic",
        "model_confidence": 0.65,
        "token_usage": {
            "total_tokens": 120,
            "cost_per_token": 0.00003,
            "baseline_cost": 0.004,
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{ORCHESTRATOR}/pipeline/process", json=payload, timeout=15.0)
        result = resp.json()

    print(f"\n  Routing Action:  {result['routing_action'].upper()}")
    print(f"  Processing Time: {result['processing_time_ms']:.1f}ms")
    print(f"\n  Fused Signal z_t:")
    for k, v in result["fused_signal"].items():
        print(f"    {k:>15} = {v}")
    print(f"\n  Routing Scores φ_a(z):")
    for action, score in sorted(result["routing_scores"].items(), key=lambda x: -x[1]):
        marker = " ← WINNER" if action == result["routing_action"] else ""
        print(f"    {action:>10}: {score:+.4f}{marker}")

    obs = result.get("risk_observables", {})
    print(f"\n  Risk Observables:")
    print(f"    p_t = {obs.get('p_t', 'N/A')} — moderate performance risk")
    print(f"    r_t = {obs.get('r_t', 'N/A')} — no safety/bias/PII issues")
    print(f"    Key: hedging language ('I think', 'approximately') detected")

    syn = result.get("syndrome_result")
    if syn:
        print(f"\n  Syndrome Decode (Eq. 40-41):")
        print(f"    Correctable: {syn.get('correctable', 'N/A')}")
        print(f"    Error set size: {syn.get('error_set_size', 'N/A')}")
        print(f"    → Syndrome localizes specific facts to correct")

    print(f"\n  Tier A (US-generic):")
    print(f"    α_A = 0.10 (looser threshold — Table 3)")
    print(f"    This response is editable, not block-worthy")
    print(f"    Same content under Tier C/EU would route to BLOCK or ESCALATE")

    print(f"\n  ✓ SCENARIO 3 — Demonstrates tier-aware routing differentiation")
    print("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(run())
