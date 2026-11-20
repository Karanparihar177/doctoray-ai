import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas.consultation import ConsultationNote, TranscriptTurn
from app.services.llm.base import LLMProvider, LLMRequest, LLMResponse, Message, Usage
from app.services.llm.errors import NoteValidationError, PermanentLLMError
from app.services.llm.retry import RetryPolicy, call_with_retry
from app.services.summarization.grounding import check_grounding
from app.services.summarization.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_repair_message,
    build_user_message,
)


@dataclass(frozen=True)
class GenerationMeta:
    provider: str
    model: str
    prompt_version: str
    attempts: int              # model calls that returned output (1 = no repair needed)
    usage: Usage
    request_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedNote:
    note: ConsultationNote
    meta: GenerationMeta


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text)


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in e['loc']) or 'root'}: {e['msg']}"
        for e in exc.errors()
    ]


def generate_consultation_note(
    turns: list[TranscriptTurn],
    provider: LLMProvider,
    *,
    retry: RetryPolicy = RetryPolicy(),
    max_repairs: int = 2,
    max_output_tokens: int = 4096,
    sleep: Callable[[float], None] = time.sleep,
) -> GeneratedNote:
    """Turn a speaker-labelled transcript into a validated, grounded draft note.

    Two kinds of retry, kept separate:
    - transient provider errors are retried with backoff (`retry`);
    - output that fails the schema or grounding checks is sent back to the
      model with the list of problems, up to `max_repairs` times.
    The result is always a draft for the doctor. If no valid note is produced,
    NoteValidationError carries the problems and the last raw output.
    """
    if not turns:
        raise ValueError("Transcript has no turns")

    messages = [Message("user", build_user_message(turns))]
    usage = Usage()
    request_ids: list[str] = []
    issues: list[str] = []
    last_text = ""
    model = provider.model

    for attempt in range(1, max_repairs + 2):
        request = LLMRequest(
            system=SYSTEM_PROMPT,
            messages=list(messages),
            json_schema=ConsultationNote.model_json_schema(),
            schema_name="consultation_note",
            max_output_tokens=max_output_tokens,
        )
        response: LLMResponse = call_with_retry(
            lambda: provider.generate(request), retry, sleep=sleep
        )

        usage = usage + response.usage
        model = response.model or model
        if response.request_id:
            request_ids.append(response.request_id)
        if response.truncated:
            raise PermanentLLMError(
                "Output hit the token limit; raise max_output_tokens or shorten the transcript"
            )

        last_text = response.text
        try:
            note = ConsultationNote.model_validate_json(_strip_fences(response.text))
        except ValidationError as exc:
            issues = _format_pydantic_errors(exc)
        else:
            issues = check_grounding(note, turns)
            if not issues:
                return GeneratedNote(
                    note=note,
                    meta=GenerationMeta(
                        provider=provider.name,
                        model=model,
                        prompt_version=PROMPT_VERSION,
                        attempts=attempt,
                        usage=usage,
                        request_ids=request_ids,
                    ),
                )

        messages.append(Message("assistant", response.text))
        messages.append(Message("user", build_repair_message(issues)))

    raise NoteValidationError(issues, last_text, max_repairs + 1)
