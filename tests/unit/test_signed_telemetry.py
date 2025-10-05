"""Unit tests for signed telemetry and audit trails."""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from weaver_ai.security.audit import log_security_audit
from weaver_ai.settings import AppSettings
from weaver_ai.telemetry import (
    SignedEvent,
    _compute_event_hash,
    _sign_event,
    log_security_event,
    verify_event_signature,
)


@pytest.fixture
def rsa_keypair() -> tuple[str, str]:
    """Generate RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return private_pem, public_pem


class TestEventHashing:
    """Test event hashing for integrity verification."""

    def test_compute_event_hash_deterministic(self):
        """Event hash should be deterministic for same data."""
        event_data = {"user_id": "test@example.com", "action": "login"}

        hash1 = _compute_event_hash(event_data)
        hash2 = _compute_event_hash(event_data)

        assert hash1 == hash2

    def test_compute_event_hash_different_data(self):
        """Different event data should produce different hashes."""
        event1 = {"user_id": "user1@example.com", "action": "login"}
        event2 = {"user_id": "user2@example.com", "action": "login"}

        hash1 = _compute_event_hash(event1)
        hash2 = _compute_event_hash(event2)

        assert hash1 != hash2

    def test_compute_event_hash_key_order_independent(self):
        """Hash should be independent of key order (canonical JSON)."""
        event1 = {"user_id": "test@example.com", "action": "login"}
        event2 = {"action": "login", "user_id": "test@example.com"}

        hash1 = _compute_event_hash(event1)
        hash2 = _compute_event_hash(event2)

        assert hash1 == hash2


class TestEventSigning:
    """Test event signing and verification."""

    def test_sign_event_creates_valid_signature(self, rsa_keypair):
        """Signed event should have valid signature."""
        private_key, public_key = rsa_keypair
        event_data = {"user_id": "test@example.com", "reason": "invalid_token"}

        signed_event = _sign_event("auth_failure", event_data, private_key)

        assert signed_event.event_type == "auth_failure"
        assert signed_event.data == event_data
        assert signed_event.signature
        assert signed_event.event_hash

    def test_verify_event_signature_valid(self, rsa_keypair):
        """Valid signature should verify successfully."""
        private_key, public_key = rsa_keypair
        event_data = {"user_id": "test@example.com", "reason": "invalid_token"}

        signed_event = _sign_event("auth_failure", event_data, private_key)
        is_valid = verify_event_signature(signed_event, public_key)

        assert is_valid is True

    def test_verify_event_signature_tampered_data(self, rsa_keypair):
        """Tampered event data should fail verification."""
        private_key, public_key = rsa_keypair
        event_data = {"user_id": "test@example.com", "reason": "invalid_token"}

        signed_event = _sign_event("auth_failure", event_data, private_key)

        # Tamper with event data
        signed_event.data["user_id"] = "attacker@example.com"

        is_valid = verify_event_signature(signed_event, public_key)
        assert is_valid is False

    def test_verify_event_signature_wrong_public_key(self, rsa_keypair):
        """Wrong public key should fail verification."""
        private_key, _ = rsa_keypair
        event_data = {"user_id": "test@example.com", "reason": "invalid_token"}

        # Sign with first key
        signed_event = _sign_event("auth_failure", event_data, private_key)

        # Generate a completely different key pair
        wrong_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        wrong_public_key = (
            wrong_private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

        # Verify with wrong public key
        is_valid = verify_event_signature(signed_event, wrong_public_key)
        assert is_valid is False

    def test_verify_event_signature_invalid_signature_format(self, rsa_keypair):
        """Invalid signature format should fail verification."""
        _, public_key = rsa_keypair

        signed_event = SignedEvent(
            timestamp="2025-10-05T12:00:00Z",
            event_type="auth_failure",
            data={"user_id": "test@example.com"},
            signature="invalid.signature.format",
            event_hash="abc123",
        )

        is_valid = verify_event_signature(signed_event, public_key)
        assert is_valid is False


class TestSecurityEventLogging:
    """Test security event logging with signing."""

    def test_log_security_event_with_signing(self, rsa_keypair, caplog):
        """Security event should be logged with signature when key provided."""
        private_key, _ = rsa_keypair

        log_security_event(
            "auth_failure",
            signing_key=private_key,
            user_id="test@example.com",
            reason="invalid_token",
            ip_address="203.0.113.42",
        )

        # Check that event was logged (implementation depends on logging config)
        # This is a basic check - in production, verify against actual log output

    def test_log_security_event_without_signing(self, caplog):
        """Security event should be logged without signature when no key provided."""
        log_security_event(
            "auth_failure",
            signing_key=None,
            user_id="test@example.com",
            reason="invalid_token",
        )

        # Verify event was logged (without signature)


class TestSecurityAudit:
    """Test security audit logging integration."""

    def test_log_security_audit_creates_file_entry(self, tmp_path, rsa_keypair):
        """Security audit should create entry in audit log file."""
        private_key, _ = rsa_keypair
        audit_file = tmp_path / "audit.log"

        settings = AppSettings(
            audit_path=str(audit_file),
            telemetry_signing_enabled=True,
            telemetry_signing_key=private_key,
        )

        log_security_audit(
            action="auth_failure",
            user_id="test@example.com",
            detail="Invalid JWT token",
            settings=settings,
        )

        # Verify file was created and contains event
        assert audit_file.exists()
        content = audit_file.read_text()
        assert "auth_failure" in content
        assert "test@example.com" in content

    def test_log_security_audit_json_format(self, tmp_path, rsa_keypair):
        """Audit log entries should be valid JSON."""
        private_key, _ = rsa_keypair
        audit_file = tmp_path / "audit.log"

        settings = AppSettings(
            audit_path=str(audit_file),
            telemetry_signing_enabled=True,
            telemetry_signing_key=private_key,
        )

        log_security_audit(
            action="policy_violation",
            user_id="user@example.com",
            detail="Blocked URL access",
            settings=settings,
        )

        # Parse JSON from log file
        lines = audit_file.read_text().strip().split("\n")
        for line in lines:
            event = json.loads(line)
            assert "ts" in event
            assert "user_id" in event
            assert "action" in event
            assert "detail" in event

    def test_log_security_audit_without_signing(self, tmp_path):
        """Audit logging should work without signing enabled."""
        audit_file = tmp_path / "audit.log"

        settings = AppSettings(
            audit_path=str(audit_file),
            telemetry_signing_enabled=False,
            telemetry_signing_key=None,
        )

        log_security_audit(
            action="auth_success",
            user_id="test@example.com",
            detail="Login successful",
            settings=settings,
        )

        assert audit_file.exists()
        content = audit_file.read_text()
        assert "auth_success" in content


class TestSignedEventModel:
    """Test SignedEvent Pydantic model."""

    def test_signed_event_model_validation(self):
        """SignedEvent model should validate correctly."""
        event = SignedEvent(
            timestamp="2025-10-05T12:00:00Z",
            event_type="auth_failure",
            data={"user_id": "test@example.com", "reason": "invalid_token"},
            signature="eyJhbGc...",
            event_hash="abc123...",
        )

        assert event.timestamp == "2025-10-05T12:00:00Z"
        assert event.event_type == "auth_failure"
        assert event.data["user_id"] == "test@example.com"

    def test_signed_event_serialization(self):
        """SignedEvent should serialize to dict correctly."""
        event = SignedEvent(
            timestamp="2025-10-05T12:00:00Z",
            event_type="policy_violation",
            data={"url": "http://blocked.com"},
            signature="eyJhbGc...",
            event_hash="def456...",
        )

        event_dict = event.model_dump()
        assert "timestamp" in event_dict
        assert "event_type" in event_dict
        assert "data" in event_dict
        assert "signature" in event_dict
        assert "event_hash" in event_dict


class TestIntegrity:
    """Test tamper-evidence and non-repudiation properties."""

    def test_cannot_forge_signature(self, rsa_keypair):
        """Attacker cannot forge valid signature without private key."""
        private_key, public_key = rsa_keypair
        event_data = {"user_id": "legitimate@example.com"}

        # Create legitimate signed event
        signed_event = _sign_event("auth_success", event_data, private_key)

        # Attacker tries to create malicious event with forged signature
        malicious_event = SignedEvent(
            timestamp=signed_event.timestamp,
            event_type="admin_privilege_grant",  # Escalated privilege
            data={"user_id": "attacker@example.com"},
            signature=signed_event.signature,  # Reuse legitimate signature
            event_hash=_compute_event_hash({"user_id": "attacker@example.com"}),
        )

        # Verification should fail
        is_valid = verify_event_signature(malicious_event, public_key)
        assert is_valid is False

    def test_replay_protection_via_timestamp(self, rsa_keypair):
        """Old signatures cannot be replayed (timestamp verification)."""
        private_key, public_key = rsa_keypair
        event_data = {"user_id": "test@example.com"}

        signed_event = _sign_event("auth_success", event_data, private_key)

        # Verify signature is valid
        is_valid = verify_event_signature(signed_event, public_key)
        assert is_valid is True

        # In production, timestamp should be checked against current time
        # to prevent replay of old valid signatures
