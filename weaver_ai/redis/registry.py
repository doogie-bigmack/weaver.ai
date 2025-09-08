"""Redis-backed agent registry for distributed agent discovery."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel


class AgentInfo(BaseModel):
    """Information about a registered agent."""

    agent_id: str
    agent_type: str
    capabilities: list[str]
    status: str = "online"
    registered_at: datetime
    last_heartbeat: datetime | None = None
    metadata: dict[str, Any] = {}


class RedisAgentRegistry:
    """Redis-backed agent registry for distributed agents.

    Tracks agent capabilities and health status using Redis.
    """

    def __init__(self, redis: aioredis.Redis):
        """Initialize registry.

        Args:
            redis: Redis connection
        """
        self.redis = redis
        self.heartbeat_ttl = 30  # seconds

    async def register(self, agent_info: AgentInfo) -> str:
        """Register agent in Redis.

        Args:
            agent_info: Agent information

        Returns:
            Agent ID
        """
        # Store agent info
        await self.redis.hset("agents", agent_info.agent_id, agent_info.json())

        # Index by capabilities
        for capability in agent_info.capabilities:
            await self.redis.sadd(
                f"capability:{capability.replace(':', '_')}", agent_info.agent_id
            )

        # Index by type
        await self.redis.sadd(
            f"agent_type:{agent_info.agent_type}", agent_info.agent_id
        )

        # Set initial heartbeat
        await self.heartbeat(agent_info.agent_id)

        # Publish registration event
        await self.redis.publish(
            "agent:registered",
            json.dumps(
                {
                    "agent_id": agent_info.agent_id,
                    "capabilities": agent_info.capabilities,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ),
        )

        return agent_info.agent_id

    async def unregister(self, agent_id: str):
        """Unregister agent.

        Args:
            agent_id: Agent ID to unregister
        """
        # Get agent info first
        agent_json = await self.redis.hget("agents", agent_id)
        if not agent_json:
            return

        agent_info = AgentInfo.parse_raw(agent_json)

        # Remove from capability indices
        for capability in agent_info.capabilities:
            await self.redis.srem(
                f"capability:{capability.replace(':', '_')}", agent_id
            )

        # Remove from type index
        await self.redis.srem(f"agent_type:{agent_info.agent_type}", agent_id)

        # Remove agent info
        await self.redis.hdel("agents", agent_id)

        # Remove heartbeat
        await self.redis.delete(f"heartbeat:{agent_id}")

        # Publish unregistration event
        await self.redis.publish(
            "agent:unregistered",
            json.dumps(
                {
                    "agent_id": agent_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ),
        )

    async def heartbeat(self, agent_id: str):
        """Update agent heartbeat.

        Args:
            agent_id: Agent ID
        """
        await self.redis.setex(
            f"heartbeat:{agent_id}", self.heartbeat_ttl, datetime.now(UTC).isoformat()
        )

        # Update last heartbeat in agent info
        agent_json = await self.redis.hget("agents", agent_id)
        if agent_json:
            agent_info = AgentInfo.parse_raw(agent_json)
            agent_info.last_heartbeat = datetime.now(UTC)
            await self.redis.hset("agents", agent_id, agent_info.json())

    async def find_capable_agents(
        self,
        capabilities: list[str],
        require_all: bool = True,
        only_online: bool = True,
    ) -> list[str]:
        """Find agents with specified capabilities.

        Args:
            capabilities: Required capabilities
            require_all: Whether agents must have all capabilities
            only_online: Only return online agents

        Returns:
            List of agent IDs
        """
        if not capabilities:
            return []

        agent_sets = []
        for capability in capabilities:
            key = f"capability:{capability.replace(':', '_')}"
            agents = await self.redis.smembers(key)
            agent_sets.append(agents)

        if require_all:
            # Intersection - agents with all capabilities
            result = agent_sets[0]
            for agent_set in agent_sets[1:]:
                result = result.intersection(agent_set)
        else:
            # Union - agents with any capability
            result = set()
            for agent_set in agent_sets:
                result = result.union(agent_set)

        # Filter to online agents if requested
        if only_online:
            online = []
            for agent_id in result:
                if await self.is_online(agent_id):
                    online.append(agent_id)
            return online

        return list(result)

    async def is_online(self, agent_id: str) -> bool:
        """Check if agent is online.

        Args:
            agent_id: Agent ID

        Returns:
            True if online
        """
        return await self.redis.exists(f"heartbeat:{agent_id}") > 0

    async def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        """Get agent information.

        Args:
            agent_id: Agent ID

        Returns:
            Agent info if found
        """
        agent_json = await self.redis.hget("agents", agent_id)
        if agent_json:
            return AgentInfo.parse_raw(agent_json)
        return None

    async def list_agents(
        self,
        agent_type: str | None = None,
        only_online: bool = False,
    ) -> list[AgentInfo]:
        """List all agents.

        Args:
            agent_type: Filter by agent type
            only_online: Only return online agents

        Returns:
            List of agent information
        """
        if agent_type:
            # Get agents of specific type
            agent_ids = await self.redis.smembers(f"agent_type:{agent_type}")
        else:
            # Get all agents
            agents_dict = await self.redis.hgetall("agents")
            agent_ids = agents_dict.keys()

        agents = []
        for agent_id in agent_ids:
            if only_online and not await self.is_online(agent_id):
                continue

            info = await self.get_agent_info(agent_id)
            if info:
                agents.append(info)

        return agents

    async def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Statistics dictionary
        """
        total_agents = await self.redis.hlen("agents")

        # Count online agents
        online_count = 0
        agents_dict = await self.redis.hgetall("agents")
        for agent_id in agents_dict.keys():
            if await self.is_online(agent_id):
                online_count += 1

        # Get capability counts
        capability_keys = []
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor, match="capability:*", count=100
            )
            capability_keys.extend(keys)
            if cursor == 0:
                break

        capability_counts = {}
        for key in capability_keys:
            capability = key.replace("capability:", "").replace("_", ":")
            count = await self.redis.scard(key)
            capability_counts[capability] = count

        return {
            "total_agents": total_agents,
            "online_agents": online_count,
            "offline_agents": total_agents - online_count,
            "capabilities": capability_counts,
        }
