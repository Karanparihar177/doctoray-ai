import pytest
from pydantic import ValidationError

from app.schemas.consultation import ConsultationNote, NoteSection
from tests.llm_helpers import item, section, valid_note


def test_valid_note_parses():
    note = ConsultationNote.model_validate(valid_note())
    assert note.role_of(0).value == "doctor"
    assert note.role_of(99).value == "unknown"


def test_stated_section_needs_items():
    with pytest.raises(ValidationError, match="needs at least one item"):
        NoteSection.model_validate(section("stated"))


def test_not_stated_section_must_be_empty():
    with pytest.raises(ValidationError, match="must have no items"):
        NoteSection.model_validate(section("not_stated", [item("x", 0, "xxxx")]))


def test_unclear_section_needs_remark():
    with pytest.raises(ValidationError, match="needs a remark"):
        NoteSection.model_validate(section("unclear"))


def test_item_needs_evidence():
    data = section("stated", [{"text": "Cough", "evidence": []}])
    with pytest.raises(ValidationError, match="no evidence"):
        NoteSection.model_validate(data)


def test_unknown_fields_are_rejected():
    data = valid_note()
    data["diagnosis"] = "gastroenteritis"
    with pytest.raises(ValidationError):
        ConsultationNote.model_validate(data)


def test_two_doctors_rejected():
    data = valid_note()
    data["speaker_roles"][1]["role"] = "doctor"
    with pytest.raises(ValidationError, match="more than one speaker"):
        ConsultationNote.model_validate(data)


def test_json_schema_has_no_numeric_bounds():
    """Keeps the schema acceptable to every provider's structured-output mode."""
    text = str(ConsultationNote.model_json_schema())
    for keyword in ("minItems", "minLength", "maxLength", "minimum", "maximum"):
        assert keyword not in text
