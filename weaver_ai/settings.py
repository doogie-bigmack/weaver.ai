from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # RSA private key for signing events
    telemetry_signing_key: str | None = None
    # RSA public key for verification
    telemetry_verification_key: str | None = None

    auth_mode: Literal["api_key", "jwt"] = "api_key"
    allowed_api_keys: str | list[str] = ""
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

    # SailPoint Integration Settings
    sailpoint_base_url: str = "http://localhost:8080/identityiq"
    sailpoint_mcp_host: str = "localhost"
    sailpoint_mcp_port: int = 3000

    # Feature Flags for Security
    enable_python_eval: bool = False  # SECURITY: Disabled by default

    # CORS Configuration
    cors_enabled: bool = True
    cors_origins: list[str] = []  # Empty list = allow no origins (secure default)
    cors_allow_credentials: bool = False
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]
    cors_max_age: int = 600  # Preflight cache in seconds

    # Security Headers Configuration
    security_headers_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year
    csp_report_uri: str | None = None

    # CSRF Configuration
    csrf_enabled: bool = True
    csrf_secret_key: str | None = None
    csrf_cookie_secure: bool = True
    csrf_exclude_paths: list[str] = []

    def model_post_init(self, __context) -> None:
        """Load keys from files if they appear to be file paths."""
        from pathlib import Path

        # Load A2A private key from file if it looks like a path
        if self.a2a_signing_private_key_pem and (
            self.a2a_signing_private_key_pem.startswith("/")
            or self.a2a_signing_private_key_pem.startswith("./")
        ):
            key_path = Path(self.a2a_signing_private_key_pem)
            if key_path.exists():
                self.a2a_signing_private_key_pem = key_path.read_text()

        # Load A2A public key from file if it looks like a path
        if self.a2a_signing_public_key_pem and (
            self.a2a_signing_public_key_pem.startswith("/")
            or self.a2a_signing_public_key_pem.startswith("./")
        ):
            key_path = Path(self.a2a_signing_public_key_pem)
            if key_path.exists():
                self.a2a_signing_public_key_pem = key_path.read_text()

    model_config = SettingsConfigDict(
        env_prefix="WEAVER_",
        env_parse_none_str="none",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_api_keys", mode="before")
    @classmethod
    def parse_allowed_api_keys(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            # Handle comma-separated values
            return [k.strip() for k in v.split(",") if k.strip()]
        if isinstance(v, list):
            return v
        return []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            # Handle comma-separated values or JSON array
            if v.startswith("["):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return []

    @field_validator("csrf_exclude_paths", mode="before")
    @classmethod
    def parse_csrf_exclude_paths(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            # Handle comma-separated values or JSON array
            if v.startswith("["):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return []
            return [path.strip() for path in v.split(",") if path.strip()]
        if isinstance(v, list):
            return v
        return []

    @field_validator("mcp_server_public_keys", mode="before")
    @classmethod
    def parse_mcp_server_public_keys(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            # Handle JSON string
            import json

            try:
                parsed = json.loads(v)
                # Convert literal \n in keys to actual newlines
                if isinstance(parsed, dict):
                    return {
                        k: v.replace("\\n", "\n") if isinstance(v, str) else v
                        for k, v in parsed.items()
                    }
                return parsed
            except json.JSONDecodeError:
                return {}
        if isinstance(v, dict):
            # Convert literal \n in keys to actual newlines
            return {
                k: v.replace("\\n", "\n") if isinstance(v, str) else v
                for k, v in v.items()
            }
        return {}
