import json

import pytest

from app.services.llm.base import LLMResponse, Usage
from app.services.llm.errors import NoteValidationError, PermanentLLMError, TransientLLMError
from app.services.llm.retry import RetryPolicy
from app.services.summarization.service import generate_consultation_note
from tests.llm_helpers import TURNS, ScriptedProvider, item, section, valid_note


def generate(provider, **kwargs):
    return generate_consultation_note(TURNS, provider, sleep=lambda s: None, **kwargs)


def test_valid_output_is_returned_with_metadata():
    provider = ScriptedProvider(valid_note())
    result = generate(provider)

    assert result.note.summary.startswith("Patient reports")
    assert result.meta.attempts == 1
    assert result.meta.provider == "scripted"
    assert result.meta.prompt_version == "note-v1"
    assert result.meta.usage == Usage(100, 50)
    request = provider.requests[0]
    assert "[1] Speaker 1: I've had diarrhea" in request.messages[0].content
    assert request.json_schema["type"] == "object"


def test_code_fences_are_tolerated():
    provider = ScriptedProvider("```json\n" + json.dumps(valid_note()) + "\n```")
    assert generate(provider).meta.attempts == 1


def test_invalid_json_is_repaired():
    provider = ScriptedProvider("not json at all", valid_note())
    result = generate(provider)

    assert result.meta.attempts == 2
    assert result.meta.usage == Usage(200, 100)
    repair = provider.requests[1].messages
    assert [m.role for m in repair] == ["user", "assistant", "user"]
    assert "problems" in repair[-1].content


def test_ungrounded_quote_is_sent_back_for_repair():
    bad = valid_note()
    bad["symptoms_discussed"] = section("stated", [item("Fever", 1, "high fever")])
    provider = ScriptedProvider(bad, valid_note())

    result = generate(provider)

    assert result.meta.attempts == 2
    assert "not in turn 1" in provider.requests[1].messages[-1].content


def test_gives_up_after_max_repairs_and_reports_issues():
    provider = ScriptedProvider("bad", "bad", "bad")

    with pytest.raises(NoteValidationError) as caught:
        generate(provider, max_repairs=2)

    assert caught.value.attempts == 3
    assert caught.value.last_text == "bad"
    assert len(provider.requests) == 3


def test_transient_errors_are_retried_without_using_repairs():
    provider = ScriptedProvider(TransientLLMError("429"), valid_note())

    result = generate(provider, retry=RetryPolicy(max_attempts=3))

    assert result.meta.attempts == 1
    assert len(provider.requests) == 2


def test_truncated_output_fails_fast():
    provider = ScriptedProvider(LLMResponse(text='{"speaker_roles": [', truncated=True))

    with pytest.raises(PermanentLLMError, match="token limit"):
        generate(provider)
    assert len(provider.requests) == 1


def test_empty_transcript_is_rejected():
    with pytest.raises(ValueError):
        generate_consultation_note([], ScriptedProvider())
