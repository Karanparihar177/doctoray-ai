# Doctoray AI

An independent Python/FastAPI proof-of-concept service for AI-assisted
workflows in the Doctoray consultation platform.

The current development focus is the **recording-to-transcript
foundation**: downloading a consultation recording, extracting audio as
Opus or FLAC, and transcribing it with Deepgram (Nova-3) with speaker
labels.

> **POC boundary:** This repository is being developed and validated
> independently. Doctoray's existing Node.js backend remains responsible
> for authentication and canonical application data (MySQL). Frontend and
> backend integration will be considered after the standalone POC is
> validated.

## Table of contents

- [Current scope](#current-scope)
- [Architecture and data flow](#architecture-and-data-flow)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Local setup](#local-setup)
- [Scripts and commands](#scripts-and-commands)
- [Transcription API](#transcription-api)
- [Transcription with Deepgram](#transcription-with-deepgram)
- [Audio formats](#audio-formats)
- [Development data (PriMock57)](#development-data-primock57)
- [Tests](#tests)
- [Configuration and environment](#configuration-and-environment)
- [Security and handling consultation recordings](#security-and-handling-consultation-recordings)
- [Current limitations and next steps](#current-limitations-and-next-steps)

## Current scope

The original Doctoray AI POC has two intended features:

1. AI consultation summaries and medical notes.
2. Patient symptom summarisation and pre-consultation briefs.

Implemented so far (the foundation for feature 1):

- Download a recording over HTTPS.
- Extract mono Opus (64 kbps) or FLAC audio and print media metadata.
- Transcribe Arabic or English audio with Deepgram, with speaker turns.
- An upload endpoint that returns the transcript as JSON.

Not implemented yet: doctor/patient role labelling, English translation of
Arabic transcripts, note generation, the patient brief, authentication, job
status tracking, and S3 presigned-URL retrieval.

Clinical safety boundaries:

- AI-generated consultation notes must be reviewed, edited if needed,
  and approved by a doctor before becoming a final medical record.
- Symptom summaries must reflect information explicitly supplied by
  the patient.
- The service must not autonomously diagnose, prescribe medication, or
  make treatment decisions.
- Preserve source recordings and source information; do not silently
  replace them with generated content.

## Architecture and data flow

### Current flow

```text
Recording URL (HTTPS)                  Audio file (upload or local)
        |                                          |
        v                                          |
 download  -> data/recordings/*.mp4                |
        |                                          |
        v                                          |
 to-opus / to-flac  -> data/audio/*.opus|.flac ----+
 (one "compressed audio" step)                     |
                                                   v
                                  transcribe (Deepgram Nova-3,
                                  language + speaker labels)
                                                   |
                                                   v
                              data/transcripts/*.json  and  *.txt
                              (speaker 0 / speaker 1 turns)
```

`pipeline` runs download and Opus conversion in one command. The upload
endpoint skips the files and returns the transcript directly.

### Intended flow

```text
Node.js backend creates job and presigned S3 URL (same auth token)
                    |
                    v
   AI service: fetch, extract audio (Opus/FLAC), transcribe
                    |
                    v
   LLM: suggest which speaker is the doctor, translate to English
                    |
                    v
   LLM: structured note draft, validated (Pydantic)
                    |
                    v
   Backend stores draft in MySQL -> doctor reviews, confirms
```

Deepgram only numbers speakers. Deciding which speaker is the doctor is a
later step, and the doctor confirms it in review. Avoid queues, vector
databases, agents, or orchestration frameworks until a demonstrated
requirement justifies them. See `docs/` for the workflow diagrams.

## Repository structure

```text
doctoray-ai/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── health.py
│   │   ├── router.py
│   │   └── transcriptions.py        # POST /api/v1/transcriptions
│   ├── core/config.py               # settings from .env
│   └── services/
│       ├── storage/http_downloader.py
│       ├── audio/metadata.py        # FFprobe inspection
│       └── transcription/deepgram_client.py
├── scripts/
│   └── all_scripts.py               # download, to-opus, to-flac, transcribe, pipeline
├── scripts/inspect_media.py         # print media metadata
├── tests/
│   ├── test_health.py
│   ├── test_metadata.py
│   └── test_transcriptions.py
├── data/
│   ├── recordings/                  # downloaded video; NOT tracked
│   ├── audio/                       # generated Opus/FLAC; tracked
│   ├── transcripts/                 # Deepgram output; tracked
│   └── primock57/                   # public sample; TextGrids tracked, WAVs not
├── docs/                            # workflow diagrams
├── .env.example
└── README.md
```

| File | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI application and mounts the router. |
| `app/api/v1/transcriptions.py` | Upload endpoint: validates the file, sends it to Deepgram, returns speaker turns. The upload is kept only in a temporary file. |
| `app/core/config.py` | Environment-based settings, including the Deepgram key (kept as a secret). |
| `app/services/storage/http_downloader.py` | Streams a remote recording to disk in chunks via a `.part` file, published only after success. HTTPS only, 600 MB cap. |
| `app/services/audio/metadata.py` | FFprobe inspection: format, duration, size, video and audio streams. |
| `app/services/transcription/deepgram_client.py` | Calls Deepgram's `/v1/listen` over HTTP and flattens the result into speaker turns. |
| `scripts/all_scripts.py` | The step-by-step workflow commands (see below). It contains the FFmpeg conversion logic. |
| `scripts/inspect_media.py` | Prints metadata for a video or audio file. |

The earlier WAV, FLAC-compression and benchmark scripts and their tests
were removed as unused. They remain in git history.

## Requirements

- Python (developed with Python 3.14.7; use the project's virtual
  environment and the versions in `requirements.txt`).
- FFmpeg and FFprobe on `PATH` (`brew install ffmpeg` on macOS).
- A Deepgram API key for transcription.
- Git. Git LFS is only needed if you clone the full PriMock57 repository.

## Local setup

Run commands from the repository root.

```bash
git clone <YOUR_GIT_REPOSITORY_URL>
cd doctoray-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then set DEEPGRAM_AI_KEY in .env
mkdir -p data/recordings data/audio data/transcripts
fastapi dev app/main.py
```

Interactive API docs: `http://127.0.0.1:8000/docs`. Health endpoints:
`GET /health` and `GET /api/v1/health`.

## Scripts and commands

Run as Python modules from the repository root with the virtual
environment active. Use `--help` on any command for its arguments.

```bash
python -m scripts.all_scripts download   --url "<HTTPS_URL>"
python -m scripts.all_scripts to-opus    --input data/recordings/appointment.mp4
python -m scripts.all_scripts to-flac    --input data/recordings/appointment.mp4
python -m scripts.all_scripts transcribe --input data/audio/appointment.opus --language ar-EG
python -m scripts.all_scripts pipeline   --url "<HTTPS_URL>"
python -m scripts.inspect_media --input data/audio/appointment.opus
```

| Command | What it does |
|---|---|
| `download` | Streams the video to `data/recordings/appointment.mp4` (`--output` to change). |
| `to-opus` | Mono Opus, 64 kbps target, VBR, `voip` mode, to `data/audio/<name>.opus` (`--bitrate`). |
| `to-flac` | Lossless FLAC to `data/audio/<name>.flac` (`--level 0-12`, default 5). |
| `transcribe` | Sends Opus, FLAC or WAV to Deepgram and saves `data/transcripts/<name>.<language>.json` (raw response) and `.txt` (one line per speaker turn). `--language` is a Deepgram code such as `en` or `ar-EG`; `--no-diarize` skips speaker labels. |
| `pipeline` | `download`, then `to-opus` at 64 kbps (`--name` sets the base file name). |

- Conversions accept video or audio input and refuse to overwrite existing
  output unless you pass `--force`. Only a verified output file is kept.
  Source tags are kept (`-map_metadata 0`).
- Each command prints extension, duration and size, plus codec, sample
  rate and channels, when it finishes.
- The download URL is never printed, because it may be presigned.
- Do not paste real URLs, credentials, or patient information into source
  control, examples, or logs.

## Transcription API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transcriptions \
  -F "file=@data/audio/primock57_day1_c01.opus" \
  -F "language=en"
```

- Accepts `.opus`, `.ogg`, `.flac`, `.wav`, `.mp3` up to `MAX_UPLOAD_MB`
  (default 200).
- Returns `request_id`, `language`, `duration_seconds`, `speakers`, and
  `utterances` (speaker, start, end, text, confidence).
- Errors: 415 unsupported type, 422 invalid language, 400 empty file,
  413 too large, 502 Deepgram error, 503 key not configured.
- The upload is stored only in a temporary file that is deleted
  afterwards, and nothing is persisted by the endpoint.
- **No authentication yet.** Do not expose this endpoint beyond localhost
  until the shared auth token check is added.
- The request waits for Deepgram, so very long recordings can time out the
  client. The job-and-status flow replaces this later.

## Transcription with Deepgram

- Model: `nova-3`. Arabic is supported on Nova-3 only. The sample
  appointment is Egyptian Arabic, so use `ar-EG` (other dialect codes
  exist, such as `ar-SA` and `ar-AE`). English uses `en`.
- Request options: `punctuate`, `smart_format`, `utterances`, speaker
  labels via `diarize_model=latest`, and `mip_opt_out=true` to exclude the
  audio from Deepgram's model-improvement program.
- Each call sets one language. Arabic with embedded English words
  (code-switching) is unverified and needs a real test.
- Deepgram does not translate. English versions of Arabic transcripts will
  come from an LLM, and the Arabic stays the source of truth.
- Speakers are numbers (`0`, `1`). Which one is the doctor is not
  assumed; role mapping must be verified by the doctor.
- Data residency: set `DEEPGRAM_BASE_URL=https://api.eu.deepgram.com`
  for the EU endpoint. Confirm retention terms and any business associate
  agreement with Deepgram before sending real patient audio.
- Check on the PriMock57 sample: speaker labels agreed with the human
  transcripts on about 99.6% of scored words. That audio is two clean
  tracks mixed together, so treat it as an upper bound. Word error rate
  has not been measured, and Egyptian Arabic accuracy is unmeasured
  because no one on the team can verify Arabic output yet.

## Audio formats

FLAC and Opus are treated as one "compressed audio" step. Choose by
transcription quality and the provider's file limits, not size alone.

| Recording | FLAC | Opus (64 kbps) |
|---|---|---|
| Doctoray sample, about 18 min, AAC 48 kHz mono source | 31.94 MiB | 8.26 MiB (about 92% smaller than WAV) |
| PriMock57 consultation, 7m 38s, 16 kHz mono | 7.26 MB | 3.26 MB |

These are one-off measurements, not guarantees. The Doctoray source
already has lossy AAC audio, so FLAC preserves decoded samples without
restoring detail, and Opus adds another lossy step.

## Development data (PriMock57)

To avoid sending real consultations to an outside provider during
development, tests use one public mock consultation from
[PriMock57](https://github.com/babylonhealth/primock57) (CC BY 4.0;
attribution in `data/primock57/ATTRIBUTION.md`).

- `data/primock57/` holds the separate doctor and patient WAV files and
  their human TextGrid transcripts (`day1_consultation01`). The WAV files
  are git-ignored (about 28 MB); download them with:

```bash
mkdir -p data/primock57 && cd data/primock57
for r in doctor patient; do
  curl -fLO https://media.githubusercontent.com/media/babylonhealth/primock57/main/audio/day1_consultation01_$r.wav
done
cd ../..
```

- The two WAV files were mixed into one mono recording to match Doctoray's
  single-track recordings, then converted:

```bash
ffmpeg -i data/primock57/day1_consultation01_doctor.wav \
       -i data/primock57/day1_consultation01_patient.wav \
       -filter_complex "amix=inputs=2:duration=longest:normalize=0" -ac 1 \
       data/recordings/primock57_day1_c01.wav
python -m scripts.all_scripts to-opus --input data/recordings/primock57_day1_c01.wav
python -m scripts.all_scripts to-flac --input data/recordings/primock57_day1_c01.wav
python -m scripts.all_scripts transcribe --input data/audio/primock57_day1_c01.opus --language en
```

- Git tracks `data/primock57/` (TextGrids and attribution, not the WAVs),
  `data/audio/` and `data/transcripts/`. `*.wav` and `data/recordings/`
  are ignored. Files named `appointment*` in the audio
  and transcripts folders are ignored too, because those are real
  consultation recordings. If you use a different `--name` for real
  recordings, add it to `.gitignore` before committing.

## Tests

```bash
pytest -v
```

Covers the health endpoints, media metadata (using small FFmpeg-generated
fixtures), and the transcription endpoint with Deepgram mocked, so the
tests make no network calls and need no API key. FFmpeg and FFprobe must be
installed. The conversion commands and the Deepgram client itself are
checked manually and have no automated tests yet.

## Configuration and environment

| Variable | Purpose | Default |
|---|---|---|
| `DEEPGRAM_AI_KEY` | Deepgram API key. Set in `.env` only. | none |
| `DEEPGRAM_BASE_URL` | Deepgram host (use the EU host for EU residency). | `https://api.deepgram.com` |
| `DEEPGRAM_MODEL` | Speech model. | `nova-3` |
| `MAX_UPLOAD_MB` | Upload limit for the API. | `200` |

- Keep secrets in `.env`; commit only `.env.example` with placeholders.
- Do not commit real consultation recordings, transcripts, patient
  information, API keys, or presigned storage URLs.
- Use pinned requirements for reproducible environments.

## Security and handling consultation recordings

Consultation recordings contain sensitive health information. Before
production use:

1. Retrieve recordings only through an authorised backend-to-service
   workflow or short-lived, scoped storage access (presigned URLs).
2. Use least-privilege storage permissions. Avoid public recording URLs.
3. Validate the storage host and redirects before downloading remote
   URLs to prevent server-side request forgery (SSRF).
4. Encrypt data in transit and at rest.
5. Avoid logging patient data, transcript text, access tokens, or
   presigned URLs.
6. Restrict local recording access and delete temporary media according
   to an approved retention policy. Transcript files contain patient
   speech and need the same care as the audio.
7. Use synthetic or de-identified recordings for development where
   possible.
8. Verify vendor contractual, privacy, retention, and healthcare
   compliance requirements before sending real consultation data to an
   external AI provider.

The existing backend remains the source of truth for authentication,
appointments, recordings, patient input, and final approved notes.

## Current limitations and next steps

- Add the shared auth token check to the API and the job-and-status flow
  with presigned S3 URLs (replaces the open HTTP downloader).
- Verify Egyptian Arabic quality with a native speaker, including
  medical terms, names, numbers, and speaker turns.
- Test Arabic with embedded English words, and compare FLAC with Opus
  transcripts.
- Measure word error rate on PriMock57 against the human transcripts.
- Add an LLM step to suggest speaker roles and translate Arabic to
  English. Never assume speaker 0 is the doctor.
- Generate structured note drafts with validation, source quotes, and
  mandatory doctor approval.
- Build the patient symptom brief.
- Add tests for the Deepgram client and the conversion commands.
- Integrate with the Doctoray backend (MySQL, shared auth token) only
  after the standalone POC is validated.

---

**Development principle:** Keep the implementation small, modular,
testable, and evidence-driven.
