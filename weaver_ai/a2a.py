from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import jwt
from pydantic import BaseModel, Field

from .redis.nonce_store import SyncRedisNonceStore

logger = logging.getLogger(__name__)


class Capability(BaseModel):
    name: str
    version: str
    scopes: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    tokens: int
    time_ms: int
    tool_calls: int


class A2AEnvelope(BaseModel):
    request_id: str
    sender_id: str
    receiver_id: str
    created_at: datetime
    nonce: str
    capabilities: list[Capability]
    budget: Budget
    payload: dict[str, Any]
    signature: str | None = None


# Initialize Redis-backed nonce store with fallback to memory
# This provides persistent, distributed nonce storage
_nonce_store = SyncRedisNonceStore(
    redis_url="redis://localhost:6379/0",
    namespace="a2a:nonce",
    ttl_seconds=300,  # 5 minutes TTL
    fallback_to_memory=True,  # Fallback to in-memory if Redis is unavailable
)


def canonical_json(obj: Any) -> bytes:
    """
    Convert object to canonical JSON for consistent hashing/signing.

    Args:
        obj: Object to convert

    Returns:
        Canonical JSON bytes
    """

    def convert(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, dict):
            return {k: convert(v) for k, v in o.items()}
        if isinstance(o, list):
            return [convert(i) for i in o]
        return o

    return json.dumps(convert(obj), sort_keys=True, separators=(",", ":")).encode()


def sign(envelope: A2AEnvelope, private_key: str) -> str:
    """
    Sign an A2A envelope with RS256 algorithm.

    Args:
        envelope: The envelope to sign
        private_key: RSA private key in PEM format

    Returns:
        JWT signature string
    """
    payload = canonical_json(envelope.model_dump(exclude={"signature"}))
    return jwt.encode({"payload": payload.decode()}, private_key, algorithm="RS256")


def verify(envelope: A2AEnvelope, public_key: str) -> bool:
    """
    Verify an A2A envelope signature and check for replay attacks.

    Args:
        envelope: The envelope to verify
        public_key: RSA public key in PEM format

    Returns:
        True if signature is valid and nonce is not replayed, False otherwise
    """
    # Check nonce for replay attack using Redis-backed store
    if not _nonce_store.check_and_add(envelope.nonce):
        logger.warning(f"Nonce replay detected: {envelope.nonce}")
        return False

    try:
        decoded = jwt.decode(envelope.signature or "", public_key, algorithms=["RS256"])
        logger.debug(f"JWT decode successful, payload keys: {list(decoded.keys())}")
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode failed: {type(e).__name__}: {e}")
        return False

    payload = canonical_json(envelope.model_dump(exclude={"signature"})).decode()
    decoded_payload = decoded.get("payload")
    matches = decoded_payload == payload

    if not matches:
        logger.error(
            f"Payload mismatch. Expected length: {len(payload)}, "
            f"Got length: {len(decoded_payload) if decoded_payload else 0}"
        )
        logger.debug(f"Expected (first 100): {payload[:100]}")
        logger.debug(
            f"Got (first 100): {decoded_payload[:100] if decoded_payload else 'None'}"
        )

    return matches


def check_timestamp(envelope: A2AEnvelope, skew_seconds: int = 30) -> bool:
    """
    Check if envelope timestamp is within acceptable skew.

    Args:
        envelope: The envelope to check
        skew_seconds: Maximum allowed time skew in seconds

    Returns:
        True if timestamp is within acceptable range, False otherwise
    """
    now = datetime.now(UTC)
    return abs((now - envelope.created_at).total_seconds()) <= skew_seconds


def get_nonce_store_stats() -> dict:
    """
    Get statistics about the nonce store.

    Returns:
        Dictionary with nonce store statistics
    """
    try:
        # For sync store, we return basic stats
        return {
            "type": "redis_backed",
            "namespace": _nonce_store.namespace,
            "ttl_seconds": _nonce_store.ttl_seconds,
            "fallback_enabled": _nonce_store.fallback_to_memory,
            "memory_store_size": len(_nonce_store._memory_store),
        }
    except Exception as e:
        logger.error(f"Failed to get nonce store stats: {e}")
        return {"error": str(e)}


def configure_nonce_store(
    redis_url: str = "redis://localhost:6379/0",
    namespace: str = "a2a:nonce",
    ttl_seconds: int = 300,
    fallback_to_memory: bool = True,
) -> None:
    """
    Configure the global nonce store.

    Args:
        redis_url: Redis connection URL
        namespace: Redis key namespace for nonces
        ttl_seconds: Time-to-live for nonces in seconds
        fallback_to_memory: If True, fallback to in-memory storage on Redis failure
    """
    global _nonce_store

    # Close existing store if any
    if _nonce_store:
        try:
            _nonce_store.close()
        except Exception as e:
            logger.error(f"Error closing existing nonce store: {e}")

    # Create new store with configuration
    _nonce_store = SyncRedisNonceStore(
        redis_url=redis_url,
        namespace=namespace,
        ttl_seconds=ttl_seconds,
        fallback_to_memory=fallback_to_memory,
    )

    logger.info(
        f"Nonce store configured: redis_url={redis_url}, "
        f"namespace={namespace}, ttl={ttl_seconds}s, "
        f"fallback={fallback_to_memory}"
    )
