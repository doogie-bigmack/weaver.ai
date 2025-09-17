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
    max_items: int | None = None  # For test compatibility
    compression: bool = True
    ttl_days: int | None = None  # None = no expiry
    ttl_seconds: int | None = None  # For test compatibility


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

    def __init__(
        self,
        short_term_size: int | None = None,
        long_term_size: int | None = None,
        short_term_ttl: int | None = None,
        long_term_ttl: int | None = None,
        **kwargs,
    ):
        """Initialize memory strategy with optional test compatibility parameters."""
        # Handle test compatibility parameters
        if short_term_size is not None:
            kwargs.setdefault("short_term", {})
            kwargs["short_term"]["max_items"] = short_term_size

        if long_term_size is not None:
            kwargs.setdefault("long_term", {})
            # For test compatibility: interpret as max_items
            kwargs["long_term"]["max_items"] = long_term_size

        if short_term_ttl is not None:
            kwargs.setdefault("short_term", {})
            kwargs["short_term"]["ttl_seconds"] = short_term_ttl

        if long_term_ttl is not None:
            kwargs.setdefault("long_term", {})
            # For test compatibility: store as ttl_seconds if < 1 day
            if long_term_ttl < 86400:
                kwargs["long_term"]["ttl_seconds"] = long_term_ttl
            else:
                kwargs["long_term"]["ttl_days"] = long_term_ttl // 86400

        # Initialize configs from kwargs
        if "short_term" in kwargs and isinstance(kwargs["short_term"], dict):
            kwargs["short_term"] = ShortTermConfig(**kwargs["short_term"])
        if "long_term" in kwargs and isinstance(kwargs["long_term"], dict):
            kwargs["long_term"] = LongTermConfig(**kwargs["long_term"])
        if "episodic" in kwargs and isinstance(kwargs["episodic"], dict):
            kwargs["episodic"] = EpisodicConfig(**kwargs["episodic"])
        if "semantic" in kwargs and isinstance(kwargs["semantic"], dict):
            kwargs["semantic"] = SemanticConfig(**kwargs["semantic"])
        if "persistent" in kwargs and isinstance(kwargs["persistent"], dict):
            kwargs["persistent"] = PersistentConfig(**kwargs["persistent"])

        super().__init__(**kwargs)

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
