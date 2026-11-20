import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from app.services.llm.errors import TransientLLMError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Retries for transient provider failures only (not for invalid output)."""

    max_attempts: int = 4        # total calls, including the first
    base_delay: float = 1.0      # seconds; doubles each retry
    max_delay: float = 30.0
    deadline: float = 120.0      # give up once this much time has passed


def call_with_retry(
    fn: Callable[[], T],
    policy: RetryPolicy = RetryPolicy(),
    *,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
    clock: Callable[[], float] = time.monotonic,
) -> T:
    """Call `fn`, retrying TransientLLMError with exponential backoff and jitter.

    Any other exception, including PermanentLLMError, propagates immediately.
    A server-supplied `retry_after` overrides the computed delay.
    """
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except TransientLLMError as exc:
            if attempt >= policy.max_attempts:
                raise
            if exc.retry_after is not None:
                delay = min(exc.retry_after, policy.max_delay)
            else:
                ceiling = min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1))
                delay = rng() * ceiling  # full jitter
            if clock() - started + delay > policy.deadline:
                raise
            sleep(delay)
