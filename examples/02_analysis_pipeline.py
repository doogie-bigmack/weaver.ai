#!/usr/bin/env python3
"""Multi-Agent Analysis Pipeline Example.

This example demonstrates a powerful multi-agent workflow where:
1. Researcher gathers data on a topic
2. Analyst processes and analyzes the data
3. Reporter creates a final report

The workflow automatically routes data between agents based on types.
"""

import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from weaver_ai.agents import BaseAgent, agent
from weaver_ai.events import Event
from weaver_ai.workflow import Workflow


# Data models for the workflow
class ResearchRequest(BaseModel):
    """Request to research a topic."""

    topic: str
    depth: str = "moderate"  # shallow, moderate, deep
    max_sources: int = 5


class ResearchData(BaseModel):
    """Raw research data collected."""

    topic: str
    sources: list[str] = Field(default_factory=list)
    raw_content: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=datetime.now)


class Analysis(BaseModel):
    """Analyzed data with insights."""

    topic: str
    key_findings: list[str] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    analysis_method: str = "statistical"


class Report(BaseModel):
    """Final formatted report."""

    title: str
    executive_summary: str
    sections: list[dict] = Field(default_factory=list)
    conclusions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


# Agent implementations
@agent(
    agent_type="researcher",
    capabilities=["research:topics", "gather:data"],
    memory_strategy="analyst",
)
class Researcher(BaseAgent):
    """Researches topics and gathers data."""

    async def process(self, event: Event) -> ResearchData:
        """Research a topic and gather data.

        Args:
            event: Event containing ResearchRequest

        Returns:
            ResearchData with collected information
        """
        # Extract request
        if isinstance(event.data, ResearchRequest):
            request = event.data
        elif isinstance(event.data, str):
            request = ResearchRequest(topic=event.data)
        else:
            request = ResearchRequest(topic=str(event.data))

        print(f"  🔍 Researching: {request.topic}")

        # Simulate research using model router
        research_data = ResearchData(topic=request.topic)

        if self.model_router:
            # Generate research content
            prompt = f"""Research the topic: {request.topic}
            Depth: {request.depth}
            Provide key information and sources."""

            response = await self.model_router.generate(prompt)
            research_data.raw_content = [response.text]
            research_data.sources = [
                f"Source {i+1}: Academic Database"
                for i in range(min(3, request.max_sources))
            ]
        else:
            # Mock data for testing
            research_data.raw_content = [
                f"Research finding 1 about {request.topic}",
                f"Research finding 2 about {request.topic}",
                f"Research finding 3 about {request.topic}",
            ]
            research_data.sources = ["Source 1", "Source 2", "Source 3"]

        research_data.metadata = {
            "depth": request.depth,
            "sources_found": len(research_data.sources),
        }

        # Store in memory for future reference
        if self.memory:
            await self.memory.add_to_short_term(
                f"research_{request.topic}", research_data.dict()
            )

        print(f"  ✅ Found {len(research_data.sources)} sources")
        return research_data


@agent(
    agent_type="analyst",
    capabilities=["analyze:data", "extract:insights"],
    memory_strategy="analyst",
)
class Analyst(BaseAgent):
    """Analyzes research data and extracts insights."""

    async def process(self, event: Event) -> Analysis:
        """Analyze research data.

        Args:
            event: Event containing ResearchData

        Returns:
            Analysis with insights and recommendations
        """
        if not isinstance(event.data, ResearchData):
            raise ValueError("Analyst requires ResearchData")

        research = event.data
        print(f"  📊 Analyzing data for: {research.topic}")

        analysis = Analysis(topic=research.topic)

        if self.model_router:
            # Use LLM to analyze the research
            prompt = f"""Analyze this research data about {research.topic}:

            Content: {' '.join(research.raw_content)}
            Sources: {', '.join(research.sources)}

            Provide:
            1. Key findings
            2. Trends
            3. Recommendations"""

            await self.model_router.generate(prompt)

            # Parse response (in production, use structured output)
            analysis.key_findings = [
                "Finding 1 from analysis",
                "Finding 2 from analysis",
                "Finding 3 from analysis",
            ]
            analysis.trends = ["Trend 1", "Trend 2"]
            analysis.recommendations = ["Recommendation 1", "Recommendation 2"]
            analysis.confidence_score = 0.85
        else:
            # Mock analysis for testing
            analysis.key_findings = [
                f"Key finding about {research.topic}",
                f"Important insight about {research.topic}",
                f"Critical observation about {research.topic}",
            ]
            analysis.trends = [
                f"Increasing interest in {research.topic}",
                f"Emerging patterns in {research.topic}",
            ]
            analysis.recommendations = [
                f"Consider investigating {research.topic} further",
                f"Monitor developments in {research.topic}",
            ]
            analysis.confidence_score = 0.75

        # Store analysis in long-term memory
        if self.memory:
            await self.memory.add_to_long_term(
                f"analysis_{research.topic}", analysis.dict()
            )

        print(f"  ✅ Analysis complete (confidence: {analysis.confidence_score})")
        return analysis


