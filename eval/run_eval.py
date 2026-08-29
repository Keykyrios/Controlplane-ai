"""
Evaluation Harness — Section 21
=================================
Runs the full pipeline against the synthetic corpus and computes
the 5 key measurements from the whitepaper:

1. False-Positive Rate (FPR) — safe responses incorrectly flagged
2. False-Negative Rate (FNR) — violations incorrectly passed
3. Median Latency (L_fast) — per-response processing time
4. P99 Latency — tail latency
5. Throughput — responses/second

Also computes per-tier breakdowns and confusion matrices.

Whitepaper: Section 21
Blueprint: Section 16
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

ORCHESTRATOR_URL = "http://localhost:8000"
CORPUS_PATH = "eval/corpus.json"
REPORT_PATH = "eval/eval_report.json"


async def run_single(client: httpx.AsyncClient, entry: dict) -> dict:
    """Run a single corpus entry through the pipeline and return result + timing."""
    payload = {
        "session_id": entry["session_id"],
        "response_id": entry["id"],
        "response_text": entry["response_text"],
        "prompt_text": entry["prompt_text"],
        "grounding_context": entry.get("grounding_context", ""),
        "tier": entry.get("tier", "A"),
        "jurisdiction": entry.get("jurisdiction", "US-generic"),
        "model_confidence": entry.get("model_confidence"),
        "token_usage": entry.get("token_usage", {}),
    }

    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/pipeline/process",
            json=payload,
            timeout=10.0,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            result = resp.json()
            return {
                "entry_id": entry["id"],
                "category": entry["category"],
                "is_violation": entry["is_violation"],
                "expected_action": entry["expected_action"],
                "actual_action": result.get("routing_action", "escalate"),
                "fused_signal": result.get("fused_signal", {}),
                "latency_ms": latency_ms,
                "processing_time_ms": result.get("processing_time_ms", latency_ms),
                "degraded_layers": result.get("degraded_layers", []),
                "success": True,
                "tier": entry.get("tier", "A"),
            }
        else:
            return {
                "entry_id": entry["id"],
                "category": entry["category"],
                "is_violation": entry["is_violation"],
                "expected_action": entry["expected_action"],
                "actual_action": "error",
                "latency_ms": latency_ms,
                "success": False,
                "error": f"HTTP {resp.status_code}",
                "tier": entry.get("tier", "A"),
            }
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "entry_id": entry["id"],
            "category": entry["category"],
            "is_violation": entry["is_violation"],
            "expected_action": entry["expected_action"],
            "actual_action": "error",
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
            "tier": entry.get("tier", "A"),
        }


async def run_eval(corpus: list[dict], concurrency: int = 5) -> list[dict]:
    """Run evaluation with controlled concurrency."""
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        async def bounded_run(entry):
            async with semaphore:
                return await run_single(client, entry)

        tasks = [bounded_run(entry) for entry in corpus]
        results = await asyncio.gather(*tasks)

    return list(results)


def compute_metrics(results: list[dict]) -> dict:
    """
    Compute the 5 whitepaper measurements + per-tier breakdowns.
    
    A response is considered "flagged" if action ∈ {edit, block, escalate}.
    A response is considered "passed" if action == "pass".
    
    FPR = |safe responses flagged| / |safe responses|
    FNR = |violations passed| / |violations|
    """
    successful = [r for r in results if r.get("success", False)]
    
    if not successful:
        return {"error": "No successful results"}

    # Separate safe vs violation
    safe = [r for r in successful if not r["is_violation"]]
    violations = [r for r in successful if r["is_violation"]]

    # FPR: safe responses incorrectly flagged
    safe_flagged = sum(1 for r in safe if r["actual_action"] != "pass")
    fpr = safe_flagged / max(1, len(safe))

    # FNR: violations incorrectly passed
    violations_passed = sum(1 for r in violations if r["actual_action"] == "pass")
    fnr = violations_passed / max(1, len(violations))

    # Latency
    latencies = sorted([r["latency_ms"] for r in successful])
    median_latency = latencies[len(latencies) // 2]
    p99_latency = latencies[int(len(latencies) * 0.99)]

    # Throughput
    total_time_s = sum(r["latency_ms"] for r in successful) / 1000
    throughput = len(successful) / max(0.001, total_time_s)

    # Confusion matrix
    confusion = defaultdict(int)
    for r in successful:
        predicted = "positive" if r["actual_action"] != "pass" else "negative"
        actual = "positive" if r["is_violation"] else "negative"
        confusion[f"{actual}_{predicted}"] += 1

    # Per-tier breakdown
    tier_metrics = {}
    for tier in ["A", "B", "C"]:
        tier_results = [r for r in successful if r.get("tier") == tier]
        if tier_results:
            tier_safe = [r for r in tier_results if not r["is_violation"]]
            tier_viol = [r for r in tier_results if r["is_violation"]]
            tier_fpr = sum(1 for r in tier_safe if r["actual_action"] != "pass") / max(1, len(tier_safe))
            tier_fnr = sum(1 for r in tier_viol if r["actual_action"] == "pass") / max(1, len(tier_viol))
            tier_lats = sorted([r["latency_ms"] for r in tier_results])
            tier_metrics[tier] = {
                "count": len(tier_results),
                "fpr": round(tier_fpr, 4),
                "fnr": round(tier_fnr, 4),
                "median_latency_ms": round(tier_lats[len(tier_lats) // 2], 2),
            }

    # Per-category breakdown
    category_metrics = {}
    for cat in set(r["category"] for r in successful):
        cat_results = [r for r in successful if r["category"] == cat]
        action_dist = Counter(r["actual_action"] for r in cat_results)
        category_metrics[cat] = {
            "count": len(cat_results),
            "action_distribution": dict(action_dist),
        }

    # Degradation tracking
    degraded_count = sum(1 for r in successful if r.get("degraded_layers"))
    degraded_layers = Counter()
    for r in successful:
        for layer in r.get("degraded_layers", []):
            degraded_layers[layer] += 1

    return {
        "summary": {
            "total_evaluated": len(results),
            "successful": len(successful),
            "failed": len(results) - len(successful),
        },
        "measurements": {
            "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            "median_latency_ms": round(median_latency, 2),
            "p99_latency_ms": round(p99_latency, 2),
            "throughput_rps": round(throughput, 2),
        },
        "confusion_matrix": {
            "true_positive": confusion["positive_positive"],
            "false_positive": confusion["negative_positive"],
            "true_negative": confusion["negative_negative"],
            "false_negative": confusion["positive_negative"],
        },
        "per_tier": tier_metrics,
        "per_category": category_metrics,
        "degradation": {
            "degraded_responses": degraded_count,
            "degraded_layers": dict(degraded_layers),
        },
    }


def print_report(metrics: dict):
    """Pretty-print the evaluation report."""
    print("\n" + "=" * 72)
    print("  CONTROLPLANE MANIFOLD — EVALUATION REPORT (Section 21)")
    print("=" * 72)

    m = metrics.get("measurements", {})
    print(f"\n  Total Evaluated: {metrics['summary']['total_evaluated']}")
    print(f"  Successful:      {metrics['summary']['successful']}")
    print(f"  Failed:          {metrics['summary']['failed']}")

    print("\n  ┌─────────────────────────────────────────┐")
    print(f"  │  FPR (False Positive Rate):  {m.get('fpr', 'N/A'):>8}  │")
    print(f"  │  FNR (False Negative Rate):  {m.get('fnr', 'N/A'):>8}  │")
    print(f"  │  Median Latency (ms):        {m.get('median_latency_ms', 'N/A'):>8}  │")
    print(f"  │  P99 Latency (ms):           {m.get('p99_latency_ms', 'N/A'):>8}  │")
    print(f"  │  Throughput (rps):            {m.get('throughput_rps', 'N/A'):>8}  │")
    print("  └─────────────────────────────────────────┘")

    cm = metrics.get("confusion_matrix", {})
    print("\n  Confusion Matrix:")
    print("                  Predicted")
    print("              Positive  Negative")
    print(f"  Actual  P     {cm.get('true_positive', 0):>4}      {cm.get('false_negative', 0):>4}")
    print(f"          N     {cm.get('false_positive', 0):>4}      {cm.get('true_negative', 0):>4}")

    print("\n  Per-Tier:")
    for tier, tm in metrics.get("per_tier", {}).items():
        print(f"    Tier {tier}: n={tm['count']} FPR={tm['fpr']} FNR={tm['fnr']} median={tm['median_latency_ms']}ms")

    print("\n  Per-Category:")
    for cat, cm in metrics.get("per_category", {}).items():
        print(f"    {cat}: n={cm['count']} actions={cm['action_distribution']}")

    print("\n" + "=" * 72)


async def main():
    # Load or generate corpus
    corpus_path = Path(CORPUS_PATH)
    if not corpus_path.exists():
        from synthetic_corpus_generator import generate_corpus, save_corpus
        corpus = generate_corpus(200)
        save_corpus(corpus, str(corpus_path))
    else:
        with open(corpus_path) as f:
            corpus = json.load(f)

    print(f"Loaded {len(corpus)} evaluation entries")
    print("Running evaluation...")

    results = await run_eval(corpus, concurrency=5)
    metrics = compute_metrics(results)

    # Save results
    report_path = Path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({"metrics": metrics, "results": results}, f, indent=2)

    print_report(metrics)
    print(f"\nFull report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
