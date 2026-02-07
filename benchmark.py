#!/usr/bin/env python
"""
VoxNav Performance Benchmarking
Measures latency, throughput, and success rates.
"""

import os
import time
import statistics
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    operation: str
    latency_ms: float
    success: bool
    model_used: str = ""
    error: str = ""

@dataclass  
class BenchmarkSummary:
    """Summary of benchmark results."""
    operation: str
    total_requests: int
    successful: int
    failed: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    success_rate: float


def benchmark_openrouter_client(n_requests: int = 5) -> List[BenchmarkResult]:
    """Benchmark raw OpenRouter API calls."""
    from core.openrouter_client import OpenRouterClient
    
    client = OpenRouterClient()
    results = []
    
    test_prompts = [
        "Say hello",
        "What is 2+2?",
        "Translate 'hello' to Hindi",
    ]
    
    print(f"\n🔬 Benchmarking OpenRouter API ({n_requests} requests)...")
    print("-" * 50)
    
    for i in range(n_requests):
        prompt = test_prompts[i % len(test_prompts)]
        start = time.perf_counter()
        
        try:
            response = client.generate(prompt, max_tokens=50)
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="openrouter_generate",
                latency_ms=latency,
                success=True
            ))
            print(f"  ✓ Request {i+1}: {latency:.0f}ms")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="openrouter_generate",
                latency_ms=latency,
                success=False,
                error=str(e)
            ))
            print(f"  ✗ Request {i+1}: {latency:.0f}ms (failed)")
        
        time.sleep(0.5)  # Avoid rate limits
    
    return results


def benchmark_intent_classification(n_requests: int = 5) -> List[BenchmarkResult]:
    """Benchmark intent classification."""
    from core.intent_dispatcher import IntentDispatcher
    
    dispatcher = IntentDispatcher()
    results = []
    
    test_inputs = [
        "Book a train ticket from Delhi to Mumbai",
        "Zomato pe pizza order karo",
        "Weather batao Bangalore ka",
        "Cancel my booking",
        "Help me with something",
    ]
    
    print(f"\n🎯 Benchmarking Intent Classification ({n_requests} requests)...")
    print("-" * 50)
    
    for i in range(n_requests):
        text = test_inputs[i % len(test_inputs)]
        start = time.perf_counter()
        
        try:
            result = dispatcher.classify(text)
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="intent_classification",
                latency_ms=latency,
                success=result.confidence > 0.5
            ))
            print(f"  ✓ Request {i+1}: {latency:.0f}ms → {result.intent.value}")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="intent_classification",
                latency_ms=latency,
                success=False,
                error=str(e)
            ))
            print(f"  ✗ Request {i+1}: {latency:.0f}ms (failed)")
        
        time.sleep(0.5)
    
    return results


def benchmark_language_detection(n_requests: int = 10) -> List[BenchmarkResult]:
    """Benchmark language detection (local, no API)."""
    from core.multilingual import MultilingualHandler
    
    handler = MultilingualHandler()
    results = []
    
    test_inputs = [
        "Book a train ticket",
        "Mujhe ticket book karni hai",
        "ट्रेन टिकट बुक करो",
        "எனக்கு டிக்கெட் வேண்டும்",
        "నాకు టికెట్ కావాలి",
    ]
    
    print(f"\n🌐 Benchmarking Language Detection ({n_requests} requests)...")
    print("-" * 50)
    
    for i in range(n_requests):
        text = test_inputs[i % len(test_inputs)]
        start = time.perf_counter()
        
        try:
            result = handler.detect_language(text)
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="language_detection",
                latency_ms=latency,
                success=True
            ))
            print(f"  ✓ Request {i+1}: {latency:.2f}ms → {result.primary_language.value}")
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            results.append(BenchmarkResult(
                operation="language_detection",
                latency_ms=latency,
                success=False,
                error=str(e)
            ))
            print(f"  ✗ Request {i+1}: {latency:.2f}ms (failed)")
    
    return results


