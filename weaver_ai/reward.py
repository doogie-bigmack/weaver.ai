from __future__ import annotations

from .verifier import VerificationResult


def compute_reward(
    verification: VerificationResult,
    latency_ms: float,
    *,
    max_latency_ms: float = 2000.0,
) -> float:
    base = 1.0 if verification.success else 0.0
    latency_penalty = max(0.0, (latency_ms - max_latency_ms) / max_latency_ms)
    return max(0.0, base - latency_penalty)