@agent(
    agent_type="reporter",
    capabilities=["generate:reports", "format:documents"],
    memory_strategy="minimal",
)
class Reporter(BaseAgent):
    """Creates formatted reports from analysis."""

    async def process(self, event: Event) -> Report:
        """Generate a report from analysis.

        Args:
            event: Event containing Analysis

        Returns:
            Report with formatted content
        """
        if not isinstance(event.data, Analysis):
            raise ValueError("Reporter requires Analysis")

        analysis = event.data
        print(f"  📝 Generating report for: {analysis.topic}")

        # Create report structure
        report = Report(
            title=f"Analysis Report: {analysis.topic}",
            executive_summary=f"This report presents findings on {analysis.topic} "
            f"based on comprehensive research and analysis.",
        )

        # Add sections
        report.sections = [
            {"title": "Key Findings", "content": analysis.key_findings},
            {"title": "Identified Trends", "content": analysis.trends},
            {"title": "Recommendations", "content": analysis.recommendations},
            {
                "title": "Methodology",
                "content": [
                    f"Analysis method: {analysis.analysis_method}",
                    f"Confidence score: {analysis.confidence_score}",
                ],
            },
        ]

        # Add conclusions
        report.conclusions = [
            f"The analysis of {analysis.topic} reveals significant insights.",
            f"Confidence in findings: {analysis.confidence_score * 100:.0f}%",
            "Further research recommended in identified trend areas.",
        ]

        print(f"  ✅ Report generated with {len(report.sections)} sections")
        return report


async def main():
    """Run the multi-agent analysis pipeline."""
    print("=" * 60)
    print("Multi-Agent Analysis Pipeline Example")
    print("=" * 60)

    # Create the workflow with automatic type-based routing
    workflow = (
        Workflow("analysis_pipeline")
        .add_agents(Researcher, Analyst, Reporter)
        .with_observability(True)
        .with_error_handling("retry", max_retries=3)
        .with_timeout(60)
    )

    # Example 1: Simple topic analysis
    print("\n1. Analyzing 'AI Safety':")
    print("-" * 40)

    request = ResearchRequest(topic="AI Safety", depth="moderate", max_sources=5)

    report = await workflow.run(request)

    if isinstance(report, Report):
        print(f"\n📄 {report.title}")
        print(f"\nExecutive Summary:\n{report.executive_summary}")
        print("\nSections:")
        for section in report.sections:
            print(f"  • {section['title']}: {len(section['content'])} items")
        print("\nConclusions:")
        for conclusion in report.conclusions:
            print(f"  • {conclusion}")

    # Example 2: With custom routing (override automatic routing)
    print("\n\n2. Pipeline with custom routing:")
    print("-" * 40)

    # Create workflow with custom routing rules
    custom_workflow = (
        Workflow("custom_pipeline")
        .add_agent(Researcher, instance_id="researcher")
        .add_agent(
            Analyst, instance_id="analyst", error_handling="retry", max_retries=5
        )
        .add_agent(Reporter, instance_id="reporter")
        # Add custom route: Skip reporter if confidence is low
        .add_route(
            when=lambda result: (
                isinstance(result, Analysis) and result.confidence_score < 0.5
            ),
            from_agent="analyst",
            to_agent="researcher",  # Go back to researcher for more data
            priority=10,
        )
    )

    request2 = ResearchRequest(
        topic="Quantum Computing Applications", depth="deep", max_sources=10
    )

    print("Running custom workflow...")
    report2 = await custom_workflow.run(request2)

    if isinstance(report2, Report):
        print(f"✅ Custom workflow completed: {report2.title}")

    # Example 3: With intervention capability
    print("\n\n3. Pipeline with intervention enabled:")
    print("-" * 40)

    intervention_workflow = (
        Workflow("intervention_pipeline")
        .add_agents(Researcher, Analyst, Reporter)
        .with_intervention(True)  # Allow external agents to intervene
        .with_observability(True)
    )

    request3 = ResearchRequest(topic="Climate Change Solutions", depth="deep")

    print("Running with intervention enabled...")
    report3 = await intervention_workflow.run(request3)

    if isinstance(report3, Report):
        print("✅ Intervention-enabled workflow completed")
        print(f"   Generated at: {report3.generated_at}")

    print("\n" + "=" * 60)
    print("Multi-agent pipeline examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"\nError running example: {e}")
        import traceback

        traceback.print_exc()