def calculate_summary(results: List[BenchmarkResult]) -> BenchmarkSummary:
    """Calculate summary statistics from results."""
    if not results:
        return None
    
    latencies = [r.latency_ms for r in results if r.success]
    successful = sum(1 for r in results if r.success)
    
    if not latencies:
        latencies = [0]
    
    sorted_latencies = sorted(latencies)
    p50_idx = int(len(sorted_latencies) * 0.5)
    p95_idx = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
    
    return BenchmarkSummary(
        operation=results[0].operation,
        total_requests=len(results),
        successful=successful,
        failed=len(results) - successful,
        avg_latency_ms=statistics.mean(latencies),
        min_latency_ms=min(latencies),
        max_latency_ms=max(latencies),
        p50_latency_ms=sorted_latencies[p50_idx],
        p95_latency_ms=sorted_latencies[p95_idx],
        success_rate=successful / len(results) * 100
    )


def print_summary(summary: BenchmarkSummary):
    """Print formatted summary."""
    print(f"""
┌{'─' * 50}┐
│ {summary.operation.upper():^48} │
├{'─' * 50}┤
│ Total Requests:    {summary.total_requests:>28} │
│ Successful:        {summary.successful:>28} │
│ Failed:            {summary.failed:>28} │
│ Success Rate:      {summary.success_rate:>27.1f}% │
├{'─' * 50}┤
│ Avg Latency:       {summary.avg_latency_ms:>24.0f} ms │
│ Min Latency:       {summary.min_latency_ms:>24.0f} ms │
│ Max Latency:       {summary.max_latency_ms:>24.0f} ms │
│ P50 Latency:       {summary.p50_latency_ms:>24.0f} ms │
│ P95 Latency:       {summary.p95_latency_ms:>24.0f} ms │
└{'─' * 50}┘""")


def run_full_benchmark():
    """Run all benchmarks."""
    print("""
╔══════════════════════════════════════════════════════════╗
║           VoxNav Performance Benchmark                   ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Check API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ OPENROUTER_API_KEY not set!")
        return
    
    all_results = {}
    
    # 1. Language Detection (local - fast)
    lang_results = benchmark_language_detection(10)
    all_results["language_detection"] = calculate_summary(lang_results)
    
    # 2. OpenRouter API (external - slower)
    api_results = benchmark_openrouter_client(5)
    all_results["openrouter_api"] = calculate_summary(api_results)
    
    # 3. Intent Classification (uses API)
    intent_results = benchmark_intent_classification(5)
    all_results["intent_classification"] = calculate_summary(intent_results)
    
    # Print summaries
    print("\n" + "=" * 54)
    print("                    SUMMARY")
    print("=" * 54)
    
    for name, summary in all_results.items():
        if summary:
            print_summary(summary)
    
    # Overall assessment
    print("\n📊 Performance Assessment:")
    
    lang_avg = all_results.get("language_detection")
    api_avg = all_results.get("openrouter_api")
    intent_avg = all_results.get("intent_classification")
    
    if lang_avg and lang_avg.avg_latency_ms < 10:
        print("  ✅ Language Detection: EXCELLENT (local processing)")
    
    if api_avg:
        if api_avg.avg_latency_ms < 2000:
            print(f"  ✅ OpenRouter API: GOOD ({api_avg.avg_latency_ms:.0f}ms avg)")
        elif api_avg.avg_latency_ms < 5000:
            print(f"  ⚠️ OpenRouter API: SLOW ({api_avg.avg_latency_ms:.0f}ms avg)")
        else:
            print(f"  ❌ OpenRouter API: VERY SLOW ({api_avg.avg_latency_ms:.0f}ms avg)")
    
    if intent_avg:
        print(f"  📍 Intent Classification: {intent_avg.success_rate:.0f}% success rate")


if __name__ == "__main__":
    run_full_benchmark()
