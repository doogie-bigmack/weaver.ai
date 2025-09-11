"""Result publisher for secure agent result sharing.

The ResultPublisher provides secure, versioned result storage with access control.
Agents can publish results and other agents can retrieve them based on capabilities.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

import redis.asyncio as redis
from pydantic import BaseModel, Field


class ResultMetadata(BaseModel):
    """Metadata for a published result."""

    result_id: str = Field(default_factory=lambda: uuid4().hex)
    agent_id: str
    workflow_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    version: int = 1
    capabilities_required: list[str] = []
    ttl_seconds: int = 3600  # Default 1 hour
    content_type: str = "application/json"
    size_bytes: int = 0
    checksum: str | None = None
    parent_result_id: str | None = None  # For lineage tracking
    tags: dict[str, str] = {}


class PublishedResult(BaseModel):
    """A published result from an agent."""

    metadata: ResultMetadata
    data: Any
    access_token: str | None = None  # Optional capability token


class ResultPublisher:
    """Manages secure result publishing and retrieval between agents.

    Features:
    - Secure result storage in Redis with optional S3 backup
    - Access control via capability tokens
    - Result versioning and lineage tracking
    - Automatic TTL and cleanup
    - Metadata indexing for efficient queries
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        redis_url: str = "redis://localhost:6379",
        namespace: str = "results",
        enable_s3_backup: bool = False,
        s3_bucket: str | None = None,
    ):
        """Initialize the ResultPublisher.

        Args:
            redis_client: Existing Redis client or None to create one
            redis_url: Redis connection URL
            namespace: Redis key namespace for results
            enable_s3_backup: Whether to backup large results to S3
            s3_bucket: S3 bucket name for backups
        """
        self.redis = redis_client
        self.redis_url = redis_url
        self.namespace = namespace
        self.enable_s3_backup = enable_s3_backup
        self.s3_bucket = s3_bucket
        self._connected = False

    async def connect(self) -> None:
        """Connect to Redis if not already connected."""
        if not self._connected and not self.redis:
            self.redis = await redis.from_url(self.redis_url)
            self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._connected and self.redis:
            await self.redis.close()
            self._connected = False

    async def publish(
        self,
        agent_id: str,
        data: Any,
        capabilities_required: list[str] | None = None,
        workflow_id: str | None = None,
        ttl_seconds: int = 3600,
        parent_result_id: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> PublishedResult:
        """Publish a result from an agent.

        Args:
            agent_id: ID of the publishing agent
            data: Result data to publish
            capabilities_required: Capabilities needed to access this result
            workflow_id: Optional workflow ID for grouping
            ttl_seconds: Time to live in seconds
            parent_result_id: Parent result for lineage tracking
            tags: Optional tags for categorization

        Returns:
            PublishedResult with metadata and access token
        """
        await self.connect()

        # Serialize data
        if isinstance(data, BaseModel):
            serialized = data.model_dump_json()
        elif isinstance(data, dict | list):
            serialized = json.dumps(data)
        else:
            serialized = str(data)

        # Create metadata
        metadata = ResultMetadata(
            agent_id=agent_id,
            workflow_id=workflow_id,
            capabilities_required=capabilities_required or [],
            ttl_seconds=ttl_seconds,
            size_bytes=len(serialized.encode()),
            parent_result_id=parent_result_id,
            tags=tags or {},
        )

        # Generate access token if capabilities required
        access_token = None
        if capabilities_required:
            access_token = self._generate_access_token(metadata.result_id)

        # Store in Redis
        result_key = f"{self.namespace}:{metadata.result_id}"

        # Store result data
        await self.redis.setex(
            f"{result_key}:data",
            ttl_seconds,
            serialized,
        )

        # Store metadata
        await self.redis.setex(
            f"{result_key}:metadata",
            ttl_seconds,
            metadata.model_dump_json(),
        )

        # Index by workflow if specified
        if workflow_id:
            workflow_key = f"{self.namespace}:workflows:{workflow_id}"
            await self.redis.sadd(workflow_key, metadata.result_id)
            await self.redis.expire(workflow_key, ttl_seconds)

        # Index by agent
        agent_key = f"{self.namespace}:agents:{agent_id}"
        await self.redis.zadd(
            agent_key,
            {metadata.result_id: metadata.timestamp},
        )
        await self.redis.expire(agent_key, ttl_seconds)

        # Index by capabilities
        for capability in capabilities_required or []:
            cap_key = f"{self.namespace}:capabilities:{capability}"
            await self.redis.sadd(cap_key, metadata.result_id)
            await self.redis.expire(cap_key, ttl_seconds)

        # Store lineage if parent specified
        if parent_result_id:
            lineage_key = f"{self.namespace}:lineage:{parent_result_id}"
            await self.redis.sadd(lineage_key, metadata.result_id)
            await self.redis.expire(lineage_key, ttl_seconds)

        # Backup to S3 if enabled and result is large
        if self.enable_s3_backup and metadata.size_bytes > 1024 * 1024:  # 1MB
            await self._backup_to_s3(metadata.result_id, serialized)

        return PublishedResult(
            metadata=metadata,
            data=data,
            access_token=access_token,
        )

    async def retrieve(
        self,
        result_id: str,
        agent_capabilities: list[str] | None = None,
        access_token: str | None = None,
    ) -> PublishedResult | None:
        """Retrieve a published result.

        Args:
            result_id: ID of the result to retrieve
            agent_capabilities: Capabilities of the requesting agent
            access_token: Optional access token for authorization

        Returns:
            PublishedResult if authorized, None otherwise
        """
        await self.connect()

        # Get metadata
        metadata_key = f"{self.namespace}:{result_id}:metadata"
        metadata_json = await self.redis.get(metadata_key)

        if not metadata_json:
            return None

        metadata = ResultMetadata.model_validate_json(metadata_json)

        # Check access control
        if metadata.capabilities_required:
            # Check if agent has required capabilities
            if agent_capabilities:
                has_access = any(
                    cap in agent_capabilities for cap in metadata.capabilities_required
                )
            else:
                has_access = False

            # Check access token as alternative
            if not has_access and access_token:
                has_access = self._verify_access_token(result_id, access_token)

            if not has_access:
                return None  # Not authorized

        # Get data
        data_key = f"{self.namespace}:{result_id}:data"
        data_json = await self.redis.get(data_key)

        if not data_json:
            # Try S3 backup if enabled
            if self.enable_s3_backup:
                data_json = await self._retrieve_from_s3(result_id)

            if not data_json:
                return None

        # Deserialize data
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            data = data_json.decode() if isinstance(data_json, bytes) else data_json

        return PublishedResult(
            metadata=metadata,
            data=data,
        )

    async def list_by_workflow(
        self,
        workflow_id: str,
        agent_capabilities: list[str] | None = None,
    ) -> list[ResultMetadata]:
        """List all results for a workflow.

        Args:
            workflow_id: Workflow ID to query
            agent_capabilities: Capabilities for filtering

        Returns:
            List of result metadata
        """
        await self.connect()

        workflow_key = f"{self.namespace}:workflows:{workflow_id}"
        result_ids = await self.redis.smembers(workflow_key)

        results = []
        for result_id in result_ids:
            result = await self.retrieve(
                result_id.decode() if isinstance(result_id, bytes) else result_id,
                agent_capabilities=agent_capabilities,
            )
            if result:
                results.append(result.metadata)

        return sorted(results, key=lambda r: r.timestamp)

    async def list_by_agent(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> list[ResultMetadata]:
        """List recent results from an agent.

        Args:
            agent_id: Agent ID to query
            limit: Maximum number of results

        Returns:
            List of result metadata
        """
        await self.connect()

        agent_key = f"{self.namespace}:agents:{agent_id}"
        result_ids = await self.redis.zrevrange(agent_key, 0, limit - 1)

        results = []
        for result_id in result_ids:
            rid = result_id.decode() if isinstance(result_id, bytes) else result_id
            metadata_key = f"{self.namespace}:{rid}:metadata"
            metadata_json = await self.redis.get(metadata_key)
            if metadata_json:
                results.append(ResultMetadata.model_validate_json(metadata_json))

        return results

    async def get_lineage(
        self,
        result_id: str,
        max_depth: int = 10,
    ) -> list[ResultMetadata]:
        """Get lineage of a result (parent and children).

        Args:
            result_id: Result ID to trace
            max_depth: Maximum depth to traverse

        Returns:
            List of related results in lineage order
        """
        await self.connect()

        lineage = []
        visited = set()

        async def traverse(rid: str, depth: int):
            if depth >= max_depth or rid in visited:
                return

            visited.add(rid)

            # Get metadata
            metadata_key = f"{self.namespace}:{rid}:metadata"
            metadata_json = await self.redis.get(metadata_key)

            if metadata_json:
                metadata = ResultMetadata.model_validate_json(metadata_json)
                lineage.append(metadata)

                # Get children
                lineage_key = f"{self.namespace}:lineage:{rid}"
                children = await self.redis.smembers(lineage_key)

                for child_id in children:
                    child = (
                        child_id.decode() if isinstance(child_id, bytes) else child_id
                    )
                    await traverse(child, depth + 1)

        await traverse(result_id, 0)
        return lineage

    async def cleanup_expired(self) -> int:
        """Clean up expired results.

        Returns:
            Number of results cleaned up
        """
        # Redis handles TTL automatically
        # This method is for compatibility and logging
        return 0

    def _generate_access_token(self, result_id: str) -> str:
        """Generate an access token for a result."""
        # Simple token generation - in production use JWT or similar
        return f"tok_{result_id}_{uuid4().hex[:8]}"

    def _verify_access_token(self, result_id: str, token: str) -> bool:
        """Verify an access token for a result."""
        # Simple verification - in production use JWT or similar
        return token.startswith(f"tok_{result_id}_")

    async def _backup_to_s3(self, result_id: str, data: str) -> None:
        """Backup large result to S3."""
        # Placeholder for S3 backup
        # In production, use boto3 or similar
        pass

    async def _retrieve_from_s3(self, result_id: str) -> str | None:
        """Retrieve result from S3 backup."""
        # Placeholder for S3 retrieval
        # In production, use boto3 or similar
        return None
