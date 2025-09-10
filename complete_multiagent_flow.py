#!/usr/bin/env python3
"""
Complete Multi-Agent Workflow Example for Weaver AI Framework

This example demonstrates a realistic customer support ticket processing system
with multiple specialized agents working together to handle, classify, and resolve
customer issues.

Scenario: Customer Support Ticket Processing Pipeline
- Customer submits a support ticket
- Multiple agents collaborate to process, classify, and resolve the ticket
- Each agent has specialized capabilities and security permissions
- Full A2A protocol compliance with telemetry and verification

Agents in this workflow:
1. IntakeAgent: Initial ticket processing and data extraction
2. ClassificationAgent: Categorizes tickets and determines priority
3. TechnicalAgent: Handles technical issues and troubleshooting
4. EscalationAgent: Manages complex cases requiring human intervention
5. ResponseAgent: Generates customer-facing responses

Usage:
    python complete_multiagent_flow.py

Requirements:
    pip install fastapi uvicorn pydantic pyyaml structlog pytest
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

# Mock implementations of Weaver AI components for this standalone example
# In production, these would be imported from the actual weaver_ai package

# ============================================================================
# MOCK WEAVER AI FRAMEWORK COMPONENTS
# ============================================================================


class TicketPriority(str, Enum):
    """Ticket priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    """Ticket categories"""

    TECHNICAL = "technical"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    ACCOUNT = "account"
    OTHER = "other"


class TicketStatus(str, Enum):
    """Ticket processing status"""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class A2AEnvelope:
    """A2A protocol message envelope"""

    id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict[str, Any]
    timestamp: datetime
    nonce: str = None
    signature: str = None

    def __post_init__(self):
        if self.nonce is None:
            self.nonce = str(uuid.uuid4())
        if self.signature is None:
            # In production, this would be a proper JWT signature
            self.signature = f"mock_signature_{self.nonce[:8]}"


class MockModelRouter:
    """Mock model router for demonstration"""

    async def generate(self, prompt: str, model: str = "gpt-4") -> str:
        """Mock text generation - in production this would call real models"""
        # Simple mock responses based on prompt content
        prompt_lower = prompt.lower()

        if "classify" in prompt_lower and "ticket" in prompt_lower:
            if "password" in prompt_lower or "login" in prompt_lower:
                return json.dumps(
                    {
                        "category": "account",
                        "priority": "medium",
                        "confidence": 0.85,
                        "reasoning": "Authentication-related issue detected",
                    }
                )
            elif "crash" in prompt_lower or "error" in prompt_lower:
                return json.dumps(
                    {
                        "category": "bug_report",
                        "priority": "high",
                        "confidence": 0.92,
                        "reasoning": "Application crash indicates critical bug",
                    }
                )
            else:
                return json.dumps(
                    {
                        "category": "technical",
                        "priority": "medium",
                        "confidence": 0.75,
                        "reasoning": "General technical inquiry",
                    }
                )

        elif "troubleshoot" in prompt_lower:
            return json.dumps(
                {
                    "solution": (
                        "Please try clearing your browser cache and cookies, "
                        "then restart the application."
                    ),
                    "additional_steps": [
                        "Check browser version",
                        "Disable extensions",
                        "Try incognito mode",
                    ],
                    "confidence": 0.88,
                }
            )

        elif "response" in prompt_lower and "customer" in prompt_lower:
            return """Dear Customer,

Thank you for contacting our support team. We have reviewed your issue and have
identified a solution.

Please try the following steps:
1. Clear your browser cache and cookies
2. Restart your browser
3. Try accessing the application again

If the issue persists, please don't hesitate to reach out to us again.

Best regards,
Customer Support Team"""

        else:
            return f"Mock response for: {prompt[:50]}..."


class MockTelemetry:
    """Mock telemetry system for demonstration"""

    def __init__(self):
        self.events = []

    def record_event(self, event_type: str, agent_id: str, data: dict[str, Any]):
        """Record a telemetry event"""
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "agent_id": agent_id,
            "data": data,
        }
        self.events.append(event)
        # Log event (logger would be configured in production)
        print(f"Telemetry: {event_type} - {agent_id}")


