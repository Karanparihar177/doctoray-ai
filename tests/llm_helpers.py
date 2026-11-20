"""Shared test doubles and a valid note, so no test calls a real LLM."""

import json

from app.schemas.consultation import TranscriptTurn
from app.services.llm.base import LLMRequest, LLMResponse, Usage

TURNS = [
    TranscriptTurn(index=0, speaker=0, start=0, end=3, text="Good morning. How can I help you today?"),
    TranscriptTurn(index=1, speaker=1, start=3, end=9, text="I've had diarrhea for the last three days."),
    TranscriptTurn(index=2, speaker=0, start=9, end=14, text="Drink plenty of fluids and come back if it gets worse."),
]


def section(status="not_stated", items=None, remark=""):
    return {"status": status, "items": items or [], "remark": remark}


def item(text, turn, quote):
    return {"text": text, "evidence": [{"turn": turn, "quote": quote}]}


def valid_note() -> dict:
    return {
        "speaker_roles": [
            {"speaker": 0, "role": "doctor", "confidence": "high", "reason": "Opens the consultation"},
            {"speaker": 1, "role": "patient", "confidence": "high", "reason": "Describes symptoms"},
        ],
        "summary": "Patient reports three days of diarrhea. Doctor advised fluids.",
        "reason_for_visit": section("stated", [item("Diarrhea for three days", 1, "diarrhea for the last three days")]),
        "patient_reported_symptoms": section("stated", [item("Diarrhea", 1, "had diarrhea")]),
        "symptoms_discussed": section(),
        "relevant_observations": section(),
        "doctors_assessment": section(),
        "treatment_or_medication": section("stated", [item("Drink plenty of fluids", 2, "Drink plenty of fluids")]),
        "follow_up_instructions": section("stated", [item("Return if worse", 2, "come back if it gets worse")]),
        "pending_actions_remarks": section(),
        "warnings": [],
    }


class ScriptedProvider:
    """Returns queued responses; an Exception in the queue is raised instead."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, LLMResponse):
            return out
        text = out if isinstance(out, str) else json.dumps(out)
        return LLMResponse(text=text, usage=Usage(100, 50), model=self.model, request_id=f"req-{len(self.requests)}")
