"""Memory strategy configurations for different agent roles."""

from __future__ import annotations

from pydantic import BaseModel


class ShortTermConfig(BaseModel):
    """Short-term memory configuration."""

    enabled: bool = True
    max_items: int = 100
    ttl_seconds: int = 3600  # 1 hour default


class LongTermConfig(BaseModel):
    """Long-term memory configuration."""

    enabled: bool = True
    max_size_mb: int = 1024  # 1GB default
    compression: bool = True
    ttl_days: int | None = None  # None = no expiry


class EpisodicConfig(BaseModel):
    """Episodic memory configuration."""

    enabled: bool = False
    max_episodes: int = 1000
    importance_threshold: float = 0.7
    consolidation_interval: int = 3600  # seconds


class SemanticConfig(BaseModel):
    """Semantic memory configuration for knowledge storage."""

    enabled: bool = False
    vector_dimensions: int = 1536  # OpenAI embedding size
    index_type: str = "flat"  # flat, hnsw, ivf
    similarity_threshold: float = 0.8


class PersistentConfig(BaseModel):
    """Persistence configuration for memory across restarts."""

    enabled: bool = True
    checkpoint_interval: int = 300  # 5 minutes
    backup_location: str = "/data/agents/{agent_id}/memory"
    max_backups: int = 3


class MemoryStrategy(BaseModel):
    """Complete memory strategy for an agent."""

    short_term: ShortTermConfig = ShortTermConfig()
    long_term: LongTermConfig = LongTermConfig()
    episodic: EpisodicConfig = EpisodicConfig()
    semantic: SemanticConfig = SemanticConfig()
    persistent: PersistentConfig = PersistentConfig()

    @classmethod
    def analyst_strategy(cls) -> MemoryStrategy:
        """Strategy optimized for data analysts."""
        return cls(
            short_term=ShortTermConfig(max_items=1000, ttl_seconds=7200),
            long_term=LongTermConfig(max_size_mb=10240),  # 10GB
            semantic=SemanticConfig(enabled=True),  # For pattern matching
            persistent=PersistentConfig(enabled=True),
        )

    @classmethod
    def coordinator_strategy(cls) -> MemoryStrategy:
        """Strategy optimized for workflow coordinators."""
        return cls(
            short_term=ShortTermConfig(max_items=5000, ttl_seconds=1800),
            long_term=LongTermConfig(enabled=False),  # Don't need history
            episodic=EpisodicConfig(enabled=True, max_episodes=100),
            persistent=PersistentConfig(enabled=True),
        )

    @classmethod
    def validator_strategy(cls) -> MemoryStrategy:
        """Strategy optimized for validators."""
        return cls(
            short_term=ShortTermConfig(max_items=500),
            long_term=LongTermConfig(max_size_mb=512),
            semantic=SemanticConfig(enabled=True, similarity_threshold=0.95),
            persistent=PersistentConfig(enabled=False),  # Stateless
        )

    @classmethod
    def minimal_strategy(cls) -> MemoryStrategy:
        """Minimal memory for simple agents."""
        return cls(
            short_term=ShortTermConfig(max_items=50, ttl_seconds=600),
            long_term=LongTermConfig(enabled=False),
            episodic=EpisodicConfig(enabled=False),
            semantic=SemanticConfig(enabled=False),
            persistent=PersistentConfig(enabled=False),
        )
