from __future__ import annotations

from datetime import datetime, timezone

from weaver_ai.a2a import A2AEnvelope, Budget, Capability, sign, verify


def make_env(nonce: str) -> A2AEnvelope:
    return A2AEnvelope(
        request_id="1",
        sender_id="a",
        receiver_id="b",
        created_at=datetime.now(timezone.utc),
        nonce=nonce,
        capabilities=[Capability(name="x", version="1", scopes=[])],
        budget=Budget(tokens=1, time_ms=1, tool_calls=1),
        payload={"hello": "world"},
    )


def test_sign_verify():
    env = make_env("n")
    env.signature = sign(env, "k")
    assert verify(env, "k")


def test_replay_nonce():
    env = make_env("r")
    env.signature = sign(env, "k")
    assert verify(env, "k")
    assert not verify(env, "k")
