class LLMError(Exception):
    """Base class for everything the LLM layer raises."""


class TransientLLMError(LLMError):
    """Worth retrying: rate limit, 5xx, timeout, dropped connection."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class PermanentLLMError(LLMError):
    """Retrying the same request will not help (bad key, bad request, truncated output)."""


class LLMRefusalError(PermanentLLMError):
    """The provider declined to answer."""


class ProviderConfigError(PermanentLLMError):
    """Provider name unknown, key missing, or adapter not installed."""


class NoteValidationError(LLMError):
    """The model never produced a valid, grounded note within the allowed attempts."""

    def __init__(self, issues: list[str], last_text: str, attempts: int):
        super().__init__(
            f"No valid note after {attempts} attempt(s): " + "; ".join(issues[:3])
        )
        self.issues = issues
        self.last_text = last_text
        self.attempts = attempts
