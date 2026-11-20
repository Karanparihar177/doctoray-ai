from app.schemas.consultation import TranscriptTurn

PROMPT_VERSION = "note-v1"

SYSTEM_PROMPT = """\
You write structured notes of a recorded doctor-patient consultation, from a \
transcript, for the doctor to review. You assist the doctor. You never decide \
anything clinically.

Input: numbered turns such as "[12] Speaker 1: text". Speakers are only numbers. \
Work out from the conversation which speaker is the doctor and which is the \
patient, and fill speaker_roles for every speaker number that appears. If you \
cannot tell, use role "unknown" and confidence "low".

Rules:
- Use only what is said in the transcript. Never invent or infer diagnoses, \
medication, doses, tests, assessments or instructions.
- Patient-reported information and the doctor's statements are different. Put \
a symptom the patient reports under patient_reported_symptoms. Put an \
assessment, treatment, medication or follow-up only if the doctor said it, and \
only cite doctor turns for those.
- Every item needs evidence: the turn number and a short quote copied exactly \
from that turn (a few words are enough). Cite one turn per quote.
- If a section was not discussed, set status "not_stated" with no items and an \
empty remark. If something was mentioned but is ambiguous, contradictory or \
possibly mis-transcribed, set status "unclear" and explain in remark.
- Transcription errors are possible. Do not guess what an unclear word meant.
- Write in English, in short factual phrases. summary is 2-4 sentences. Use \
warnings for anything the doctor should double-check; otherwise an empty list.
- Return only the JSON object that matches the schema."""


def format_transcript(turns: list[TranscriptTurn]) -> str:
    return "\n".join(f"[{t.index}] Speaker {t.speaker}: {t.text}" for t in turns)


def build_user_message(turns: list[TranscriptTurn]) -> str:
    return f"Transcript:\n\n{format_transcript(turns)}"


def build_repair_message(issues: list[str]) -> str:
    listed = "\n".join(f"- {i}" for i in issues)
    return (
        "Your previous JSON has these problems:\n"
        f"{listed}\n\n"
        "Return the complete corrected JSON. Fix only what is listed. Do not add "
        "information that is not in the transcript."
    )
