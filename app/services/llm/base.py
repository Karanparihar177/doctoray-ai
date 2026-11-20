"""Provider-independent LLM contract.

Adapters (Anthropic, OpenAI, Gemini, ...) implement `LLMProvider`. They send
the request, ask the vendor for JSON matching `json_schema` where supported,
map vendor errors to `app.services.llm.errors`, and return the raw JSON text.
Parsing and validation happen once, in the caller, so behaviour is identical
whichever vendor is plugged in.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    system: str
    messages: list[Message]
    json_schema: dict
    schema_name: str
    max_output_tokens: int = 4096


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    truncated: bool = False          # hit the output-token limit
    request_id: str | None = None


class LLMProvider(Protocol):
    name: str    # e.g. "anthropic"
    model: str   # e.g. the model id sent to the vendor

    def generate(self, request: LLMRequest) -> LLMResponse:
        """One model call. Raise TransientLLMError, PermanentLLMError or LLMRefusalError."""
        ...
