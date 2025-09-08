#!/usr/bin/env python3
"""Analyze baseline performance results and recommend optimizations.

This script analyzes the baseline test results to identify bottlenecks
and recommend which performance optimizations to implement first.
"""

import json
from pathlib import Path


class BaselineAnalyzer:
    """Analyzes baseline performance data to identify optimization opportunities."""

    def __init__(self, results_path: str = "load_tests/results"):
        """Initialize analyzer.

        Args:
            results_path: Path to results directory
        """
        self.results_path = Path(results_path)
        self.bottlenecks = []
        self.recommendations = []

    def load_latest_baseline(self) -> list[dict]:
        """Load the most recent baseline results.

        Returns:
            List of test results
        """
        baseline_files = list(self.results_path.glob("baseline_*.json"))
        if not baseline_files:
            raise FileNotFoundError(
                "No baseline results found. Run baseline tests first."
            )

        # Get most recent file
        latest_file = max(baseline_files, key=lambda f: f.stat().st_mtime)

        with open(latest_file, "r") as f:
            return json.load(f)

    def analyze_scalability(self, results: list[dict]) -> dict:
        """Analyze how the system scales with load.

        Args:
            results: Test results

        Returns:
            Scalability metrics
        """
        scalability = {
            "linear_scaling": False,
            "scaling_factor": 0.0,
            "bottleneck_point": None,
            "max_sustainable_users": 0,
            "max_sustainable_rps": 0.0,
        }

        # Find single user baseline
        single_user = next((r for r in results if r["users"] == 1), None)
        if not single_user:
            return scalability

        baseline_rps = single_user.get("rps", 1.0)

        # Analyze scaling
        for result in results:
            users = result["users"]
            rps = result.get("rps", 0)
            failure_rate = result.get("failure_rate", 0)
            p95 = result.get("p95", 0)

            # Calculate scaling efficiency
            expected_rps = baseline_rps * users
            actual_scaling = rps / expected_rps if expected_rps > 0 else 0

            # Check if still sustainable
            if failure_rate < 0.05 and p95 < 2000:
                scalability["max_sustainable_users"] = users
                scalability["max_sustainable_rps"] = rps

            # Find bottleneck point
            if actual_scaling < 0.5 and not scalability["bottleneck_point"]:
                scalability["bottleneck_point"] = users

        # Calculate overall scaling factor
        if scalability["max_sustainable_users"] > 1:
            scalability["scaling_factor"] = scalability["max_sustainable_rps"] / (
                baseline_rps * scalability["max_sustainable_users"]
            )
            scalability["linear_scaling"] = scalability["scaling_factor"] > 0.8

        return scalability

    def identify_bottlenecks(self, results: list[dict], scalability: dict) -> list[str]:
        """Identify performance bottlenecks.

        Args:
            results: Test results
            scalability: Scalability analysis

        Returns:
            List of identified bottlenecks
        """
        bottlenecks = []

        # Analyze response time patterns
        if results:
            # Check for high baseline latency
            single_user = next((r for r in results if r["users"] == 1), None)
            if single_user and single_user.get("median_response", 0) > 200:
                bottlenecks.append("high_baseline_latency")

            # Check for poor scaling
            if scalability["scaling_factor"] < 0.5:
                bottlenecks.append("poor_scaling")

            # Check for early bottleneck
            if (
                scalability["bottleneck_point"]
                and scalability["bottleneck_point"] <= 10
            ):
                bottlenecks.append("early_bottleneck")

            # Analyze latency growth
            latencies = [r.get("median_response", 0) for r in results]
            if len(latencies) > 2:
                latency_growth = (
                    latencies[-1] / latencies[0] if latencies[0] > 0 else float("inf")
                )
                if latency_growth > 10:
                    bottlenecks.append("exponential_latency_growth")

            # Check for connection limits
            max_users = max(r["users"] for r in results)
            max_rps = max(r.get("rps", 0) for r in results)
            if max_rps < max_users * 0.5:
                bottlenecks.append("connection_limits")

        return bottlenecks

    def generate_recommendations(
        self, bottlenecks: list[str], scalability: dict
    ) -> list[tuple[int, str, str]]:
        """Generate optimization recommendations based on bottlenecks.

        Args:
            bottlenecks: Identified bottlenecks
            scalability: Scalability metrics

        Returns:
            List of (priority, optimization, rationale) tuples
        """
        recommendations = []

        # Priority 1: Critical bottlenecks
        if "connection_limits" in bottlenecks:
            recommendations.append(
                (
                    1,
                    "Implement Connection Pooling",
                    (
                    "System appears to be hitting connection limits. "
                    "Connection pooling will reuse connections and dramatically improve throughput."
                ),
                )
            )

        if "high_baseline_latency" in bottlenecks:
            recommendations.append(
                (
                    1,
                    "Add Redis Caching Layer",
                    (
                    "High latency even with single user suggests expensive operations. "
                    "Caching will reduce latency for repeated queries."
                ),
                )
            )

        # Priority 2: Scaling issues
        if "poor_scaling" in bottlenecks or "early_bottleneck" in bottlenecks:
            recommendations.append(
                (
                    2,
                    "Implement Batch Processing",
                    (
                    "System doesn't scale linearly. "
                    "Batch processing can group similar requests and improve efficiency."
                ),
                )
            )

            recommendations.append(
                (
                    2,
                    "Add Horizontal Scaling",
                    "Single instance hitting limits. Deploy multiple instances behind a load balancer.",
                )
            )

        if "exponential_latency_growth" in bottlenecks:
            recommendations.append(
                (
                    2,
                    "Optimize Request Queue Management",
                    (
                    "Latency grows exponentially with load. "
                    "Implement better queue management and backpressure."
                ),
                )
            )

        # Priority 3: General optimizations
        if scalability["max_sustainable_rps"] < 50:
            recommendations.append(
                (
                    3,
                    "Add Response Streaming (SSE)",
                    "Streaming responses will improve perceived performance and reduce memory usage.",
                )
            )

        recommendations.append(
            (
                3,
                "Implement Prometheus Metrics",
                "Add detailed metrics to identify specific bottlenecks in production.",
            )
        )

        # Sort by priority
        recommendations.sort(key=lambda x: x[0])

        return recommendations

    def generate_report(self, results: list[dict]) -> str:
        """Generate comprehensive analysis report.

        Args:
            results: Test results

        Returns:
            Formatted report
        """
        report = []
        report.append("\n" + "=" * 70)
        report.append("BASELINE PERFORMANCE ANALYSIS")
        report.append("=" * 70 + "\n")

        # Analyze scalability
        scalability = self.analyze_scalability(results)

        report.append("Scalability Analysis:")
        report.append("-" * 70)
        report.append(
            f"Linear Scaling: {'✅ Yes' if scalability['linear_scaling'] else '❌ No'}"
        )
        report.append(f"Scaling Factor: {scalability['scaling_factor']:.2f}")
        report.append(f"Max Sustainable Users: {scalability['max_sustainable_users']}")
        report.append(f"Max Sustainable RPS: {scalability['max_sustainable_rps']:.2f}")
        if scalability["bottleneck_point"]:
            report.append(f"Bottleneck Point: {scalability['bottleneck_point']} users")
        report.append("")

        # Identify bottlenecks
        bottlenecks = self.identify_bottlenecks(results, scalability)

        report.append("Identified Bottlenecks:")
        report.append("-" * 70)
        if bottlenecks:
            for bottleneck in bottlenecks:
                report.append(f"⚠️  {bottleneck.replace('_', ' ').title()}")
        else:
            report.append("✅ No critical bottlenecks identified")
        report.append("")

        # Generate recommendations
        recommendations = self.generate_recommendations(bottlenecks, scalability)

        report.append("Optimization Recommendations (Priority Order):")
        report.append("-" * 70)

        current_priority = 0
        for priority, optimization, rationale in recommendations:
            if priority != current_priority:
                current_priority = priority
                report.append(f"\nPriority {priority}:")

            report.append(f"\n  📌 {optimization}")
            report.append(f"     {rationale}")

        # Implementation plan
        report.append("\n\nSuggested Implementation Plan:")
        report.append("-" * 70)

        if recommendations:
            # Group by priority
            p1_recs = [r for r in recommendations if r[0] == 1]
            p2_recs = [r for r in recommendations if r[0] == 2]
            p3_recs = [r for r in recommendations if r[0] == 3]

            if p1_recs:
                report.append("\nWeek 1: Critical Optimizations")
                for _, opt, _ in p1_recs[:2]:  # Top 2 priority 1 items
                    report.append(f"  - {opt}")

            if p2_recs:
                report.append("\nWeek 2: Scaling Improvements")
                for _, opt, _ in p2_recs[:2]:  # Top 2 priority 2 items
                    report.append(f"  - {opt}")

            if p3_recs:
                report.append("\nWeek 3: Monitoring & Fine-tuning")
                for _, opt, _ in p3_recs[:2]:  # Top 2 priority 3 items
                    report.append(f"  - {opt}")

        # Expected improvements
        report.append("\n\nExpected Improvements After Optimization:")
        report.append("-" * 70)

        if "connection_limits" in bottlenecks:
            report.append("• Connection Pooling: 3-5x throughput improvement")
        if "high_baseline_latency" in bottlenecks:
            report.append("• Caching: 50-80% latency reduction for cached queries")
        if "poor_scaling" in bottlenecks:
            report.append("• Horizontal Scaling: Linear scaling up to 100+ users")

        report.append("\n" + "=" * 70 + "\n")

        return "\n".join(report)


def main():
    """Run baseline analysis."""
    analyzer = BaselineAnalyzer()

    try:
        # Load results
        results = analyzer.load_latest_baseline()

        # Generate report
        report = analyzer.generate_report(results)
        print(report)

        # Save report
        report_file = analyzer.results_path / "analysis_report.txt"
        with open(report_file, "w") as f:
            f.write(report)

        print(f"Analysis saved to: {report_file}")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("\nPlease run baseline tests first:")
        print("  make baseline-run")
        return 1

    except Exception as e:
        print(f"❌ Error analyzing results: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
