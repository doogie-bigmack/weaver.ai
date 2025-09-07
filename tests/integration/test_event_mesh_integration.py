"""Integration tests for EventMesh with simulated agents."""

from __future__ import annotations

import asyncio
import time

import pytest
import pytest_asyncio
from pydantic import BaseModel

from weaver_ai.events import AccessPolicy, EventMesh


# Define workflow event types
class SalesData(BaseModel):
    """Raw sales data event."""

    quarter: str
    sales: list[float]
    regions: list[str]


class SalesAnalysis(BaseModel):
    """Analysis result event."""

    quarter: str
    total_sales: float
    average_sale: float
    top_region: str
    insights: list[str]


class QuarterlyReport(BaseModel):
    """Final report event."""

    quarter: str
    summary: str
    metrics: dict


class ErrorEvent(BaseModel):
    """Error event for testing error handling."""

    error_message: str
    source_event_id: str


class TestEventMeshIntegration:
    """Integration tests for EventMesh workflows."""

    @pytest_asyncio.fixture
    async def mesh(self):
        """Create event mesh for testing."""
        mesh = EventMesh()
        yield mesh
        await mesh.clear()

    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self, mesh):
        """Test a complete multi-agent workflow."""
        processed_events = {"analyst": [], "reporter": [], "notifier": []}

        # Simulated Analyst Agent
        async def analyst_agent():
            async for event in mesh.subscribe(
                [SalesData], agent_id="analyst", agent_roles=["analyst"]
            ):
                data: SalesData = event.data
                processed_events["analyst"].append(data)

                # Perform analysis
                total = sum(data.sales)
                avg = total / len(data.sales) if data.sales else 0
                top_region = data.regions[0] if data.regions else "unknown"

                analysis = SalesAnalysis(
                    quarter=data.quarter,
                    total_sales=total,
                    average_sale=avg,
                    top_region=top_region,
                    insights=[
                        f"Total sales: ${total:,.2f}",
                        f"Average sale: ${avg:,.2f}",
                        f"Top region: {top_region}",
                    ],
                )

                # Publish analysis
                await mesh.publish(
                    SalesAnalysis,
                    analysis,
                    metadata=event.metadata,  # Preserve correlation
                )

                if len(processed_events["analyst"]) >= 1:
                    break

        # Simulated Reporter Agent
        async def reporter_agent():
            async for event in mesh.subscribe(
                [SalesAnalysis], agent_id="reporter", agent_roles=["reporter"]
            ):
                analysis: SalesAnalysis = event.data
                processed_events["reporter"].append(analysis)

                # Generate report
                report = QuarterlyReport(
                    quarter=analysis.quarter,
                    summary=f"Q{analysis.quarter} Performance Report",
                    metrics={
                        "total_sales": analysis.total_sales,
                        "average_sale": analysis.average_sale,
                        "top_region": analysis.top_region,
                        "insights_count": len(analysis.insights),
                    },
                )

                # Publish report
                await mesh.publish(QuarterlyReport, report, metadata=event.metadata)

                if len(processed_events["reporter"]) >= 1:
                    break

        # Simulated Notifier Agent
        async def notifier_agent():
            async for event in mesh.subscribe(
                [QuarterlyReport], agent_id="notifier", agent_roles=["notifier"]
            ):
                report: QuarterlyReport = event.data
                processed_events["notifier"].append(report)

                if len(processed_events["notifier"]) >= 1:
                    break

        # Start all agents
        await asyncio.gather(
            asyncio.create_task(analyst_agent()),
            asyncio.create_task(reporter_agent()),
            asyncio.create_task(notifier_agent()),
            return_exceptions=True,
        )

        # Give agents time to start
        await asyncio.sleep(0.1)

        # Trigger workflow with initial data
        initial_data = SalesData(
            quarter="Q4",
            sales=[1000.0, 1500.0, 2000.0, 1200.0],
            regions=["North", "South", "East", "West"],
        )

        await mesh.publish(SalesData, initial_data)

        # Wait for workflow to complete
        await asyncio.sleep(0.5)

        # Verify workflow execution
        assert len(processed_events["analyst"]) == 1
        assert len(processed_events["reporter"]) == 1
        assert len(processed_events["notifier"]) == 1

        # Verify data flow
        assert processed_events["analyst"][0].quarter == "Q4"
        assert processed_events["reporter"][0].total_sales == 5700.0
        assert processed_events["notifier"][0].metrics["top_region"] == "North"

    @pytest.mark.asyncio
    async def test_concurrent_workflows(self, mesh):
        """Test multiple concurrent workflows."""
        completed_workflows = []

        async def workflow_processor(workflow_id: int):
            """Process a single workflow instance."""
            results = []

            # Subscribe to workflow events
            async for event in mesh.subscribe(
                [SalesAnalysis], agent_id=f"processor_{workflow_id}"
            ):
                if event.metadata.correlation_id == f"workflow_{workflow_id}":
                    results.append(event.data)
                    break

            return workflow_id, results

        # Start multiple workflow processors
        processors = [asyncio.create_task(workflow_processor(i)) for i in range(10)]

        await asyncio.sleep(0.1)

        # Trigger multiple workflows
        for i in range(10):
            data = SalesData(
                quarter=f"Q{i % 4 + 1}",
                sales=[float(i * 100 + j * 10) for j in range(5)],
                regions=[f"Region_{j}" for j in range(5)],
            )

            # Each workflow has unique correlation ID
            from weaver_ai.events import EventMetadata

            metadata = EventMetadata(correlation_id=f"workflow_{i}")

            await mesh.publish(SalesData, data, metadata=metadata)

            # Also publish analysis for this workflow
            analysis = SalesAnalysis(
                quarter=data.quarter,
                total_sales=sum(data.sales),
                average_sale=sum(data.sales) / len(data.sales),
                top_region=data.regions[0],
                insights=[f"Workflow {i} analysis"],
            )

            await mesh.publish(SalesAnalysis, analysis, metadata=metadata)

        # Wait for all processors to complete
        results = await asyncio.gather(*processors)
        completed_workflows = [r[0] for r in results if r[1]]

        # Verify all workflows completed
        assert len(completed_workflows) == 10
        assert sorted(completed_workflows) == list(range(10))

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mesh):
        """Test error handling in workflows."""
        errors_caught = []

        async def error_handler():
            """Agent that handles errors."""
            async for event in mesh.subscribe([ErrorEvent], agent_id="error_handler"):
                errors_caught.append(event.data)
                if len(errors_caught) >= 1:
                    break

        async def faulty_agent():
            """Agent that generates errors."""
            async for event in mesh.subscribe([SalesData], agent_id="faulty_agent"):
                # Simulate error
                error = ErrorEvent(
                    error_message="Failed to process sales data",
                    source_event_id=event.metadata.event_id,
                )
                await mesh.publish(ErrorEvent, error)
                break

        # Start agents
        error_task = asyncio.create_task(error_handler())
        faulty_task = asyncio.create_task(faulty_agent())

        await asyncio.sleep(0.1)

        # Trigger faulty workflow
        await mesh.publish(SalesData, SalesData(quarter="Q1", sales=[], regions=[]))

        # Wait for error handling
        await asyncio.gather(error_task, faulty_task)

        assert len(errors_caught) == 1
        assert "Failed to process" in errors_caught[0].error_message

    @pytest.mark.asyncio
    async def test_access_controlled_workflow(self, mesh):
        """Test workflow with access controls."""
        public_results = []
        confidential_results = []

        async def public_agent():
            """Agent with public access."""
            async for event in mesh.subscribe(
                [SalesAnalysis], agent_id="public_agent", agent_level="public"
            ):
                public_results.append(event.data)

        async def confidential_agent():
            """Agent with confidential access."""
            async for event in mesh.subscribe(
                [SalesAnalysis],
                agent_id="confidential_agent",
                agent_level="confidential",
            ):
                confidential_results.append(event.data)
                if len(confidential_results) >= 2:
                    break

        # Start agents
        public_task = asyncio.create_task(public_agent())
        conf_task = asyncio.create_task(confidential_agent())

        await asyncio.sleep(0.1)

        # Publish public analysis
        public_analysis = SalesAnalysis(
            quarter="Q1",
            total_sales=1000.0,
            average_sale=100.0,
            top_region="North",
            insights=["Public insight"],
        )
        await mesh.publish(
            SalesAnalysis,
            public_analysis,
            access_policy=AccessPolicy(min_level="public"),
        )

        # Publish confidential analysis
        conf_analysis = SalesAnalysis(
            quarter="Q2",
            total_sales=5000.0,
            average_sale=500.0,
            top_region="Secret",
            insights=["Confidential insight"],
        )
        await mesh.publish(
            SalesAnalysis,
            conf_analysis,
            access_policy=AccessPolicy(min_level="confidential"),
        )

        # Wait for confidential agent to complete
        await conf_task

        # Cancel public agent
        await asyncio.sleep(0.2)
        public_task.cancel()

        # Verify access control
        assert len(public_results) == 1  # Only saw public event
        assert len(confidential_results) == 2  # Saw both events
        assert public_results[0].quarter == "Q1"
        assert confidential_results[0].quarter == "Q1"
        assert confidential_results[1].quarter == "Q2"

    @pytest.mark.asyncio
    async def test_performance_many_subscribers(self, mesh):
        """Test performance with many subscribers."""
        num_subscribers = 100
        received_counts = {}

        async def subscriber(sub_id: int):
            """Individual subscriber."""
            count = 0
            async for _ in mesh.subscribe([SalesData], agent_id=f"sub_{sub_id}"):
                count += 1
                if count >= 10:
                    break
            received_counts[sub_id] = count

        # Start many subscribers
        start_time = time.time()
        subscribers = [
            asyncio.create_task(subscriber(i)) for i in range(num_subscribers)
        ]

        await asyncio.sleep(0.2)

        # Publish events
        for i in range(10):
            await mesh.publish(
                SalesData,
                SalesData(
                    quarter=f"Q{i % 4 + 1}",
                    sales=[float(i * 100)],
                    regions=[f"Region_{i}"],
                ),
            )

        # Wait for all subscribers
        await asyncio.gather(*subscribers)
        elapsed = time.time() - start_time

        # Verify all subscribers received all events
        assert len(received_counts) == num_subscribers
        assert all(count == 10 for count in received_counts.values())

        # Performance check - should complete reasonably fast
        assert elapsed < 5.0  # Should complete in under 5 seconds

        stats = mesh.get_stats()
        assert stats["total_events"] == 10
