#!/usr/bin/env python3
"""Quick baseline performance test for Weaver AI."""

import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


def make_request(session, url, query="What is 2+2?"):
    """Make a single request and measure response time."""
    start = time.time()
    try:
        response = session.post(
            url,
            json={"query": query, "user_id": "test_user"},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        elapsed = time.time() - start

        return {
            "status": response.status_code,
            "elapsed": elapsed,
            "success": response.status_code == 200,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {"status": 0, "elapsed": elapsed, "success": False, "error": str(e)}


def run_test(host="http://localhost:8005", users=1, duration=30):
    """Run a simple load test."""
    print(f"\n{'='*60}")
    print(f"Running Quick Baseline Test")
    print(f"Host: {host}")
    print(f"Users: {users}")
    print(f"Duration: {duration}s")
    print(f"{'='*60}\n")

    # Check if service is up
    try:
        r = requests.get(f"{host}/health", timeout=5)
        print(f"✅ Service is up (health check: {r.status_code})")
    except:
        print("❌ Service is not responding")
        return None

    # Prepare for test
    url = f"{host}/ask"
    session = requests.Session()
    results = []
    start_time = time.time()

    print(f"\nStarting test at {datetime.now().strftime('%H:%M:%S')}")
    print("Progress: ", end="", flush=True)

    # Run test with concurrent users
    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = []
        request_count = 0

        while time.time() - start_time < duration:
            # Submit requests for all users
            for _ in range(users):
                future = executor.submit(make_request, session, url)
                futures.append(future)
                request_count += 1

            # Collect results
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                # Show progress
                if len(results) % 10 == 0:
                    print(".", end="", flush=True)

            futures.clear()

            # Small delay between batches
            time.sleep(0.1)

    print(" Done!\n")

    # Calculate metrics
    total_time = time.time() - start_time
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    response_times = [r["elapsed"] for r in successful]

    if not response_times:
        print("❌ No successful requests")
        return None

    response_times.sort()

    metrics = {
        "total_requests": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "duration": total_time,
        "rps": len(results) / total_time,
        "success_rate": len(successful) / len(results) * 100,
        "min_response": min(response_times),
        "max_response": max(response_times),
        "avg_response": sum(response_times) / len(response_times),
        "p50": response_times[int(len(response_times) * 0.50)],
        "p95": response_times[int(len(response_times) * 0.95)],
        "p99": (
            response_times[int(len(response_times) * 0.99)]
            if len(response_times) > 100
            else response_times[-1]
        ),
    }

    return metrics


def print_results(metrics):
    """Print formatted results."""
    if not metrics:
        return

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    print(f"\nThroughput:")
    print(f"  Total Requests: {metrics['total_requests']}")
    print(f"  Successful: {metrics['successful']}")
    print(f"  Failed: {metrics['failed']}")
    print(f"  Duration: {metrics['duration']:.2f}s")
    print(f"  RPS: {metrics['rps']:.2f}")
    print(f"  Success Rate: {metrics['success_rate']:.1f}%")

    print(f"\nLatency (seconds):")
    print(f"  Min: {metrics['min_response']:.3f}s")
    print(f"  Avg: {metrics['avg_response']:.3f}s")
    print(f"  P50: {metrics['p50']:.3f}s")
    print(f"  P95: {metrics['p95']:.3f}s")
    print(f"  P99: {metrics['p99']:.3f}s")
    print(f"  Max: {metrics['max_response']:.3f}s")

    print("\n" + "=" * 60)


def main():
    """Run progressive load tests."""
    host = "http://localhost:8005"

    # Test configurations
    tests = [
        {"users": 1, "duration": 10, "name": "Single User"},
        {"users": 5, "duration": 20, "name": "Light Load"},
        {"users": 10, "duration": 20, "name": "Moderate Load"},
        {"users": 25, "duration": 30, "name": "Heavy Load"},
    ]

    all_results = []

    for test in tests:
        print(f"\n\n{'#'*60}")
        print(f"TEST: {test['name']}")
        print(f"{'#'*60}")

        metrics = run_test(host, test["users"], test["duration"])

        if metrics:
            metrics["test_name"] = test["name"]
            metrics["users"] = test["users"]
            all_results.append(metrics)
            print_results(metrics)

        # Cool down between tests
        if test != tests[-1]:
            print("\nCooling down for 5 seconds...")
            time.sleep(5)

    # Summary
    print("\n\n" + "=" * 70)
    print("BASELINE SUMMARY")
    print("=" * 70)
    print(
        f"\n{'Test':<15} {'Users':<8} {'RPS':<10} {'P50 (ms)':<12} {'P95 (ms)':<12} {'Success':<10}"
    )
    print("-" * 70)

    for r in all_results:
        print(
            f"{r['test_name']:<15} "
            f"{r['users']:<8} "
            f"{r['rps']:<10.2f} "
            f"{r['p50']*1000:<12.1f} "
            f"{r['p95']*1000:<12.1f} "
            f"{r['success_rate']:<10.1f}%"
        )

    print("-" * 70)

    # Identify bottlenecks
    print("\n🔍 ANALYSIS:")
    print("-" * 70)

    if all_results:
        # Check scalability
        single_user_rps = all_results[0]["rps"] if all_results else 0
        last_test_rps = all_results[-1]["rps"] if all_results else 0
        last_test_users = all_results[-1]["users"] if all_results else 1

        if single_user_rps > 0:
            scaling_efficiency = (
                last_test_rps / (single_user_rps * last_test_users)
            ) * 100
            print(f"Scaling Efficiency: {scaling_efficiency:.1f}%")

            if scaling_efficiency < 50:
                print("⚠️  Poor scaling - system has bottlenecks")
            elif scaling_efficiency < 80:
                print("⚡ Moderate scaling - room for optimization")
            else:
                print("✅ Good scaling")

        # Check latency
        if all_results[-1]["p95"] > 2.0:
            print("⚠️  High P95 latency under load")

        # Check error rate
        if all_results[-1]["success_rate"] < 95:
            print("⚠️  High error rate under load")

    print("\n" + "=" * 70)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"load_tests/results/quick_baseline_{timestamp}.json"

    import os

    os.makedirs("load_tests/results", exist_ok=True)

    with open(filename, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nResults saved to: {filename}")

    return all_results


if __name__ == "__main__":
    results = main()
