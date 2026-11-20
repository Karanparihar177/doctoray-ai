import pytest

from app.services.llm.errors import PermanentLLMError, TransientLLMError
from app.services.llm.retry import RetryPolicy, call_with_retry


class Flaky:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def run(fn, policy=RetryPolicy(), now=None):
    sleeps = []
    clock = now or (lambda: 0.0)
    result = call_with_retry(fn, policy, sleep=sleeps.append, rng=lambda: 1.0, clock=clock)
    return result, sleeps


def test_returns_first_success_without_sleeping():
    fn = Flaky("ok")
    assert run(fn) == ("ok", [])


def test_retries_transient_errors_with_exponential_backoff():
    fn = Flaky(TransientLLMError("a"), TransientLLMError("b"), "ok")
    result, sleeps = run(fn)
    assert result == "ok"
    assert fn.calls == 3
    assert sleeps == [1.0, 2.0]  # rng=1.0 -> full ceiling


def test_backoff_is_capped():
    policy = RetryPolicy(max_attempts=6, base_delay=10, max_delay=15, deadline=1000)
    fn = Flaky(*[TransientLLMError("x")] * 5, "ok")
    _, sleeps = run(fn, policy)
    assert max(sleeps) == 15


def test_retry_after_overrides_backoff():
    fn = Flaky(TransientLLMError("slow down", retry_after=7), "ok")
    _, sleeps = run(fn)
    assert sleeps == [7]


def test_gives_up_after_max_attempts():
    fn = Flaky(*[TransientLLMError("x")] * 4)
    with pytest.raises(TransientLLMError):
        run(fn, RetryPolicy(max_attempts=4))
    assert fn.calls == 4


def test_permanent_errors_are_not_retried():
    fn = Flaky(PermanentLLMError("bad key"), "ok")
    with pytest.raises(PermanentLLMError):
        run(fn)
    assert fn.calls == 1


def test_stops_when_deadline_would_be_exceeded():
    fn = Flaky(TransientLLMError("x", retry_after=30), "ok")
    with pytest.raises(TransientLLMError):
        run(fn, RetryPolicy(deadline=10))
    assert fn.calls == 1
