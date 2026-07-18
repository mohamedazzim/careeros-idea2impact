"""
Real LLM Provider Benchmark — measures actual LLM completion time.

Measures: Request Start → LLM Completion → Persistence → Response Ready
NOT: API acceptance time, async queue submission, or background task creation.

Usage:
    cd backend && python -m scripts.benchmark_providers
"""

import asyncio
import json
import time
import statistics
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class BenchmarkResult:
    provider: str
    model: str
    operation: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    success: bool = True
    error: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None


@dataclass
class BenchmarkSummary:
    provider: str
    model: str
    operation: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    fallback_count: int = 0
    latency_ms_avg: float = 0.0
    latency_ms_p50: float = 0.0
    latency_ms_p95: float = 0.0
    latency_ms_p99: float = 0.0
    latency_ms_min: float = 0.0
    latency_ms_max: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    success_rate: float = 0.0
    fallback_rate: float = 0.0


BENCHMARK_PROMPTS = [
    {
        "name": "simple_completion",
        "system": "You are a helpful assistant.",
        "user": "What are the top 3 skills for an AI Engineer in 2026?",
        "max_tokens": 200,
    },
    {
        "name": "structured_json",
        "system": "Return JSON only.",
        "user": "Return a JSON object with keys: skills (list of 5 strings), experience_level (string), summary (string). Base it on this job: Senior ML Engineer at Google.",
        "max_tokens": 400,
    },
    {
        "name": "career_coaching",
        "system": "You are a senior career coach. Be concise and actionable.",
        "user": "A candidate has 5 years of Python experience but no cloud certifications. They want to transition to MLOps. Give 3 specific recommendations.",
        "max_tokens": 500,
    },
    {
        "name": "governance_check",
        "system": "You are a governance validator. Return JSON only.",
        "user": "Validate this action: sending a voice notification to a candidate about a job opportunity with match score 85. Return JSON with: approved (bool), reason (string), risk_level (string: low/medium/high).",
        "max_tokens": 300,
    },
    {
        "name": "resume_analysis",
        "system": "You are an ATS scoring engine. Return JSON only.",
        "user": "Score this resume against the job: Python, AWS, Docker, Kubernetes, ML. Resume mentions: Python, Flask, AWS S3, Docker. Return JSON with: ats_score (number 0-100), matching_skills (list), missing_skills (list).",
        "max_tokens": 400,
    },
]


async def _run_single_benchmark(provider, prompt: Dict[str, Any]) -> BenchmarkResult:
    """Run a single benchmark and measure actual LLM completion time."""
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            provider.generate(
                system_prompt=prompt["system"],
                user_message=prompt["user"],
                max_tokens=prompt["max_tokens"],
                temperature=0.0,
                cache_key_hint=f"benchmark:{prompt['name']}",
            ),
            timeout=60.0,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        tokens = result.get("tokens", {})
        return BenchmarkResult(
            provider=result.get("provider", "unknown"),
            model=result.get("model", "unknown"),
            operation=prompt["name"],
            latency_ms=round(latency_ms, 2),
            prompt_tokens=tokens.get("input", 0),
            completion_tokens=tokens.get("output", 0),
            total_tokens=tokens.get("input", 0) + tokens.get("output", 0),
            success=True,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return BenchmarkResult(
            provider="unknown",
            model="unknown",
            operation=prompt["name"],
            latency_ms=round(latency_ms, 2),
            success=False,
            error=str(e)[:200],
        )


def _compute_summary(results: List[BenchmarkResult], operation: str = "all") -> BenchmarkSummary:
    """Compute benchmark summary statistics from raw results."""
    if not results:
        return BenchmarkSummary(provider="none", model="none", operation=operation)

    latencies = [r.latency_ms for r in results]
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    fallback_used = [r for r in results if r.fallback_used]

    sorted_latencies = sorted(latencies)

    def percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        k = (len(data) - 1) * (p / 100)
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[-1]
        return data[f] + (k - f) * (data[c] - data[f])

    return BenchmarkSummary(
        provider=successful[0].provider if successful else "failed",
        model=successful[0].model if successful else "unknown",
        operation=operation,
        total_requests=len(results),
        successful=len(successful),
        failed=len(failed),
        fallback_count=len(fallback_used),
        latency_ms_avg=round(statistics.mean(latencies), 2) if latencies else 0,
        latency_ms_p50=round(percentile(sorted_latencies, 50), 2),
        latency_ms_p95=round(percentile(sorted_latencies, 95), 2),
        latency_ms_p99=round(percentile(sorted_latencies, 99), 2),
        latency_ms_min=round(min(latencies), 2) if latencies else 0,
        latency_ms_max=round(max(latencies), 2) if latencies else 0,
        total_prompt_tokens=sum(r.prompt_tokens for r in successful),
        total_completion_tokens=sum(r.completion_tokens for r in successful),
        total_tokens=sum(r.total_tokens for r in successful),
        success_rate=round(len(successful) / len(results) * 100, 2) if results else 0,
        fallback_rate=round(len(fallback_used) / len(results) * 100, 2) if results else 0,
    )


async def run_benchmark(num_runs: int = 3) -> Dict[str, Any]:
    """Run full provider benchmark suite."""
    from src.services.llm.factory import get_llm_provider, reset_llm_provider

    results: List[BenchmarkResult] = []
    start_time = time.monotonic()

    for i in range(num_runs):
        for prompt in BENCHMARK_PROMPTS:
            provider = get_llm_provider()
            result = await _run_single_benchmark(provider, prompt)
            results.append(result)
            reset_llm_provider()

    total_time_ms = (time.monotonic() - start_time) * 1000

    # Per-operation summaries
    operations = {}
    for prompt in BENCHMARK_PROMPTS:
        op_results = [r for r in results if r.operation == prompt["name"]]
        operations[prompt["name"]] = asdict(_compute_summary(op_results, prompt["name"]))

    # Overall summary
    overall = _compute_summary(results, "overall")

    return {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "num_runs_per_prompt": num_runs,
        "total_requests": len(results),
        "total_benchmark_time_ms": round(total_time_ms, 2),
        "overall": asdict(overall),
        "per_operation": operations,
        "raw_results": [asdict(r) for r in results],
    }


if __name__ == "__main__":
    result = asyncio.run(run_benchmark(num_runs=3))
    print(json.dumps(result, indent=2, default=str))
