from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application configuration."""

    model_provider: Literal["openai", "anthropic", "vllm", "tgi", "stub"] = "stub"
    model_name: str = "gpt-4o"
    model_endpoint: str | None = None
    model_api_key: str | None = None

    # Telemetry settings (Logfire)
    telemetry_enabled: bool = True
    telemetry_service_name: str = "weaver-ai"
    telemetry_environment: str = "development"
    logfire_token: str | None = None
    logfire_send_to_cloud: bool = False
    telemetry_signing_enabled: bool = True
    telemetry_signing_key: str | None = None  # RSA private key for signing events
    telemetry_verification_key: str | None = None  # RSA public key for verification

    auth_mode: Literal["api_key", "jwt"] = "api_key"
    allowed_api_keys: list[str] = []
    jwt_public_key: str | None = None
    ratelimit_rps: int = 5
    ratelimit_burst: int = 10
    request_max_tokens: int = 4096
    request_timeout_ms: int = 25000
    request_max_tools: int = 3
    audit_path: str = "./audit.log"
    url_allowlist: list[str] = []
    url_denylist: list[str] = []
    pii_redact: bool = True
    a2a_signing_private_key_pem: str | None = None
    a2a_signing_public_key_pem: str | None = None
    mcp_server_public_keys: dict[str, str] = {}

    class Config:
        env_prefix = "WEAVER_"