class MockVerifier:
    """Mock verification system for output validation"""

    def verify_output(self, output: str, agent_id: str) -> tuple[bool, str]:
        """Verify agent output meets safety and quality standards"""
        # Basic verification - in production this would be much more sophisticated
        if len(output.strip()) == 0:
            return False, "Empty output"

        # Check for potentially harmful content (very basic example)
        harmful_keywords = ["hack", "exploit", "bypass", "credentials"]
        if any(keyword in output.lower() for keyword in harmful_keywords):
            return False, "Potentially harmful content detected"

        return True, "Output verified"


class MockSecurityManager:
    """Mock security manager for authentication and authorization"""

    def __init__(self):
        self.agent_permissions = {
            "intake_agent": ["read_tickets", "create_tickets", "update_tickets"],
            "classification_agent": [
                "read_tickets",
                "classify_tickets",
                "update_tickets",
            ],
            "technical_agent": ["read_tickets", "generate_solutions", "update_tickets"],
            "escalation_agent": ["read_tickets", "escalate_tickets", "assign_human"],
            "response_agent": ["read_tickets", "generate_responses", "send_responses"],
        }

    def check_permission(self, agent_id: str, permission: str) -> bool:
        """Check if agent has required permission"""
        return permission in self.agent_permissions.get(agent_id, [])

    def authenticate_agent(self, agent_id: str, token: str) -> bool:
        """Mock authentication - always returns True for demo"""
        return True


# ============================================================================
# TICKET DATA MODELS
# ============================================================================


