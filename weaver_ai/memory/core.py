"""Core memory implementation for agents."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel

from .strategies import MemoryStrategy


class MemoryUsage(BaseModel):
    """Track memory usage statistics."""
    
    short_term_items: int = 0
    long_term_bytes: int = 0
    episodic_count: int = 0
    semantic_vectors: int = 0
    total_recalls: int = 0
    total_stores: int = 0
    last_persist: datetime | None = None


class MemoryItem(BaseModel):
    """Individual memory item."""
    
    key: str
    value: Any
    memory_type: str
    timestamp: datetime = datetime.now(timezone.utc)
    access_count: int = 0
    importance: float = 1.0


class AgentMemory:
    """Agent memory system with multiple storage types.
    
    Supports short-term, long-term, episodic, and semantic memory
    with configurable strategies and Redis persistence.
    """
    
    def __init__(
        self,
        strategy: MemoryStrategy,
        agent_id: str,
        redis_client: aioredis.Redis | None = None,
    ):
        """Initialize agent memory.
        
        Args:
            strategy: Memory strategy configuration
            agent_id: Agent identifier
            redis_client: Optional Redis client for persistence
        """
        self.strategy = strategy
        self.agent_id = agent_id
        self.redis = redis_client
        
        # Memory stores
        self.short_term: OrderedDict[str, MemoryItem] = OrderedDict()
        self.long_term: dict[str, MemoryItem] = {}
        self.episodic: list[MemoryItem] = []
        self.semantic: dict[str, MemoryItem] = {}
        
        # Usage tracking
        self.usage = MemoryUsage()
        
        # Persistence
        self._last_checkpoint = time.time()
        
    async def initialize(self):
        """Initialize memory and restore from persistence if available."""
        if self.strategy.persistent.enabled and self.redis:
            await self.restore()
    
    async def remember(
        self,
        key: str,
        value: Any,
        memory_type: str = "short_term",
        importance: float = 1.0,
    ):
        """Store information in memory.
        
        Args:
            key: Memory key
            value: Value to store
            memory_type: Type of memory (short_term, long_term, episodic, semantic)
            importance: Importance score (0-1)
        """
        item = MemoryItem(
            key=key,
            value=value,
            memory_type=memory_type,
            importance=importance,
        )
        
        if memory_type == "short_term" and self.strategy.short_term.enabled:
            await self._store_short_term(item)
        elif memory_type == "long_term" and self.strategy.long_term.enabled:
            await self._store_long_term(item)
        elif memory_type == "episodic" and self.strategy.episodic.enabled:
            await self._store_episodic(item)
        elif memory_type == "semantic" and self.strategy.semantic.enabled:
            await self._store_semantic(item)
            
        self.usage.total_stores += 1
        
        # Check if we need to persist
        await self._check_persistence()
    
    async def _store_short_term(self, item: MemoryItem):
        """Store in short-term memory with LRU eviction."""
        # Check TTL and evict expired items
        now = datetime.now(timezone.utc)
        ttl = timedelta(seconds=self.strategy.short_term.ttl_seconds)
        
        expired_keys = []
        for k, v in self.short_term.items():
            if now - v.timestamp > ttl:
                expired_keys.append(k)
                
        for k in expired_keys:
            del self.short_term[k]
        
        # Add new item
        self.short_term[item.key] = item
        
        # Evict oldest if over limit
        while len(self.short_term) > self.strategy.short_term.max_items:
            self.short_term.popitem(last=False)
            
        self.usage.short_term_items = len(self.short_term)
    
    async def _store_long_term(self, item: MemoryItem):
        """Store in long-term memory."""
        self.long_term[item.key] = item
        
        # Simple size estimation (with date handling)
        item_size = len(json.dumps(item.dict(), default=str))
        self.usage.long_term_bytes += item_size
        
        # Check size limit
        max_bytes = self.strategy.long_term.max_size_mb * 1024 * 1024
        if self.usage.long_term_bytes > max_bytes:
            # Remove least important items
            sorted_items = sorted(
                self.long_term.items(),
                key=lambda x: x[1].importance,
            )
            
            while self.usage.long_term_bytes > max_bytes and sorted_items:
                key, _ = sorted_items.pop(0)
                del self.long_term[key]
                # Recalculate size (simplified)
                self.usage.long_term_bytes = len(json.dumps([
                    item.dict() for item in self.long_term.values()
                ], default=str))
    
    async def _store_episodic(self, item: MemoryItem):
        """Store episodic memory."""
        # Only store if above importance threshold
        if item.importance >= self.strategy.episodic.importance_threshold:
            self.episodic.append(item)
            
            # Limit episodes
            while len(self.episodic) > self.strategy.episodic.max_episodes:
                self.episodic.pop(0)
                
            self.usage.episodic_count = len(self.episodic)
    
    async def _store_semantic(self, item: MemoryItem):
        """Store semantic memory (simplified - real impl would use embeddings)."""
        self.semantic[item.key] = item
        self.usage.semantic_vectors = len(self.semantic)
    
    async def recall(
        self,
        query: str | None = None,
        memory_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """Retrieve memories.
        
        Args:
            query: Search query (None = get all)
            memory_types: Memory types to search (None = all)
            limit: Maximum results
            
        Returns:
            List of memory items
        """
        if memory_types is None:
            memory_types = ["short_term", "long_term", "episodic", "semantic"]
            
        results = []
        
        for memory_type in memory_types:
            if memory_type == "short_term" and self.strategy.short_term.enabled:
                results.extend(self._search_short_term(query, limit))
            elif memory_type == "long_term" and self.strategy.long_term.enabled:
                results.extend(self._search_long_term(query, limit))
            elif memory_type == "episodic" and self.strategy.episodic.enabled:
                results.extend(self._search_episodic(query, limit))
            elif memory_type == "semantic" and self.strategy.semantic.enabled:
                results.extend(self._search_semantic(query, limit))
        
        # Update access counts
        for item in results:
            item.access_count += 1
            
        self.usage.total_recalls += 1
        
        # Sort by relevance (simplified - by importance and recency)
        results.sort(
            key=lambda x: (x.importance, x.timestamp),
            reverse=True,
        )
        
        return results[:limit]
    
    def _search_short_term(self, query: str | None, limit: int) -> list[MemoryItem]:
        """Search short-term memory."""
        items = list(self.short_term.values())
        
        if query:
            # Simple string matching
            items = [
                item for item in items
                if query.lower() in str(item.value).lower()
                or query.lower() in item.key.lower()
            ]
            
        return items[-limit:]  # Most recent
    
    def _search_long_term(self, query: str | None, limit: int) -> list[MemoryItem]:
        """Search long-term memory."""
        items = list(self.long_term.values())
        
        if query:
            items = [
                item for item in items
                if query.lower() in str(item.value).lower()
                or query.lower() in item.key.lower()
            ]
            
        return items[:limit]
    
    def _search_episodic(self, query: str | None, limit: int) -> list[MemoryItem]:
        """Search episodic memory."""
        items = self.episodic.copy()
        
        if query:
            items = [
                item for item in items
                if query.lower() in str(item.value).lower()
            ]
            
        return items[-limit:]  # Most recent episodes
    
    def _search_semantic(self, query: str | None, limit: int) -> list[MemoryItem]:
        """Search semantic memory (simplified)."""
        items = list(self.semantic.values())
        
        if query:
            # In real implementation, would use vector similarity
            items = [
                item for item in items
                if query.lower() in str(item.value).lower()
                or query.lower() in item.key.lower()
            ]
            
        return items[:limit]
    
    async def forget(self, key: str, memory_type: str | None = None):
        """Remove memory item.
        
        Args:
            key: Memory key
            memory_type: Specific memory type (None = all)
        """
        if memory_type == "short_term" or memory_type is None:
            self.short_term.pop(key, None)
            
        if memory_type == "long_term" or memory_type is None:
            self.long_term.pop(key, None)
            
        if memory_type == "semantic" or memory_type is None:
            self.semantic.pop(key, None)
    
    async def clear(self, memory_type: str | None = None):
        """Clear memory.
        
        Args:
            memory_type: Specific memory type (None = all)
        """
        if memory_type == "short_term" or memory_type is None:
            self.short_term.clear()
            
        if memory_type == "long_term" or memory_type is None:
            self.long_term.clear()
            
        if memory_type == "episodic" or memory_type is None:
            self.episodic.clear()
            
        if memory_type == "semantic" or memory_type is None:
            self.semantic.clear()
            
        # Reset usage
        if memory_type is None:
            self.usage = MemoryUsage()
    
    async def _check_persistence(self):
        """Check if we need to persist memory."""
        if not self.strategy.persistent.enabled or not self.redis:
            return
            
        now = time.time()
        if now - self._last_checkpoint > self.strategy.persistent.checkpoint_interval:
            await self.persist()
            self._last_checkpoint = now
    
    async def persist(self):
        """Save memory to Redis for persistence."""
        if not self.redis:
            return
            
        memory_data = {
            "short_term": [item.dict() for item in self.short_term.values()],
            "long_term": [item.dict() for item in self.long_term.values()],
            "episodic": [item.dict() for item in self.episodic],
            "semantic": [item.dict() for item in self.semantic.values()],
            "usage": self.usage.dict(),
        }
        
        # Save to Redis with expiry
        key = f"agent_memory:{self.agent_id}"
        await self.redis.setex(
            key,
            86400,  # 24 hour expiry
            json.dumps(memory_data, default=str),
        )
        
        self.usage.last_persist = datetime.now(timezone.utc)
    
    async def restore(self):
        """Restore memory from Redis."""
        if not self.redis:
            return
            
        key = f"agent_memory:{self.agent_id}"
        data = await self.redis.get(key)
        
        if not data:
            return
            
        try:
            memory_data = json.loads(data)
            
            # Restore short-term memory
            self.short_term.clear()
            for item_dict in memory_data.get("short_term", []):
                item = MemoryItem(**item_dict)
                self.short_term[item.key] = item
                
            # Restore long-term memory
            self.long_term.clear()
            for item_dict in memory_data.get("long_term", []):
                item = MemoryItem(**item_dict)
                self.long_term[item.key] = item
                
            # Restore episodic memory
            self.episodic.clear()
            for item_dict in memory_data.get("episodic", []):
                self.episodic.append(MemoryItem(**item_dict))
                
            # Restore semantic memory
            self.semantic.clear()
            for item_dict in memory_data.get("semantic", []):
                item = MemoryItem(**item_dict)
                self.semantic[item.key] = item
                
            # Restore usage
            if "usage" in memory_data:
                self.usage = MemoryUsage(**memory_data["usage"])
                
        except Exception as e:
            print(f"Error restoring memory for agent {self.agent_id}: {e}")