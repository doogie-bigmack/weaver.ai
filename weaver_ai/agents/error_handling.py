"""Error handling strategies for agent execution."""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class ErrorStrategy(BaseModel, ABC):
    """Base class for error handling strategies."""

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with error handling.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or raises exception
        """
        pass

    def should_fail_workflow(self) -> bool:
        """Whether errors should fail the entire workflow.

        Returns:
            True if workflow should fail on error
        """
        return False


class FailFast(ErrorStrategy):
    """Fail immediately on any error."""

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with no error handling - fail fast.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Any exception from the function
        """
        return await func(*args, **kwargs)

    def should_fail_workflow(self) -> bool:
        """Fail-fast always fails the workflow."""
        return True


class RetryWithBackoff(ErrorStrategy):
    """Retry with configurable backoff strategy."""

    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff: str = "exponential"  # exponential, linear, fixed
    jitter: bool = True
    retry_on: list[type[Exception]] = Field(default_factory=lambda: [Exception])

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Check if we should retry this exception type
                should_retry = any(
                    isinstance(e, exc_type) for exc_type in self.retry_on
                )

                if not should_retry or attempt == self.max_retries:
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt)

                # Add jitter if enabled
                if self.jitter:
                    delay = delay * (0.5 + random.random())

                # Wait before retry
                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.

        Args:
            attempt: Retry attempt number (0-based)

        Returns:
            Delay in seconds
        """
        if self.backoff == "exponential":
            delay = self.initial_delay * (2**attempt)
        elif self.backoff == "linear":
            delay = self.initial_delay * (attempt + 1)
        else:  # fixed
            delay = self.initial_delay

        return min(delay, self.max_delay)


class SkipOnError(ErrorStrategy):
    """Skip agent on error and continue workflow."""

    log_errors: bool = True
    return_default: Any = None

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute and return None on error.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or default value on error
        """
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if self.log_errors:
                # In production, this would log to proper logging system
                print(f"Skipping agent due to error: {e}")
            return self.return_default


class CircuitBreaker(ErrorStrategy):
    """Circuit breaker pattern for handling repeated failures."""

    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_requests: int = 1

    # Runtime state (not serialized)
    failure_count: int = Field(0, exclude=True)
    last_failure_time: Optional[datetime] = Field(None, exclude=True)
    state: str = Field("closed", exclude=True)  # closed, open, half_open
    half_open_successes: int = Field(0, exclude=True)

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with circuit breaker logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError if circuit is open
            Original exception if function fails
        """
        # Check circuit state
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.half_open_successes = 0
            else:
                raise CircuitOpenError(
                    f"Circuit breaker is open (failures: {self.failure_count})"
                )

        try:
            result = await func(*args, **kwargs)

            # Success - update circuit state
            if self.state == "half_open":
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_requests:
                    self._reset()
            elif self.state == "closed":
                # Reset failure count on success
                self.failure_count = 0

            return result

        except Exception as e:
            self._record_failure()

            # Check if we should open the circuit
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.last_failure_time = datetime.now(UTC)

            raise

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit.

        Returns:
            True if recovery timeout has passed
        """
        if not self.last_failure_time:
            return True

        time_since_failure = datetime.now(UTC) - self.last_failure_time
        return time_since_failure > timedelta(seconds=self.recovery_timeout)

    def _record_failure(self):
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self.state == "half_open":
            # Failed in half-open state, go back to open
            self.state = "open"

    def _reset(self):
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        self.half_open_successes = 0

    def should_fail_workflow(self) -> bool:
        """Circuit breaker fails workflow when open."""
        return self.state == "open"


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class AdaptiveRetry(ErrorStrategy):
    """Adaptive retry strategy that adjusts based on success rate."""

    initial_retries: int = 3
    min_retries: int = 1
    max_retries: int = 10
    success_rate_threshold: float = 0.8
    adjustment_window: int = 10  # Number of executions to consider

    # Runtime state
    current_retries: int = Field(3, exclude=True)
    execution_history: list[bool] = Field(default_factory=list, exclude=True)

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with adaptive retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        succeeded = False

        for attempt in range(self.current_retries + 1):
            try:
                result = await func(*args, **kwargs)
                succeeded = True
                self._record_execution(True)
                self._adjust_retries()
                return result

            except Exception as e:
                last_exception = e

                if attempt == self.current_retries:
                    self._record_execution(False)
                    self._adjust_retries()
                    raise

                # Exponential backoff with jitter
                delay = (2**attempt) * (0.5 + random.random())
                await asyncio.sleep(min(delay, 30))

        if last_exception:
            raise last_exception

    def _record_execution(self, success: bool):
        """Record execution result.

        Args:
            success: Whether execution succeeded
        """
        self.execution_history.append(success)

        # Keep only recent history
        if len(self.execution_history) > self.adjustment_window:
            self.execution_history.pop(0)

    def _adjust_retries(self):
        """Adjust retry count based on success rate."""
        if len(self.execution_history) < self.adjustment_window:
            return

        success_rate = sum(self.execution_history) / len(self.execution_history)

        if success_rate > self.success_rate_threshold:
            # High success rate - decrease retries
            self.current_retries = max(self.min_retries, self.current_retries - 1)
        elif success_rate < 0.5:
            # Low success rate - increase retries
            self.current_retries = min(self.max_retries, self.current_retries + 1)


class TimeoutStrategy(ErrorStrategy):
    """Execute with timeout."""

    timeout_seconds: float = 30.0
    fallback_value: Any = None

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with timeout.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback value on timeout

        Raises:
            asyncio.TimeoutError if no fallback value set
        """
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            if self.fallback_value is not None:
                return self.fallback_value
            raise


class CompositeStrategy(ErrorStrategy):
    """Combine multiple error strategies."""

    strategies: list[ErrorStrategy] = Field(default_factory=list)

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with all strategies in order.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """

        # Build nested execution
        async def wrapped(*a, **kw):
            return await func(*a, **kw)

        current = wrapped

        # Wrap with each strategy in reverse order
        for strategy in reversed(self.strategies):
            prev = current

            async def new_wrapped(*a, **kw):
                return await strategy.execute(prev, *a, **kw)

            current = new_wrapped

        return await current(*args, **kwargs)

    def should_fail_workflow(self) -> bool:
        """Composite fails if any strategy would fail."""
        return any(s.should_fail_workflow() for s in self.strategies)