@dataclass
class SupportTicket:
    """Support ticket data model"""

    id: str
    customer_id: str
    subject: str
    description: str
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    status: TicketStatus = TicketStatus.NEW
    created_at: datetime = None
    updated_at: datetime = None
    assigned_agent: str | None = None
    resolution: str | None = None
    customer_response: str | None = None
    internal_notes: list[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.internal_notes is None:
            self.internal_notes = []

    def to_dict(self) -> dict[str, Any]:
        """Convert ticket to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data


# ============================================================================
# BASE AGENT CLASS
# ============================================================================


class BaseAgent:
    """Base class for all agents in the workflow"""

    def __init__(
        self,
        agent_id: str,
        model_router: MockModelRouter,
        telemetry: MockTelemetry,
        verifier: MockVerifier,
        security_manager: MockSecurityManager,
    ):
        self.agent_id = agent_id
        self.model_router = model_router
        self.telemetry = telemetry
        self.verifier = verifier
        self.security_manager = security_manager
        self.logger = structlog.get_logger().bind(agent_id=agent_id)

    def check_permission(self, permission: str) -> bool:
        """Check if this agent has the required permission"""
        if not self.security_manager.check_permission(self.agent_id, permission):
            self.logger.error("Permission denied", permission=permission)
            return False
        return True

    async def send_message(
        self, to_agent: str, message_type: str, payload: dict[str, Any]
    ) -> A2AEnvelope:
        """Send A2A message to another agent"""
        envelope = A2AEnvelope(
            id=str(uuid.uuid4()),
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.now(UTC),
        )

        self.telemetry.record_event(
            event_type="message_sent",
            agent_id=self.agent_id,
            data={
                "to_agent": to_agent,
                "message_type": message_type,
                "message_id": envelope.id,
            },
        )

        return envelope

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming A2A message - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement process_message")


# ============================================================================
# SPECIALIZED AGENT IMPLEMENTATIONS
# ============================================================================


class IntakeAgent(BaseAgent):
    """
    Handles initial ticket intake and data extraction.

    Responsibilities:
    - Validate incoming ticket data
    - Extract structured information from free-form text
    - Perform initial data cleaning and normalization
    - Route tickets to classification agent
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def process_ticket(self, ticket: SupportTicket) -> SupportTicket:
        """Process a new support ticket"""
        if not self.check_permission("read_tickets"):
            raise PermissionError("Insufficient permissions")

        self.logger.info("Processing new ticket", ticket_id=ticket.id)

        # Extract key information from the ticket description
        extraction_prompt = f"""
        Extract key information from this support ticket:

        Subject: {ticket.subject}
        Description: {ticket.description}

        Please identify:
        1. Key technical terms or error messages
        2. Affected systems or features
        3. Customer's emotional state (frustrated, urgent, etc.)
        4. Any specific requests or questions

        Return as JSON with extracted_info field.
        """

        try:
            extracted_info = await self.model_router.generate(extraction_prompt)

            # Verify the extracted information
            is_valid, verification_msg = self.verifier.verify_output(
                extracted_info, self.agent_id
            )

            if not is_valid:
                self.logger.warning(
                    "Output verification failed", reason=verification_msg
                )

            # Add extraction results to internal notes
            ticket.internal_notes.append(f"Intake extraction: {extracted_info}")
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = datetime.now(UTC)

            self.telemetry.record_event(
                event_type="ticket_processed",
                agent_id=self.agent_id,
                data={"ticket_id": ticket.id, "extraction_success": is_valid},
            )

            return ticket

        except Exception as e:
            self.logger.error("Ticket processing failed", error=str(e))
            raise

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming messages"""
        if envelope.message_type == "new_ticket":
            ticket_data = envelope.payload["ticket"]
            ticket = SupportTicket(**ticket_data)

            processed_ticket = await self.process_ticket(ticket)

            # Send to classification agent
            return await self.send_message(
                to_agent="classification_agent",
                message_type="classify_ticket",
                payload={"ticket": processed_ticket.to_dict()},
            )

        return None


class ClassificationAgent(BaseAgent):
    """
    Classifies tickets by category and priority.

    Responsibilities:
    - Analyze ticket content to determine category
    - Assess priority based on business rules
    - Route tickets to appropriate handling agents
    """

    async def classify_ticket(self, ticket: SupportTicket) -> SupportTicket:
        """Classify ticket category and priority"""
        if not self.check_permission("classify_tickets"):
            raise PermissionError("Insufficient permissions")

        self.logger.info("Classifying ticket", ticket_id=ticket.id)

        classification_prompt = f"""
        Classify this support ticket:

        Subject: {ticket.subject}
        Description: {ticket.description}

        Determine:
        1. Category: {[cat.value for cat in TicketCategory]}
        2. Priority: {[pri.value for pri in TicketPriority]}
        3. Confidence score (0-1)
        4. Brief reasoning

        Return as JSON with category, priority, confidence, and reasoning fields.
        """

        try:
            classification_result = await self.model_router.generate(
                classification_prompt
            )

            # Parse classification result
            result_data = json.loads(classification_result)

            ticket.category = TicketCategory(result_data.get("category", "other"))
            ticket.priority = TicketPriority(result_data.get("priority", "medium"))
            ticket.internal_notes.append(
                f"Classification: {result_data.get('reasoning', 'No reasoning provided')}"
            )
            ticket.updated_at = datetime.now(UTC)

            self.telemetry.record_event(
                event_type="ticket_classified",
                agent_id=self.agent_id,
                data={
                    "ticket_id": ticket.id,
                    "category": ticket.category.value,
                    "priority": ticket.priority.value,
                    "confidence": result_data.get("confidence", 0.0),
                },
            )

            return ticket

        except Exception as e:
            self.logger.error("Classification failed", error=str(e))
            # Default classification
            ticket.category = TicketCategory.OTHER
            ticket.priority = TicketPriority.MEDIUM
            return ticket

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming messages"""
        if envelope.message_type == "classify_ticket":
            ticket_data = envelope.payload["ticket"]
            ticket = SupportTicket(**ticket_data)

            classified_ticket = await self.classify_ticket(ticket)

            # Route based on category and priority
            if classified_ticket.priority == TicketPriority.CRITICAL:
                next_agent = "escalation_agent"
                message_type = "escalate_ticket"
            elif classified_ticket.category in [
                TicketCategory.TECHNICAL,
                TicketCategory.BUG_REPORT,
            ]:
                next_agent = "technical_agent"
                message_type = "solve_technical"
            else:
                next_agent = "response_agent"
                message_type = "generate_response"

            return await self.send_message(
                to_agent=next_agent,
                message_type=message_type,
                payload={"ticket": classified_ticket.to_dict()},
            )

        return None


class TechnicalAgent(BaseAgent):
    """
    Handles technical issues and troubleshooting.

    Responsibilities:
    - Analyze technical problems
    - Generate step-by-step solutions
    - Provide troubleshooting guidance
    - Escalate complex technical issues
    """

    async def solve_technical_issue(self, ticket: SupportTicket) -> SupportTicket:
        """Generate technical solution for the ticket"""
        if not self.check_permission("generate_solutions"):
            raise PermissionError("Insufficient permissions")

        self.logger.info("Solving technical issue", ticket_id=ticket.id)

        solution_prompt = f"""
        Provide a technical solution for this issue:

        Category: {ticket.category.value if ticket.category else 'unknown'}
        Subject: {ticket.subject}
        Description: {ticket.description}

        Generate:
        1. Step-by-step troubleshooting guide
        2. Alternative solutions if primary fails
        3. Prevention tips
        4. Confidence level in the solution

        Return as JSON with solution, additional_steps, and confidence fields.
        """

        try:
            solution_result = await self.model_router.generate(solution_prompt)
            solution_data = json.loads(solution_result)

            ticket.resolution = solution_data.get("solution", "No solution generated")
            ticket.internal_notes.append(
                f"Technical solution generated with "
                f"{solution_data.get('confidence', 0.0)} confidence"
            )
            ticket.assigned_agent = self.agent_id
            ticket.updated_at = datetime.now(UTC)

            # Check if solution confidence is low - might need escalation
            if solution_data.get("confidence", 1.0) < 0.7:
                ticket.status = TicketStatus.ESCALATED
                self.logger.warning(
                    "Low confidence solution - marking for escalation",
                    ticket_id=ticket.id,
                )

            self.telemetry.record_event(
                event_type="technical_solution_generated",
                agent_id=self.agent_id,
                data={
                    "ticket_id": ticket.id,
                    "confidence": solution_data.get("confidence", 0.0),
                    "escalated": ticket.status == TicketStatus.ESCALATED,
                },
            )

            return ticket

        except Exception as e:
            self.logger.error("Technical solution generation failed", error=str(e))
            ticket.status = TicketStatus.ESCALATED
            return ticket

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming messages"""
        if envelope.message_type == "solve_technical":
            ticket_data = envelope.payload["ticket"]
            ticket = SupportTicket(**ticket_data)

            solved_ticket = await self.solve_technical_issue(ticket)

            # Route based on status
            if solved_ticket.status == TicketStatus.ESCALATED:
                return await self.send_message(
                    to_agent="escalation_agent",
                    message_type="escalate_ticket",
                    payload={"ticket": solved_ticket.to_dict()},
                )
            else:
                return await self.send_message(
                    to_agent="response_agent",
                    message_type="generate_response",
                    payload={"ticket": solved_ticket.to_dict()},
                )

        return None


class EscalationAgent(BaseAgent):
    """
    Manages complex cases requiring human intervention.

    Responsibilities:
    - Identify cases requiring human review
    - Prepare comprehensive briefings for human agents
    - Track escalation metrics
    - Handle high-priority routing
    """

    async def escalate_ticket(self, ticket: SupportTicket) -> SupportTicket:
        """Handle ticket escalation to human agents"""
        if not self.check_permission("escalate_tickets"):
            raise PermissionError("Insufficient permissions")

        self.logger.info("Escalating ticket", ticket_id=ticket.id)

        # Prepare escalation summary
        escalation_prompt = f"""
        Prepare an escalation summary for human agents:

        Ticket ID: {ticket.id}
        Category: {ticket.category.value if ticket.category else 'unknown'}
        Priority: {ticket.priority.value if ticket.priority else 'medium'}
        Subject: {ticket.subject}
        Description: {ticket.description}

        Current Resolution: {ticket.resolution or 'No resolution attempted'}
        Processing Notes: {'; '.join(ticket.internal_notes)}

        Provide:
        1. Concise problem summary
        2. What has been attempted
        3. Why escalation is needed
        4. Recommended next steps
        5. Urgency assessment
        """

        try:
            escalation_summary = await self.model_router.generate(escalation_prompt)

            ticket.status = TicketStatus.ESCALATED
            ticket.assigned_agent = "human_required"
            ticket.internal_notes.append(f"ESCALATED: {escalation_summary}")
            ticket.updated_at = datetime.now(UTC)

            self.telemetry.record_event(
                event_type="ticket_escalated",
                agent_id=self.agent_id,
                data={
                    "ticket_id": ticket.id,
                    "escalation_reason": "Complex case requiring human intervention",
                    "priority": ticket.priority.value if ticket.priority else "medium",
                },
            )

            return ticket

        except Exception as e:
            self.logger.error("Escalation processing failed", error=str(e))
            ticket.internal_notes.append(f"Escalation error: {str(e)}")
            return ticket

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming messages"""
        if envelope.message_type == "escalate_ticket":
            ticket_data = envelope.payload["ticket"]
            ticket = SupportTicket(**ticket_data)

            escalated_ticket = await self.escalate_ticket(ticket)

            # For demo purposes, we'll still generate a response
            # In production, this would be handled by human agents
            return await self.send_message(
                to_agent="response_agent",
                message_type="generate_escalated_response",
                payload={"ticket": escalated_ticket.to_dict()},
            )

        return None


class ResponseAgent(BaseAgent):
    """
    Generates customer-facing responses.

    Responsibilities:
    - Create professional, helpful responses to customers
    - Ensure consistent tone and branding
    - Handle different response types (solutions, escalations, etc.)
    - Track customer satisfaction indicators
    """

    async def generate_customer_response(
        self, ticket: SupportTicket, response_type: str = "standard"
    ) -> SupportTicket:
        """Generate customer-facing response"""
        if not self.check_permission("generate_responses"):
            raise PermissionError("Insufficient permissions")

        self.logger.info("Generating customer response", ticket_id=ticket.id)

        if response_type == "escalated":
            response_prompt = f"""
            Generate a professional customer response for an escalated ticket:

            Subject: {ticket.subject}
            Category: {ticket.category.value if ticket.category else 'General'}

            The ticket has been escalated to our specialized team.
            Acknowledge the complexity and set appropriate expectations.
            Be empathetic and professional.
            """
        else:
            response_prompt = f"""
            Generate a helpful customer response:

            Subject: {ticket.subject}
            Category: {ticket.category.value if ticket.category else 'General'}
            Resolution: {ticket.resolution or 'General assistance provided'}

            Provide clear, actionable guidance while maintaining a professional,
            friendly tone. If technical steps are involved, make them easy to follow.
            """

        try:
            customer_response = await self.model_router.generate(response_prompt)

            # Verify response is appropriate
            is_valid, verification_msg = self.verifier.verify_output(
                customer_response, self.agent_id
            )

            if not is_valid:
                self.logger.warning(
                    "Response verification failed", reason=verification_msg
                )
                customer_response = (
                    "Thank you for contacting support. We are reviewing "
                    "your request and will respond shortly."
                )

            ticket.customer_response = customer_response
            ticket.status = TicketStatus.RESOLVED
            ticket.updated_at = datetime.now(UTC)

            self.telemetry.record_event(
                event_type="customer_response_generated",
                agent_id=self.agent_id,
                data={
                    "ticket_id": ticket.id,
                    "response_type": response_type,
                    "verified": is_valid,
                },
            )

            return ticket

        except Exception as e:
            self.logger.error("Response generation failed", error=str(e))
            ticket.customer_response = (
                "Thank you for contacting support. We encountered "
                "an issue processing your request and will follow up manually."
            )
            return ticket

    async def process_message(self, envelope: A2AEnvelope) -> A2AEnvelope | None:
        """Process incoming messages"""
        if envelope.message_type in [
            "generate_response",
            "generate_escalated_response",
        ]:
            ticket_data = envelope.payload["ticket"]
            ticket = SupportTicket(**ticket_data)

            response_type = (
                "escalated"
                if envelope.message_type == "generate_escalated_response"
                else "standard"
            )
            final_ticket = await self.generate_customer_response(ticket, response_type)

            # This would be the final step - no further routing needed
            self.logger.info(
                "Workflow completed",
                ticket_id=final_ticket.id,
                final_status=final_ticket.status.value,
            )

            return None  # End of workflow

        return None


# ============================================================================
# WORKFLOW ORCHESTRATOR
# ============================================================================


class WorkflowOrchestrator:
    """
    Orchestrates the multi-agent workflow for ticket processing.

    This class manages the overall workflow, coordinates between agents,
    and handles error conditions and monitoring.
    """

    def __init__(self):
        # Initialize shared components
        self.model_router = MockModelRouter()
        self.telemetry = MockTelemetry()
        self.verifier = MockVerifier()
        self.security_manager = MockSecurityManager()

        # Initialize agents
        self.agents = {
            "intake_agent": IntakeAgent(
                "intake_agent",
                self.model_router,
                self.telemetry,
                self.verifier,
                self.security_manager,
            ),
            "classification_agent": ClassificationAgent(
                "classification_agent",
                self.model_router,
                self.telemetry,
                self.verifier,
                self.security_manager,
            ),
            "technical_agent": TechnicalAgent(
                "technical_agent",
                self.model_router,
                self.telemetry,
                self.verifier,
                self.security_manager,
            ),
            "escalation_agent": EscalationAgent(
                "escalation_agent",
                self.model_router,
                self.telemetry,
                self.verifier,
                self.security_manager,
            ),
            "response_agent": ResponseAgent(
                "response_agent",
                self.model_router,
                self.telemetry,
                self.verifier,
                self.security_manager,
            ),
        }

        self.logger = structlog.get_logger().bind(component="orchestrator")
        self.processed_tickets = []

    async def process_ticket_workflow(self, ticket: SupportTicket) -> SupportTicket:
        """
        Process a support ticket through the complete multi-agent workflow.

        Args:
            ticket: The support ticket to process

        Returns:
            The processed ticket with resolution
        """
        self.logger.info("Starting ticket workflow", ticket_id=ticket.id)

        workflow_start = datetime.now(UTC)

        try:
            # Start workflow with intake agent
            current_envelope = A2AEnvelope(
                id=str(uuid.uuid4()),
                from_agent="system",
                to_agent="intake_agent",
                message_type="new_ticket",
                payload={"ticket": ticket.to_dict()},
                timestamp=workflow_start,
            )

            # Process through agent chain
            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while current_envelope and iteration < max_iterations:
                iteration += 1
                target_agent = current_envelope.to_agent

                if target_agent not in self.agents:
                    self.logger.error("Unknown target agent", agent=target_agent)
                    break

                self.logger.info(
                    "Processing message",
                    iteration=iteration,
                    from_agent=current_envelope.from_agent,
                    to_agent=target_agent,
                    message_type=current_envelope.message_type,
                )

                # Process message with target agent
                agent = self.agents[target_agent]
                next_envelope = await agent.process_message(current_envelope)

                # Update current ticket state from the message
                if current_envelope.payload.get("ticket"):
                    ticket = SupportTicket(**current_envelope.payload["ticket"])

                current_envelope = next_envelope

            if iteration >= max_iterations:
                self.logger.warning("Workflow hit max iterations", ticket_id=ticket.id)

            # Record workflow completion
            workflow_duration = (datetime.now(UTC) - workflow_start).total_seconds()

            self.telemetry.record_event(
                event_type="workflow_completed",
                agent_id="orchestrator",
                data={
                    "ticket_id": ticket.id,
                    "duration_seconds": workflow_duration,
                    "iterations": iteration,
                    "final_status": ticket.status.value,
                },
            )

            self.processed_tickets.append(ticket)
            return ticket

        except Exception as e:
            self.logger.error("Workflow failed", ticket_id=ticket.id, error=str(e))

            # Create fallback response
            ticket.status = TicketStatus.ESCALATED
            ticket.customer_response = (
                "We apologize, but we encountered an issue processing your request. "
                "A human agent will review this shortly."
            )
            ticket.internal_notes.append(f"Workflow error: {str(e)}")

            return ticket

    def get_workflow_stats(self) -> dict[str, Any]:
        """Get workflow processing statistics"""
        if not self.processed_tickets:
            return {"message": "No tickets processed yet"}

        total_tickets = len(self.processed_tickets)
        status_counts = {}
        category_counts = {}
        priority_counts = {}

        for ticket in self.processed_tickets:
            # Count by status
            status = ticket.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            # Count by category
            if ticket.category:
                category = ticket.category.value
                category_counts[category] = category_counts.get(category, 0) + 1

            # Count by priority
            if ticket.priority:
                priority = ticket.priority.value
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return {
            "total_tickets_processed": total_tickets,
            "status_distribution": status_counts,
            "category_distribution": category_counts,
            "priority_distribution": priority_counts,
            "telemetry_events": len(self.telemetry.events),
        }


# ============================================================================
# SAMPLE DATA AND TESTING
# ============================================================================


def create_sample_tickets() -> list[SupportTicket]:
    """Create sample tickets for testing the workflow"""

    sample_tickets = [
        SupportTicket(
            id="TICK-001",
            customer_id="CUST-12345",
            subject="Cannot login to my account",
            description=(
                "I've been trying to login for the past hour but keep getting "
                "'invalid credentials' error. I'm sure my password is correct. This is "
                "blocking me from accessing important files for my presentation tomorrow."
            ),
        ),
        SupportTicket(
            id="TICK-002",
            customer_id="CUST-67890",
            subject="Application crashes when uploading large files",
            description=(
                "Every time I try to upload a file larger than 10MB, the application "
                "crashes with error code 500. This happens consistently across different "
                "file types. I need to upload a 15MB video for my project."
            ),
        ),
        SupportTicket(
            id="TICK-003",
            customer_id="CUST-11111",
            subject="Feature request: Dark mode",
            description=(
                "I would love to have a dark mode option in the application. I work "
                "long hours and the bright interface strains my eyes. Many modern "
                "applications offer this feature."
            ),
        ),
        SupportTicket(
            id="TICK-004",
            customer_id="CUST-22222",
            subject="Billing discrepancy on latest invoice",
            description=(
                "My latest invoice shows charges for premium features I never activated. "
                "The amount is $50 more than expected. Please review my account and "
                "correct this billing error."
            ),
        ),
        SupportTicket(
            id="TICK-005",
            customer_id="CUST-33333",
            subject="Data export not working",
            description=(
                "When I try to export my data using the export feature, the download "
                "starts but fails at around 50%. I've tried multiple times and browsers. "
                "I need this data for compliance reporting that's due next week."
            ),
        ),
    ]

    return sample_tickets


# ============================================================================
# MAIN EXECUTION AND TESTING
# ============================================================================


async def run_workflow_demo():
    """
    Run a complete demonstration of the multi-agent workflow.

    This function:
    1. Creates sample tickets
    2. Processes them through the workflow
    3. Displays results and statistics
    4. Shows telemetry data
    """
    print("=" * 80)
    print("WEAVER AI MULTI-AGENT WORKFLOW DEMONSTRATION")
    print("=" * 80)
    print()

    # Initialize orchestrator
    orchestrator = WorkflowOrchestrator()

    # Create sample tickets
    sample_tickets = create_sample_tickets()

    print(f"Processing {len(sample_tickets)} sample support tickets...\n")

    # Process each ticket
    for i, ticket in enumerate(sample_tickets, 1):
        print(f"Processing Ticket {i}/{len(sample_tickets)}: {ticket.id}")
        print(f"Subject: {ticket.subject}")
        print("-" * 60)

        try:
            processed_ticket = await orchestrator.process_ticket_workflow(ticket)

            print(f"✅ Status: {processed_ticket.status.value.upper()}")
            if processed_ticket.category:
                print(f"📂 Category: {processed_ticket.category.value}")
            if processed_ticket.priority:
                print(f"🔥 Priority: {processed_ticket.priority.value}")
            if processed_ticket.customer_response:
                print(f"📧 Response: {processed_ticket.customer_response[:100]}...")

            print()

        except Exception as e:
            print(f"❌ Error processing ticket: {str(e)}")
            print()

    # Display workflow statistics
    print("=" * 80)
    print("WORKFLOW STATISTICS")
    print("=" * 80)

    stats = orchestrator.get_workflow_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key.replace('_', ' ').title()}:")
            for sub_key, sub_value in value.items():
                print(f"  - {sub_key}: {sub_value}")
        else:
            print(f"{key.replace('_', ' ').title()}: {value}")

    print()

    # Display telemetry events
    print("=" * 80)
    print("TELEMETRY EVENTS (Last 10)")
    print("=" * 80)

    recent_events = orchestrator.telemetry.events[-10:]
    for event in recent_events:
        print(
            f"[{event['timestamp'][:19]}] {event['agent_id']} - {event['event_type']}"
        )
        if "ticket_id" in event["data"]:
            print(f"  Ticket: {event['data']['ticket_id']}")

    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


