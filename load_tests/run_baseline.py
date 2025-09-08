#!/usr/bin/env python3
"""Run baseline performance tests to establish current capabilities.

This script runs a series of load tests with increasing user counts to
determine the current system's performance characteristics.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class BaselineTestRunner:
    """Manages baseline performance testing."""

    def __init__(self, host: str = "http://localhost:8000"):
        """Initialize test runner.

        Args:
            host: Target host for testing
        """
        self.host = host
        self.results_dir = Path("load_tests/results")
        self.results_dir.mkdir(exist_ok=True)

        # Test configurations (users, spawn_rate, duration)
        self.test_configs = [
            {"users": 1, "spawn_rate": 1, "duration": "30s", "name": "single_user"},
            {"users": 5, "spawn_rate": 1, "duration": "60s", "name": "light_load"},
            {"users": 10, "spawn_rate": 2, "duration": "60s", "name": "moderate_load"},
            {"users": 25, "spawn_rate": 5, "duration": "120s", "name": "normal_load"},
            {"users": 50, "spawn_rate": 5, "duration": "120s", "name": "heavy_load"},
            {"users": 100, "spawn_rate": 10, "duration": "180s", "name": "stress_test"},
        ]

    def run_test(self, config: dict[str, Any]) -> dict[str, Any]:
        """Run a single test configuration.

        Args:
            config: Test configuration

        Returns:
            Test results dictionary
        """
        print(f"\n{'='*60}")
        print(f"Running test: {config['name']}")
        print(f"Users: {config['users']}, Duration: {config['duration']}")
        print(f"{'='*60}\n")

        # Build locust command
        stats_file = self.results_dir / f"{config['name']}_stats"

        cmd = [
            "locust",
            "-f",
            "load_tests/locustfile.py",
            "--host",
            self.host,
            "--users",
            str(config["users"]),
            "--spawn-rate",
            str(config["spawn_rate"]),
            "--run-time",
            config["duration"],
            "--headless",
            "--csv",
            str(stats_file),
            "--html",
            str(self.results_dir / f"{config['name']}.html"),
            "--print-stats",
            "--only-summary",
        ]

        # Run the test
        start_time = datetime.now()
        result = subprocess.run(cmd, capture_output=True, text=True)
        end_time = datetime.now()

        # Parse results
        results = {
            "name": config["name"],
            "users": config["users"],
            "duration": config["duration"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "elapsed_seconds": (end_time - start_time).total_seconds(),
        }

        # Try to parse CSV stats if generated
        stats_file_path = Path(f"{stats_file}_stats.csv")
        if stats_file_path.exists():
            try:
                df = pd.read_csv(stats_file_path)

                # Extract aggregate metrics
                aggregate = df[df["Name"] == "Aggregated"]
                if not aggregate.empty:
                    row = aggregate.iloc[0]
                    results.update(
                        {
                            "total_requests": int(row.get("Request Count", 0)),
                            "failure_count": int(row.get("Failure Count", 0)),
                            "median_response": float(
                                row.get("Median Response Time", 0)
                            ),
                            "average_response": float(
                                row.get("Average Response Time", 0)
                            ),
                            "min_response": float(row.get("Min Response Time", 0)),
                            "max_response": float(row.get("Max Response Time", 0)),
                            "rps": float(row.get("Requests/s", 0)),
                            "failures_per_sec": float(row.get("Failures/s", 0)),
                        }
                    )

                    # Calculate derived metrics
                    if results["total_requests"] > 0:
                        results["failure_rate"] = (
                            results["failure_count"] / results["total_requests"]
                        )
                    else:
                        results["failure_rate"] = 0.0

            except Exception as e:
                print(f"Warning: Could not parse stats CSV: {e}")

        # Parse console output for additional metrics
        if "Response time percentiles" in result.stdout:
            lines = result.stdout.split("\n")
            for line in lines:
                if "50%" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        results["p50"] = float(parts[1])
                elif "95%" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        results["p95"] = float(parts[1])
                elif "99%" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        results["p99"] = float(parts[1])

        return results

    def run_baseline_suite(self) -> list[dict[str, Any]]:
        """Run the complete baseline test suite.

        Returns:
            List of test results
        """
        print("\n" + "=" * 70)
        print("STARTING BASELINE PERFORMANCE TEST SUITE")
        print(f"Target: {self.host}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 70)

        all_results = []

        for config in self.test_configs:
            results = self.run_test(config)
            all_results.append(results)

            # Save intermediate results
            self.save_results(all_results)

            # Cool down between tests
            if config != self.test_configs[-1]:
                print("\nCooling down for 10 seconds...")
                time.sleep(10)

        return all_results

    def save_results(self, results: list[dict[str, Any]]):
        """Save test results to JSON file.

        Args:
            results: List of test results
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"baseline_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: {filename}")

    def generate_report(self, results: list[dict[str, Any]]) -> str:
        """Generate a performance report.

        Args:
            results: List of test results

        Returns:
            Formatted report string
        """
        report = []
        report.append("\n" + "=" * 70)
        report.append("BASELINE PERFORMANCE REPORT")
        report.append("=" * 70 + "\n")

        # Summary table
        report.append("Test Results Summary:")
        report.append("-" * 70)
        header = (
            f"{'Test':<15} {'Users':<8} {'RPS':<10} "
            f"{'P50 (ms)':<12} {'P95 (ms)':<12} {'Failures':<10}"
        )
        report.append(header)
        report.append("-" * 70)

        for r in results:
            report.append(
                f"{r['name']:<15} "
                f"{r.get('users', 'N/A'):<8} "
                f"{r.get('rps', 0):<10.2f} "
                f"{r.get('median_response', 0):<12.1f} "
                f"{r.get('p95', 0):<12.1f} "
                f"{r.get('failure_rate', 0)*100:<10.2f}%"
            )

        report.append("-" * 70)

        # Key findings
        report.append("\nKey Findings:")
        report.append("-" * 70)

        # Find breaking point
        breaking_point = None
        for r in results:
            if r.get("failure_rate", 0) > 0.05 or r.get("p95", 0) > 5000:
                breaking_point = r
                break

        if breaking_point:
            report.append(
                f"⚠️  System degradation starts at {breaking_point['users']} users"
            )
            report.append(f"   - P95 latency: {breaking_point.get('p95', 0):.1f}ms")
            report.append(
                f"   - Failure rate: {breaking_point.get('failure_rate', 0)*100:.2f}%"
            )

        # Maximum sustainable load
        sustainable = [
            r
            for r in results
            if r.get("failure_rate", 0) <= 0.01 and r.get("p95", 0) <= 2000
        ]
        if sustainable:
            max_sustainable = sustainable[-1]
            report.append(
                f"\n✅ Maximum sustainable load: {max_sustainable['users']} users"
            )
            report.append(f"   - RPS: {max_sustainable.get('rps', 0):.2f}")
            report.append(f"   - P95 latency: {max_sustainable.get('p95', 0):.1f}ms")

        # Performance bottlenecks
        report.append("\n\nPerformance Characteristics:")
        report.append("-" * 70)

        if results:
            first = results[0]
            last = results[-1]

            if first.get("rps", 0) > 0 and last.get("rps", 0) > 0:
                scalability = last.get("rps", 0) / (
                    first.get("rps", 0) * last.get("users", 1)
                )
                report.append(f"Scalability factor: {scalability:.2f}")

                if scalability < 0.5:
                    report.append("⚠️  Poor scalability - likely bottleneck in system")
                elif scalability < 0.8:
                    report.append("⚡ Moderate scalability - room for optimization")
                else:
                    report.append("✅ Good scalability")

        report.append("\n" + "=" * 70)

        return "\n".join(report)


def main():
    """Run baseline tests and generate report."""
    # Check if server is running
    import requests  # type: ignore[import-untyped]

    host = os.getenv("TEST_HOST", "http://localhost:8000")

    try:
        response = requests.get(f"{host}/health", timeout=5)
        if response.status_code != 200:
            print(f"⚠️  Warning: Health check returned {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: Cannot connect to {host}")
        print(f"   {e}")
        print("\nPlease ensure the Weaver AI server is running:")
        print("  python -m weaver_ai.main --host 0.0.0.0 --port 8000")
        return 1

    # Run tests
    runner = BaselineTestRunner(host)
    results = runner.run_baseline_suite()

    # Generate and print report
    report = runner.generate_report(results)
    print(report)

    # Save report
    report_file = (
        runner.results_dir
        / f"baseline_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(report_file, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {report_file}")

    return 0


if __name__ == "__main__":
    exit(main())
