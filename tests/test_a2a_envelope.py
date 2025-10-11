from __future__ import annotations

from datetime import UTC, datetime

import pytest
import redis

from weaver_ai.a2a import A2AEnvelope, Budget, Capability, sign, verify
from weaver_ai.crypto_utils import generate_rsa_key_pair


@pytest.fixture(autouse=True)
def cleanup_redis_nonces():
    """Clean up Redis nonces before each test."""
    try:
        r = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        # Delete all a2a:nonce:* keys
        keys = r.keys("a2a:nonce:*")
        if keys:
            r.delete(*keys)
    except Exception:
        # If Redis is not available, tests will use memory fallback
        pass
    yield
    # Cleanup after test as well
    try:
        r = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        keys = r.keys("a2a:nonce:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def make_env(nonce: str) -> A2AEnvelope:
    return A2AEnvelope(
        request_id="1",
        sender_id="a",
        receiver_id="b",
        created_at=datetime.now(UTC),
        nonce=nonce,
        capabilities=[Capability(name="x", version="1", scopes=[])],
        budget=Budget(tokens=1, time_ms=1, tool_calls=1),
        payload={"hello": "world"},
    )


def test_sign_verify():
    # Generate RSA key pair for RS256 testing
    private_key, public_key = generate_rsa_key_pair()

    env = make_env("n")
    env.signature = sign(env, private_key)
    assert verify(env, public_key)


def test_replay_nonce():
    # Generate RSA key pair for RS256 testing
    private_key, public_key = generate_rsa_key_pair()

    env = make_env("r")
    env.signature = sign(env, private_key)
    assert verify(env, public_key)
    assert not verify(env, public_key)  # Should fail on replay
