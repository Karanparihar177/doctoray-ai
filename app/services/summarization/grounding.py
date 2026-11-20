"""Checks that need the transcript, which a schema alone cannot do.

They catch the failure the plan worries about most: content that is not in
the conversation, or that is attributed to the wrong speaker.
"""

import re

from app.schemas.consultation import (
    DOCTOR_ONLY_SECTIONS,
    PATIENT_ONLY_SECTIONS,
    SECTION_FIELDS,
    ConsultationNote,
    Role,
    TranscriptTurn,
)

MIN_QUOTE_CHARS = 4


def normalize(text: str) -> str:
    """Lower-case, drop punctuation, collapse whitespace (works for Arabic too)."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def check_grounding(note: ConsultationNote, turns: list[TranscriptTurn]) -> list[str]:
    """Return human-readable problems; an empty list means the note is grounded."""
    issues: list[str] = []
    by_index = {t.index: t for t in turns}
    transcript_speakers = {t.speaker for t in turns}

    labelled = {r.speaker for r in note.speaker_roles}
    if labelled != transcript_speakers:
        issues.append(
            f"speaker_roles must list exactly the speakers {sorted(transcript_speakers)}, "
            f"got {sorted(labelled)}"
        )

    for field_name in SECTION_FIELDS:
        section = getattr(note, field_name)
        wanted = (
            Role.doctor if field_name in DOCTOR_ONLY_SECTIONS
            else Role.patient if field_name in PATIENT_ONLY_SECTIONS
            else None
        )
        for i, item in enumerate(section.items):
            for j, ev in enumerate(item.evidence):
                where = f"{field_name}.items[{i}].evidence[{j}]"
                turn = by_index.get(ev.turn)
                if turn is None:
                    issues.append(f"{where}: turn {ev.turn} does not exist")
                    continue

                quote = normalize(ev.quote)
                if len(quote) < MIN_QUOTE_CHARS:
                    issues.append(f"{where}: quote is too short to verify")
                elif quote not in normalize(turn.text):
                    issues.append(
                        f"{where}: quote {ev.quote!r} is not in turn {ev.turn}"
                    )

                if wanted is not None and note.role_of(turn.speaker) is not wanted:
                    issues.append(
                        f"{where}: {field_name} must be supported by a turn spoken by "
                        f"the {wanted.value}, but turn {ev.turn} is speaker {turn.speaker} "
                        f"({note.role_of(turn.speaker).value})"
                    )
    return issues