def run_unit_tests():
    """
    Basic unit tests for the workflow components.

    In production, you would use pytest for comprehensive testing.
    """
    print("\n" + "=" * 80)
    print("RUNNING UNIT TESTS")
    print("=" * 80)

    # Test ticket creation
    print("✅ Testing ticket creation...")
    ticket = SupportTicket(
        id="TEST-001",
        customer_id="TEST-CUST",
        subject="Test ticket",
        description="This is a test ticket",
    )
    assert ticket.status == TicketStatus.NEW
    assert ticket.created_at is not None

    # Test A2A envelope creation
    print("✅ Testing A2A envelope creation...")
    envelope = A2AEnvelope(
        id="test-id",
        from_agent="agent1",
        to_agent="agent2",
        message_type="test",
        payload={"data": "test"},
        timestamp=datetime.now(UTC),
    )
    assert envelope.nonce is not None
    assert envelope.signature is not None

    # Test security manager
    print("✅ Testing security manager...")
    security_manager = MockSecurityManager()
    assert security_manager.check_permission("intake_agent", "read_tickets")
    assert not security_manager.check_permission("intake_agent", "invalid_permission")

    # Test telemetry
    print("✅ Testing telemetry...")
    telemetry = MockTelemetry()
    telemetry.record_event("test_event", "test_agent", {"key": "value"})
    assert len(telemetry.events) == 1

    print("✅ All unit tests passed!")


async def main():
    """Main function to run the complete demonstration"""

    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set logging level
    logging.basicConfig(level=logging.INFO)

    # Run unit tests first
    run_unit_tests()

    # Run the full workflow demonstration
    await run_workflow_demo()

    print("\n🎉 Multi-agent workflow demonstration completed successfully!")
    print("\nKey Features Demonstrated:")
    print("- 🤖 Multi-agent coordination with specialized roles")
    print("- 📨 A2A protocol message passing")
    print("- 🔒 Security and permissions management")
    print("- 📊 Comprehensive telemetry and monitoring")
    print("- ✅ Output verification and validation")
    print("- 🔄 Error handling and graceful degradation")
    print("- 📈 Workflow statistics and analytics")

    print("\nTo run this example:")
    print(
        "1. Ensure you have the required dependencies: pip install pydantic structlog"
    )
    print("2. Run: python complete_multiagent_flow.py")
    print("3. Observe the multi-agent workflow processing sample tickets")


if __name__ == "__main__":
    asyncio.run(main())
