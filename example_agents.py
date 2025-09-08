"""Example agents demonstrating the framework capabilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from weaver_ai.agents import BaseAgent, agent
from weaver_ai.agents.base import Result
from weaver_ai.events import Event
from weaver_ai.memory import MemoryStrategy


# Data models for agent communication
class SalesData(BaseModel):
    """Sales data for analysis."""
    
    period: str
    revenue: float
    units_sold: int
    region: str
    products: list[str]


class AnalysisResult(BaseModel):
    """Result from data analysis."""
    
    summary: str
    insights: list[str]
    metrics: dict[str, float]
    recommendations: list[str]


class ValidationResult(BaseModel):
    """Validation result."""
    
    valid: bool
    errors: list[str]
    warnings: list[str]


class Report(BaseModel):
    """Generated report."""
    
    title: str
    content: str
    sections: list[dict[str, str]]
    generated_at: datetime


# Example 1: Data Analyst Agent
@agent(
    agent_type="analyst",
    capabilities=["analyze:sales", "analyze:data", "generate:insights"],
    memory_strategy="analyst"
)
class DataAnalystAgent:
    """Agent that analyzes data and generates insights."""
    
    async def process(self, event: Event) -> Result:
        """Analyze data and generate insights."""
        # Remember the analysis request
        await self.memory.remember(
            key=f"request_{event.metadata.event_id}",
            value=event.data.dict() if hasattr(event.data, "dict") else event.data,
            memory_type="short_term"
        )
        
        # Check if we've seen similar data before
        similar = await self.memory.recall(
            query="sales analysis",
            memory_types=["long_term", "semantic"],
            limit=5
        )
        
        # Simulate analysis (in real impl, would use model_router)
        if isinstance(event.data, SalesData):
            sales_data = event.data
        else:
            # Try to parse as SalesData
            sales_data = SalesData(
                period="Q4",
                revenue=1000000,
                units_sold=5000,
                region="North America",
                products=["Product A", "Product B"]
            )
        
        # Generate analysis
        analysis = AnalysisResult(
            summary=f"Sales analysis for {sales_data.period} in {sales_data.region}",
            insights=[
                f"Revenue: ${sales_data.revenue:,.2f}",
                f"Units sold: {sales_data.units_sold:,}",
                f"Average price: ${sales_data.revenue / sales_data.units_sold:.2f}",
                f"Top products: {', '.join(sales_data.products[:2])}"
            ],
            metrics={
                "revenue": sales_data.revenue,
                "units": float(sales_data.units_sold),
                "avg_price": sales_data.revenue / sales_data.units_sold,
            },
            recommendations=[
                "Focus on high-margin products",
                "Expand to new regions",
                "Optimize pricing strategy"
            ]
        )
        
        # Store analysis in long-term memory
        await self.memory.remember(
            key=f"analysis_{sales_data.period}_{sales_data.region}",
            value=analysis.dict(),
            memory_type="long_term",
            importance=0.8
        )
        
        # Store in semantic memory for pattern matching
        await self.memory.remember(
            key=f"pattern_sales_{sales_data.region}",
            value={
                "period": sales_data.period,
                "metrics": analysis.metrics
            },
            memory_type="semantic",
            importance=0.9
        )
        
        return Result(
            success=True,
            data=analysis,
            next_capabilities=["validate:analysis", "generate:report"],
            workflow_id=event.metadata.get("workflow_id")
        )


# Example 2: Validator Agent
@agent(
    agent_type="validator",
    capabilities=["validate:analysis", "validate:data", "check:quality"],
    memory_strategy="validator"
)
class ValidatorAgent:
    """Agent that validates data and analysis results."""
    
    async def process(self, event: Event) -> Result:
        """Validate analysis results."""
        errors = []
        warnings = []
        
        # Check previous validations for patterns
        similar_validations = await self.memory.recall(
            query="validation",
            memory_types=["short_term", "semantic"],
            limit=10
        )
        
        # Perform validation
        if isinstance(event.data, AnalysisResult):
            analysis = event.data
            
            # Validate metrics
            if not analysis.metrics:
                errors.append("No metrics provided")
            
            # Check for suspicious values
            for key, value in analysis.metrics.items():
                if value < 0:
                    errors.append(f"Negative value for {key}: {value}")
                elif value > 1e9:
                    warnings.append(f"Unusually high value for {key}: {value}")
            
            # Validate insights
            if not analysis.insights:
                warnings.append("No insights generated")
            
            # Store validation result
            validation = ValidationResult(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )
            
            # Remember this validation
            await self.memory.remember(
                key=f"validation_{event.metadata.event_id}",
                value=validation.dict(),
                memory_type="short_term"
            )
            
            # If valid, proceed to report generation
            next_caps = ["generate:report"] if validation.valid else ["analyze:data"]
            
            return Result(
                success=True,
                data=validation,
                next_capabilities=next_caps,
                workflow_id=event.metadata.get("workflow_id")
            )
        
        return Result(
            success=False,
            data=None,
            error="Invalid data type for validation"
        )


# Example 3: Report Generator Agent
@agent(
    agent_type="reporter",
    capabilities=["generate:report", "format:document", "create:summary"],
    memory_strategy="minimal"
)
class ReportGeneratorAgent:
    """Agent that generates formatted reports."""
    
    async def process(self, event: Event) -> Result:
        """Generate report from validated analysis."""
        # Check if we have a template in memory
        templates = await self.memory.recall(
            query="report_template",
            memory_types=["long_term"],
            limit=1
        )
        
        # Generate report
        if isinstance(event.data, (AnalysisResult, ValidationResult)):
            if isinstance(event.data, ValidationResult):
                # Generate validation report
                report = Report(
                    title="Validation Report",
                    content=f"Validation {'passed' if event.data.valid else 'failed'}",
                    sections=[
                        {"errors": "\n".join(event.data.errors)},
                        {"warnings": "\n".join(event.data.warnings)}
                    ],
                    generated_at=datetime.now(timezone.utc)
                )
            else:
                # Generate analysis report
                analysis = event.data
                report = Report(
                    title="Sales Analysis Report",
                    content=analysis.summary,
                    sections=[
                        {"insights": "\n".join(analysis.insights)},
                        {"metrics": json.dumps(analysis.metrics, indent=2)},
                        {"recommendations": "\n".join(analysis.recommendations)}
                    ],
                    generated_at=datetime.now(timezone.utc)
                )
            
            # Store generated report
            await self.memory.remember(
                key=f"report_{report.generated_at.isoformat()}",
                value=report.dict(),
                memory_type="short_term"
            )
            
            return Result(
                success=True,
                data=report,
                next_capabilities=[],  # End of workflow
                workflow_id=event.metadata.get("workflow_id")
            )
        
        return Result(
            success=False,
            data=None,
            error="Invalid data for report generation"
        )


# Example 4: Workflow Coordinator Agent
@agent(
    agent_type="coordinator",
    capabilities=["coordinate:workflow", "track:progress", "manage:agents"],
    memory_strategy="coordinator"
)
class WorkflowCoordinatorAgent:
    """Agent that coordinates multi-agent workflows."""
    
    async def process(self, event: Event) -> Result:
        """Coordinate workflow execution."""
        workflow_id = event.metadata.get("workflow_id") or event.metadata.event_id
        
        # Track workflow in episodic memory
        await self.memory.remember(
            key=f"workflow_{workflow_id}",
            value={
                "started_at": datetime.now(timezone.utc).isoformat(),
                "initial_event": event.event_type,
                "status": "running"
            },
            memory_type="episodic",
            importance=0.9
        )
        
        # Determine workflow steps based on event type
        if "sales" in event.event_type.lower():
            # Sales analysis workflow
            steps = [
                "analyze:sales",
                "validate:analysis",
                "generate:report"
            ]
        else:
            # Generic data workflow
            steps = [
                "analyze:data",
                "validate:data",
                "generate:summary"
            ]
        
        # Store workflow plan
        await self.memory.remember(
            key=f"plan_{workflow_id}",
            value={
                "steps": steps,
                "current_step": 0,
                "total_steps": len(steps)
            },
            memory_type="short_term"
        )
        
        # Start first step
        return Result(
            success=True,
            data=event.data,
            next_capabilities=[steps[0]],
            workflow_id=workflow_id
        )


# Example 5: Simple Echo Agent (for testing)
class EchoAgent(BaseAgent):
    """Simple agent that echoes input - for testing."""
    
    agent_type: str = "echo"
    capabilities: list[str] = ["echo:any", "test:connectivity"]
    
    async def process(self, event: Event) -> Result:
        """Echo the input event."""
        # Simple echo with timestamp
        echo_data = {
            "original": event.data.dict() if hasattr(event.data, "dict") else str(event.data),
            "echoed_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id
        }
        
        return Result(
            success=True,
            data=echo_data,
            next_capabilities=[],
            workflow_id=event.metadata.get("workflow_id")
        )