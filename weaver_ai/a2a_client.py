"""Client for sending A2A messages to remote agents over HTTP."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from pydantic import BaseModel

from weaver_ai.a2a import A2AEnvelope, Budget, Capability, sign, verify


class A2AResponse(BaseModel):
    """Response from A2A message."""

    success: bool
    data: dict | None = None
    error: str | None = None
    execution_time_ms: float = 0.0


class A2AClient:
    """Client for sending A2A messages to remote agents.

    This client handles:
    - Creating signed A2A envelopes
    - Sending HTTP requests to remote agents
    - Verifying response signatures
    - Error handling and retries
    """

    def __init__(
        self,
        sender_id: str,
        private_key: str,
        public_key: str,
        timeout: float = 30.0,
    ):
        """Initialize A2A client.

        Args:
            sender_id: Your agent ID
            private_key: Your RSA private key (PEM format)
            public_key: Your RSA public key (PEM format)
            timeout: HTTP request timeout in seconds
        """
        self.sender_id = sender_id
        self.private_key = private_key
        self.public_key = public_key
        self.timeout = timeout
        self.remote_public_keys: dict[str, str] = {}

    def register_remote_agent(self, agent_id: str, public_key: str):
        """Register a remote agent's public key for signature verification.

        Args:
            agent_id: Remote agent ID
            public_key: Remote agent's RSA public key (PEM format)
        """
        self.remote_public_keys[agent_id] = public_key

    async def send_message(
        self,
        endpoint: str,
        receiver_id: str,
        capability: str,
        payload: dict,
        budget: Budget | None = None,
        timeout: float | None = None,
    ) -> A2AResponse:
        """Send A2A message to remote agent.

        Args:
            endpoint: Remote agent HTTP endpoint (e.g., https://agent.com)
            receiver_id: Remote agent ID
            capability: Capability being requested
            payload: Message payload
            budget: Optional budget constraints
            timeout: Optional timeout override

        Returns:
            A2AResponse with result or error

        Example:
            >>> client = A2AClient("my-agent", private_key, public_key)
            >>> result = await client.send_message(
            ...     endpoint="https://translator.com",
            ...     receiver_id="translator-agent",
            ...     capability="translation:en-es",
            ...     payload={"text": "Hello"},
            ...     budget=Budget(tokens=1000, time_ms=5000, tool_calls=1)
            ... )
            >>> print(result.data["translated"])
        """
        start_time = time.time()

        try:
            # Create A2A envelope
            envelope = self._create_envelope(
                receiver_id=receiver_id,
                capability=capability,
                payload=payload,
                budget=budget,
            )

            # Sign envelope
            envelope.signature = sign(envelope, self.private_key)

            # Send HTTP request
            url = f"{endpoint.rstrip('/')}/a2a/message"
            timeout_seconds = timeout or self.timeout

            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    url,
                    json=envelope.model_dump(mode="json"),
                    headers={"Content-Type": "application/json"},
                )

                response.raise_for_status()

            # Parse response
            response_data = response.json()

            # Verify response if it's an A2A envelope
            if "signature" in response_data:
                response_envelope = A2AEnvelope.model_validate(response_data)

                # Verify response signature if we have the public key
                if receiver_id in self.remote_public_keys:
                    if not verify(
                        response_envelope, self.remote_public_keys[receiver_id]
                    ):
                        return A2AResponse(
                            success=False,
                            error="Invalid response signature",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )

                # Extract payload from envelope
                result_data = response_envelope.payload
            else:
                # Direct response (not wrapped in envelope)
                result_data = response_data

            # If response_data looks like a Result dict (has 'success' and 'data' fields),
            # extract the actual data from within the Result wrapper
            if (
                isinstance(result_data, dict)
                and "success" in result_data
                and "data" in result_data
            ):
                # This is a Result object dict, extract the actual data
                actual_data = result_data.get("data")
            else:
                actual_data = result_data

            execution_time = (time.time() - start_time) * 1000

            return A2AResponse(
                success=True, data=actual_data, execution_time_ms=execution_time
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            return A2AResponse(
                success=False,
                error=error_msg,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except httpx.TimeoutException:
            return A2AResponse(
                success=False,
                error=f"Request timeout after {timeout_seconds}s",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return A2AResponse(
                success=False,
                error=f"Request failed: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _create_envelope(
        self,
        receiver_id: str,
        capability: str,
        payload: dict,
        budget: Budget | None,
    ) -> A2AEnvelope:
        """Create A2A envelope for message.

        Args:
            receiver_id: Remote agent ID
            capability: Requested capability
            payload: Message payload
            budget: Budget constraints

        Returns:
            Unsigned A2AEnvelope
        """
        # Default budget if not provided
        if budget is None:
            budget = Budget(
                tokens=4096,  # Default token limit
                time_ms=30000,  # 30 second timeout
                tool_calls=5,  # Max 5 tool calls
            )

        # Create envelope
        return A2AEnvelope(
            request_id=uuid4().hex,
            sender_id=self.sender_id,
            receiver_id=receiver_id,
            created_at=datetime.now(UTC),
            nonce=uuid4().hex,
            capabilities=[
                Capability(name=capability, version="1.0.0", scopes=["execute"])
            ],
            budget=budget,
            payload=payload,
        )

    async def get_agent_card(self, endpoint: str) -> dict | None:
        """Fetch agent card from remote agent.

        Args:
            endpoint: Remote agent HTTP endpoint

        Returns:
            Agent card dictionary or None if failed
        """
        try:
            url = f"{endpoint.rstrip('/')}/a2a/card"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            print(f"Failed to fetch agent card: {e}")
            return None
