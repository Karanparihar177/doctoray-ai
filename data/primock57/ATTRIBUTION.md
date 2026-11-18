# PriMock57 sample data

Files in this folder come from the PriMock57 dataset (57 mock primary-care
consultations) published by Babylon Health:

- Source: https://github.com/babylonhealth/primock57
- Paper: Papadopoulos Korfiatis et al., "PriMock57: A Dataset Of Primary Care
  Mock Consultations", ACL 2022 (https://arxiv.org/abs/2204.00333)
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)

Used here: `day1_consultation01` only.

- `*_doctor.wav` / `*_patient.wav`: original separate recordings (16 kHz mono).
- `*_doctor.TextGrid` / `*_patient.TextGrid`: human utterance-level transcripts
  with start and end times. The speaker is given by the file name.

Changes made: none to these files. A single mixed recording was derived from
the two WAV files for development (see the project README).
