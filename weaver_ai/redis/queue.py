"""Redis-backed work queue for reliable task processing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import redis.asyncio as aioredis
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Task to be processed by an agent."""
    
    task_id: str = Field(default_factory=lambda: uuid4().hex)
    capability: str
    data: dict[str, Any]
    priority: int = 0
    workflow_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    max_attempts: int = 3


class WorkQueue:
    """Redis-backed work queue for reliable task processing.
    
    Uses Redis sorted sets for priority queuing and reliable task processing.
    """
    
    def __init__(self, redis: aioredis.Redis):
        """Initialize work queue.
        
        Args:
            redis: Redis connection
        """
        self.redis = redis
        
    async def push_task(
        self,
        task: Task,
        queue_name: str | None = None,
    ) -> str:
        """Push task to queue.
        
        Args:
            task: Task to push
            queue_name: Optional queue name (defaults to capability-based)
            
        Returns:
            Task ID
        """
        if not queue_name:
            # Route based on required capability
            queue_name = f"queue:{task.capability.replace(':', '_')}"
        
        # Use Redis sorted set for priority (lower score = higher priority)
        score = -task.priority if task.priority else datetime.now().timestamp()
        
        await self.redis.zadd(
            queue_name,
            {task.json(): score}
        )
        
        # Publish notification for waiting agents
        await self.redis.publish(
            f"notify:{queue_name}",
            json.dumps({
                "task_id": task.task_id,
                "queue": queue_name,
                "capability": task.capability,
            })
        )
        
        return task.task_id
    
    async def pop_task(
        self,
        queue_names: list[str],
        block: bool = True,
        timeout: int = 0,
    ) -> Task | None:
        """Pop highest priority task from queues.
        
        Args:
            queue_names: List of queue names to pop from
            block: Whether to block waiting for tasks
            timeout: Timeout in seconds (0 = infinite)
            
        Returns:
            Task if available, None otherwise
        """
        if block and timeout != 0:
            # Use blocking pop with timeout
            end_time = datetime.now().timestamp() + timeout
            
            while datetime.now().timestamp() < end_time:
                task = await self._try_pop(queue_names)
                if task:
                    return task
                    
                # Wait a bit before trying again
                await asyncio.sleep(0.1)
                
            return None
        elif block:
            # Block indefinitely
            while True:
                task = await self._try_pop(queue_names)
                if task:
                    return task
                    
                # Wait a bit before trying again
                import asyncio
                await asyncio.sleep(0.1)
        else:
            # Non-blocking pop
            return await self._try_pop(queue_names)
    
    async def _try_pop(self, queue_names: list[str]) -> Task | None:
        """Try to pop from queues.
        
        Args:
            queue_names: Queue names to try
            
        Returns:
            Task if found
        """
        for queue in queue_names:
            # Pop highest priority (lowest score)
            result = await self.redis.zpopmin(queue, count=1)
            if result:
                task_json, score = result[0]
                return Task.parse_raw(task_json)
        return None
    
    async def requeue_task(
        self,
        task: Task,
        queue_name: str | None = None,
        delay_seconds: int = 0,
    ):
        """Requeue a task (e.g., after failure).
        
        Args:
            task: Task to requeue
            queue_name: Optional queue name
            delay_seconds: Delay before task becomes available
        """
        task.attempts += 1
        
        if task.attempts >= task.max_attempts:
            # Move to dead letter queue
            await self.push_dead_letter(task)
        else:
            if not queue_name:
                queue_name = f"queue:{task.capability.replace(':', '_')}"
                
            # Calculate score with delay
            score = datetime.now().timestamp() + delay_seconds
            
            await self.redis.zadd(
                queue_name,
                {task.json(): score}
            )
    
    async def push_dead_letter(self, task: Task):
        """Push task to dead letter queue.
        
        Args:
            task: Failed task
        """
        await self.redis.zadd(
            "queue:dead_letter",
            {task.json(): datetime.now().timestamp()}
        )
        
        # Also store failure info
        await self.redis.hset(
            f"failed_task:{task.task_id}",
            mapping={
                "task": task.json(),
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "attempts": str(task.attempts),
            }
        )
    
    async def get_queue_stats(self, queue_name: str) -> dict[str, Any]:
        """Get queue statistics.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Queue statistics
        """
        size = await self.redis.zcard(queue_name)
        
        # Get oldest and newest tasks
        oldest = await self.redis.zrange(queue_name, 0, 0, withscores=True)
        newest = await self.redis.zrange(queue_name, -1, -1, withscores=True)
        
        return {
            "queue": queue_name,
            "size": size,
            "oldest_score": oldest[0][1] if oldest else None,
            "newest_score": newest[0][1] if newest else None,
        }
    
    async def clear_queue(self, queue_name: str) -> int:
        """Clear all tasks from a queue.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Number of tasks removed
        """
        size = await self.redis.zcard(queue_name)
        await self.redis.delete(queue_name)
        return size