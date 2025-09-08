"""Load testing scenarios for Weaver AI using Locust.

This module defines various load testing scenarios to establish performance baselines
and validate optimizations.
"""

import json
import random
import time

from locust import HttpUser, between, task
from locust.env import Environment


class BaseWeaverUser(HttpUser):
    """Base class for Weaver AI load testing users."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Setup that runs once per user when they start."""
        # Use a test API key for authentication
        self.headers = {
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
        }

        # Test connection with health check
        response = self.client.get("/health")
        if response.status_code != 200:
            print(f"Health check failed: {response.text}")


class SimpleQueryUser(BaseWeaverUser):
    """User that performs simple single-agent queries."""

    weight = 60  # 60% of users will be simple query users

    @task
    def ask_simple_question(self):
        """Ask a simple question that requires minimal processing."""
        questions = [
            "What is 2 + 2?",
            "What is the capital of France?",
            "How many days are in a week?",
            "What is the speed of light?",
            "What year is it?",
        ]

        query = random.choice(questions)

        with self.client.post(
            "/ask",
            json={"query": query, "user_id": f"user_{self.user_id}"},
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "answer" in data:
                        response.success()
                    else:
                        response.failure("Missing answer in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def check_health(self):
        """Periodically check health endpoint."""
        self.client.get("/health", headers=self.headers)


class WorkflowUser(BaseWeaverUser):
    """User that triggers multi-agent workflows."""

    weight = 30  # 30% of users will trigger workflows

    @task
    def run_analysis_workflow(self):
        """Run a multi-step analysis workflow."""
        topics = [
            "AI safety research",
            "Climate change impacts",
            "Quantum computing advances",
            "Space exploration updates",
            "Renewable energy trends",
        ]

        # Simulate a workflow by making multiple related queries
        topic = random.choice(topics)

        # Step 1: Research query
        with self.client.post(
            "/ask",
            json={
                "query": f"Research the latest developments in {topic}",
                "user_id": f"workflow_user_{self.user_id}",
            },
            headers=self.headers,
            name="/ask (research)",
        ) as response:
            if response.status_code != 200:
                return  # Skip remaining steps if first fails

        # Simulate processing time
        time.sleep(random.uniform(0.5, 1.5))

        # Step 2: Analysis query
        with self.client.post(
            "/ask",
            json={
                "query": f"Analyze the implications of recent {topic} findings",
                "user_id": f"workflow_user_{self.user_id}",
            },
            headers=self.headers,
            name="/ask (analysis)",
        ) as response:
            if response.status_code != 200:
                return

        # Simulate processing time
        time.sleep(random.uniform(0.5, 1.5))

        # Step 3: Summary query
        self.client.post(
            "/ask",
            json={
                "query": f"Summarize the key points about {topic} in bullet points",
                "user_id": f"workflow_user_{self.user_id}",
            },
            headers=self.headers,
            name="/ask (summary)",
        )


class BurstUser(BaseWeaverUser):
    """User that sends bursts of requests to test rate limiting."""

    weight = 10  # 10% of users will be burst users
    wait_time = between(5, 10)  # Longer wait between bursts

    @task
    def burst_queries(self):
        """Send a burst of queries rapidly."""
        burst_size = random.randint(5, 10)

        for i in range(burst_size):
            self.client.post(
                "/ask",
                json={
                    "query": f"Quick query {i}",
                    "user_id": f"burst_user_{self.user_id}",
                },
                headers=self.headers,
                name="/ask (burst)",
            )
            time.sleep(0.1)  # 100ms between requests in burst


class AuthenticationUser(BaseWeaverUser):
    """User that tests authentication endpoints."""

    weight = 5  # 5% of users test auth

    @task(3)
    def check_whoami(self):
        """Check user identity."""
        self.client.get("/whoami", headers=self.headers)

    @task
    def invalid_auth(self):
        """Test with invalid authentication."""
        with self.client.get(
            "/whoami",
            headers={"Authorization": "Bearer invalid-key"},
            catch_response=True,
        ) as response:
            if response.status_code == 401 or response.status_code == 403:
                response.success()  # Expected to fail
            else:
                response.failure(f"Expected 401/403, got {response.status_code}")


class StressTestUser(BaseWeaverUser):
    """User for stress testing with complex queries."""

    weight = 5  # 5% for stress testing

    @task
    def complex_query(self):
        """Send computationally intensive queries."""
        complex_queries = [
            "Generate a comprehensive 10-step plan for building a distributed system",
            "Analyze the following data and provide insights: "
            + str([random.random() for _ in range(100)]),
            "Compare and contrast 5 different approaches to machine learning",
            "Explain quantum computing to a 5-year-old, then to a PhD student",
            "Design a database schema for a social media platform with 1 billion users",
        ]

        query = random.choice(complex_queries)

        self.client.post(
            "/ask",
            json={
                "query": query,
                "user_id": f"stress_user_{self.user_id}",
                "max_tokens": 4096,
            },
            headers=self.headers,
            timeout=30,  # Longer timeout for complex queries
            name="/ask (complex)",
        )


# Custom event handlers for detailed metrics
def on_test_start(environment: Environment, **kwargs):
    """Called when test starts."""
    print("Load test starting...")
    print(f"Target host: {environment.host}")
    print(
        f"Total users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}"
    )


def on_test_stop(environment: Environment, **kwargs):
    """Called when test stops."""
    print("\nLoad test completed!")
    print("\n=== Final Statistics ===")
    environment.stats.print_stats()
    environment.stats.print_percentile_stats()
    environment.stats.print_error_report()


# Performance thresholds for validation
PERFORMANCE_THRESHOLDS = {
    "median_response_time": 500,  # 500ms median
    "percentile_95": 2000,  # 2s for 95th percentile
    "percentile_99": 5000,  # 5s for 99th percentile
    "failure_rate": 0.05,  # Max 5% failure rate
    "rps": 10,  # Minimum requests per second
}


def validate_performance(stats: dict) -> bool:
    """Validate performance against thresholds."""
    passed = True

    if (
        stats.get("median_response_time", float("inf"))
        > PERFORMANCE_THRESHOLDS["median_response_time"]
    ):
        print(
            f"❌ Median response time {stats['median_response_time']}ms exceeds threshold"
        )
        passed = False

    if (
        stats.get("percentile_95", float("inf"))
        > PERFORMANCE_THRESHOLDS["percentile_95"]
    ):
        print(f"❌ 95th percentile {stats['percentile_95']}ms exceeds threshold")
        passed = False

    if stats.get("failure_rate", 1.0) > PERFORMANCE_THRESHOLDS["failure_rate"]:
        print(f"❌ Failure rate {stats['failure_rate']*100:.2f}% exceeds threshold")
        passed = False

    if stats.get("rps", 0) < PERFORMANCE_THRESHOLDS["rps"]:
        print(f"❌ RPS {stats['rps']:.2f} below minimum threshold")
        passed = False

    if passed:
        print("✅ All performance thresholds met!")

    return passed
