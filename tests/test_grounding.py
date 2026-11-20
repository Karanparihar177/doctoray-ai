from app.schemas.consultation import ConsultationNote
from app.services.summarization.grounding import check_grounding, normalize
from tests.llm_helpers import TURNS, item, section, valid_note


def check(data):
    return check_grounding(ConsultationNote.model_validate(data), TURNS)


def test_valid_note_has_no_issues():
    assert check(valid_note()) == []


def test_normalize_ignores_case_and_punctuation():
    assert normalize("Hello,  World!") == "hello world"


def test_quote_must_be_in_cited_turn():
    data = valid_note()
    data["symptoms_discussed"] = section("stated", [item("Fever", 1, "high fever")])
    assert any("not in turn 1" in i for i in check(data))


def test_quote_matching_ignores_punctuation_and_case():
    data = valid_note()
    data["symptoms_discussed"] = section("stated", [item("Diarrhea", 1, "DIARRHEA, for the last three days")])
    assert check(data) == []


def test_unknown_turn_is_reported():
    data = valid_note()
    data["symptoms_discussed"] = section("stated", [item("Fever", 42, "high fever")])
    assert any("turn 42 does not exist" in i for i in check(data))


def test_short_quote_is_rejected():
    data = valid_note()
    data["symptoms_discussed"] = section("stated", [item("Diarrhea", 1, "had")])
    assert any("too short" in i for i in check(data))


def test_doctor_section_cannot_cite_patient_turn():
    data = valid_note()
    data["doctors_assessment"] = section("stated", [item("Gastroenteritis", 1, "diarrhea for the last")])
    assert any("spoken by the doctor" in i for i in check(data))


def test_patient_symptoms_cannot_cite_doctor_turn():
    data = valid_note()
    data["patient_reported_symptoms"] = section("stated", [item("Fluids", 2, "Drink plenty of fluids")])
    assert any("spoken by the patient" in i for i in check(data))


def test_speaker_roles_must_cover_all_speakers():
    data = valid_note()
    data["speaker_roles"] = data["speaker_roles"][:1]
    assert any("speaker_roles must list exactly" in i for i in check(data))
