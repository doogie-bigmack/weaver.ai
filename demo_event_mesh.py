#!/usr/bin/env python3
"""
Live demonstration of the Event Mesh system for multi-agent workflows.

This demonstrates:
1. Publishing typed events
2. Multiple agents subscribing to events
3. Automatic workflow formation
4. Access control and security
"""

import asyncio

from pydantic import BaseModel
from weaver_ai.events import EventMesh, EventMetadata


# Define event types for our workflow
class CustomerOrder(BaseModel):
    """Initial customer order event."""
    order_id: str
    customer_name: str
    items: list[str]
    total: float


class OrderValidated(BaseModel):
    """Order validation result."""
    order_id: str
    is_valid: bool
    validation_notes: str


class PaymentProcessed(BaseModel):
    """Payment processing result."""
    order_id: str
    payment_successful: bool
    transaction_id: str


class OrderFulfilled(BaseModel):
    """Order fulfillment notification."""
    order_id: str
    tracking_number: str
    estimated_delivery: str


async def order_validator(mesh: EventMesh):
    """Agent that validates orders."""
    print("🤖 Order Validator Agent started")
    
    async for event in mesh.subscribe(
        [CustomerOrder],
        agent_id="validator",
        agent_roles=["validator"]
    ):
        order: CustomerOrder = event.data
        print(f"  ✓ Validating order {order.order_id}")
        
        # Validate the order
        is_valid = order.total > 0 and len(order.items) > 0
        
        # Publish validation result
        await mesh.publish(
            OrderValidated,
            OrderValidated(
                order_id=order.order_id,
                is_valid=is_valid,
                validation_notes="Order validated successfully" if is_valid else "Invalid order"
            ),
            metadata=EventMetadata(
                source_agent="validator",
                parent_event_id=event.metadata.event_id
            )
        )
        print(f"  ✓ Order {order.order_id} validation complete")
        break  # Process one order for demo


async def payment_processor(mesh: EventMesh):
    """Agent that processes payments."""
    print("🤖 Payment Processor Agent started")
    
    async for event in mesh.subscribe(
        [OrderValidated],
        agent_id="payment",
        agent_roles=["payment"]
    ):
        validation: OrderValidated = event.data
        
        if validation.is_valid:
            print(f"  💳 Processing payment for order {validation.order_id}")
            
            # Process payment
            await asyncio.sleep(0.5)  # Simulate payment processing
            
            # Publish payment result
            await mesh.publish(
                PaymentProcessed,
                PaymentProcessed(
                    order_id=validation.order_id,
                    payment_successful=True,
                    transaction_id=f"TXN-{validation.order_id}"
                ),
                metadata=EventMetadata(
                    source_agent="payment",
                    parent_event_id=event.metadata.event_id
                )
            )
            print(f"  ✓ Payment processed for order {validation.order_id}")
        else:
            print(f"  ❌ Skipping payment for invalid order {validation.order_id}")
        break


async def fulfillment_agent(mesh: EventMesh):
    """Agent that handles order fulfillment."""
    print("🤖 Fulfillment Agent started")
    
    async for event in mesh.subscribe(
        [PaymentProcessed],
        agent_id="fulfillment",
        agent_roles=["fulfillment"]
    ):
        payment: PaymentProcessed = event.data
        
        if payment.payment_successful:
            print(f"  📦 Fulfilling order {payment.order_id}")
            
            # Create fulfillment
            await mesh.publish(
                OrderFulfilled,
                OrderFulfilled(
                    order_id=payment.order_id,
                    tracking_number=f"TRACK-{payment.order_id}",
                    estimated_delivery="2-3 business days"
                ),
                metadata=EventMetadata(
                    source_agent="fulfillment",
                    parent_event_id=event.metadata.event_id
                )
            )
            print(f"  ✓ Order {payment.order_id} fulfilled")
        break


async def notification_agent(mesh: EventMesh):
    """Agent that sends notifications."""
    print("🤖 Notification Agent started")
    
    async for event in mesh.subscribe(
        [OrderFulfilled],
        agent_id="notifier",
        agent_roles=["notifier"]
    ):
        fulfillment: OrderFulfilled = event.data
        print(f"  📧 Sending notification for order {fulfillment.order_id}")
        print(f"     Tracking: {fulfillment.tracking_number}")
        print(f"     Delivery: {fulfillment.estimated_delivery}")
        break


async def main():
    """Run the demonstration."""
    print("=" * 60)
    print("Event Mesh Multi-Agent Workflow Demonstration")
    print("=" * 60)
    
    # Create event mesh
    mesh = EventMesh()
    
    # Start all agents as background tasks
    print("\n🚀 Starting agents...")
    validator_task = asyncio.create_task(order_validator(mesh))
    payment_task = asyncio.create_task(payment_processor(mesh))
    fulfillment_task = asyncio.create_task(fulfillment_agent(mesh))
    notification_task = asyncio.create_task(notification_agent(mesh))
    
    # Give agents time to start
    await asyncio.sleep(0.5)
    
    # Trigger workflow with a customer order
    print("\n📝 Customer places order...")
    order = CustomerOrder(
        order_id="ORD-001",
        customer_name="Alice Smith",
        items=["Widget A", "Widget B"],
        total=99.99
    )
    
    event_id = await mesh.publish(
        CustomerOrder,
        order,
        metadata=EventMetadata(source_agent="customer_portal")
    )
    
    print(f"   Order published with ID: {event_id}")
    
    # Wait for workflow to complete
    print("\n⏳ Processing workflow...")
    
    # Wait for all agents to complete their tasks
    await asyncio.gather(
        validator_task,
        payment_task, 
        fulfillment_task,
        notification_task,
        return_exceptions=True
    )
    
    # Show statistics
    stats = mesh.get_stats()
    print("\n📊 Event Mesh Statistics:")
    print(f"   Total events processed: {stats['total_events']}")
    print(f"   Event types registered: {stats['registered_types']}")
    
    # Show event history
    print("\n📜 Event History:")
    for i, event in enumerate(mesh.event_history, 1):
        print(f"   {i}. {event.data.__class__.__name__} - {event.metadata.source_agent}")
    
    print("\n✅ Workflow demonstration complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())