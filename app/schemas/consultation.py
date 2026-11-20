"""Data shapes for consultation-note generation.

`ConsultationNote` is what the LLM must return. It is kept free of numeric
bounds and defaults so that every provider's structured-output mode accepts
it; the real rules live in the validators here and in
`app.services.summarization.grounding`.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class Role(StrEnum):
    doctor = "doctor"
    patient = "patient"
    other = "other"
    unknown = "unknown"


class Confidence(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class SectionStatus(StrEnum):
    stated = "stated"          # said in the consultation
    not_stated = "not_stated"  # nothing about it was said
    unclear = "unclear"        # mentioned but ambiguous; needs review


class TranscriptTurn(BaseModel):
    """One uninterrupted stretch of speech by one speaker (input, not LLM output)."""

    index: int
    speaker: int
    start: float | None = None
    end: float | None = None
    text: str


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    turn: int    # TranscriptTurn.index
    quote: str   # verbatim words from that turn


class NoteItem(_Strict):
    text: str
    evidence: list[Evidence]

    @model_validator(mode="after")
    def _needs_text_and_evidence(self):
        if not self.text.strip():
            raise ValueError("item text is empty")
        if not self.evidence:
            raise ValueError("item has no evidence")
        return self


class NoteSection(_Strict):
    status: SectionStatus
    items: list[NoteItem]
    remark: str  # why it is unclear; empty string otherwise

    @model_validator(mode="after")
    def _status_matches_content(self):
        if self.status is SectionStatus.stated and not self.items:
            raise ValueError("status 'stated' needs at least one item")
        if self.status is SectionStatus.not_stated and self.items:
            raise ValueError("status 'not_stated' must have no items")
        if self.status is SectionStatus.unclear and not self.remark.strip():
            raise ValueError("status 'unclear' needs a remark explaining why")
        return self


class SpeakerRole(_Strict):
    speaker: int
    role: Role
    confidence: Confidence
    reason: str


class ConsultationNote(_Strict):
    speaker_roles: list[SpeakerRole]
    summary: str
    reason_for_visit: NoteSection
    patient_reported_symptoms: NoteSection
    symptoms_discussed: NoteSection
    relevant_observations: NoteSection
    doctors_assessment: NoteSection
    treatment_or_medication: NoteSection
    follow_up_instructions: NoteSection
    pending_actions_remarks: NoteSection
    warnings: list[str]

    @model_validator(mode="after")
    def _roles_are_consistent(self):
        speakers = [r.speaker for r in self.speaker_roles]
        if len(speakers) != len(set(speakers)):
            raise ValueError("speaker_roles lists a speaker more than once")
        for role in (Role.doctor, Role.patient):
            if sum(r.role is role for r in self.speaker_roles) > 1:
                raise ValueError(f"more than one speaker is labelled {role.value}")
        if not self.summary.strip():
            raise ValueError("summary is empty")
        return self

    def role_of(self, speaker: int) -> Role:
        for r in self.speaker_roles:
            if r.speaker == speaker:
                return r.role
        return Role.unknown


SECTION_FIELDS = (
    "reason_for_visit",
    "patient_reported_symptoms",
    "symptoms_discussed",
    "relevant_observations",
    "doctors_assessment",
    "treatment_or_medication",
    "follow_up_instructions",
    "pending_actions_remarks",
)

# Evidence for these must come from a turn spoken by the labelled role.
DOCTOR_ONLY_SECTIONS = (
    "doctors_assessment",
    "treatment_or_medication",
    "follow_up_instructions",
)
PATIENT_ONLY_SECTIONS = ("patient_reported_symptoms",)
