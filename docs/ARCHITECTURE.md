# Architecture and engineering decisions

## Scope

VoiceFrame 0.1 is one authenticated personal workspace, with multiple projects, served by one FastAPI process. Apple Silicon MLX and Windows/Linux PyTorch are the priority inference paths. Intel Mac, multi-tenancy and distributed workers are deferred.

## Modules

| Module | Responsibility |
|---|---|
| `app/main.py` | HTTP API, access-key sessions, upload validation, media responses, static frontend |
| `app/models.py` | Pydantic request schemas and cue validation |
| `app/store.py` | SQLite transactions, revisions, preview approval and durable job state |
| `app/engines.py` | Lazy single-model MLX/PyTorch adapters and voice cache identity |
| `app/subtitles.py` | SRT/VTT parsing, non-recursive pronunciation replacement, SRT export |
| `app/detection.py` | Text-track extraction, Tesseract OCR, optional faster-whisper |
| `app/jobs.py` | Serial job worker, cancellation checkpoints, cache reuse and render pipeline |
| `app/media.py` | FFprobe/FFmpeg subprocesses, bounded time stretching, video encoding |
| `app/static/` | Buildless ES module UI, bilingual labels and responsive studio layout |

## State transitions

Jobs transition queued → running → completed/failed/cancelled. Queued cancellation is immediate. Restart recovery marks running jobs interrupted; retry explicitly creates a new job from the same snapshot. Edits after a job starts do not modify its snapshot. Extraction writes its detected SRT before attempting a project revision update, so a conflict preserves the result for manual import.

Project revisions increase on every edit or upload. Approved revision is cleared on edit. Approval requires a completed preview for that revision and project. Final generation checks approval. Multiple active jobs for the same project are rejected transactionally. A process-level file lock prevents two servers from sharing the queue and GPU implicitly.

## Timeline contract

`cue.start`/`cue.end` refer to the original subtitle timeline. `settings.offset` is added only for placement/export; it does not change synthesis cache identity. Positive means delayed narration. Cue overrides and dictionary rules affect speech, never original caption text. SRT export uses the original text with adjusted timestamps.

Preview selection includes whole cues intersecting the requested time range and keeps the correct picture seek offset. Final duration comes from FFprobe. Output is a disk-backed mono PCM WAV at 24 kHz; silence fills unused time. No speech is cropped to make a cue fit. FFmpeg output sample counts are measured, not inferred from requested speed.

No automatic word-level forced alignment is implemented. Burned-in OCR gives approximate sampled boundaries. Multiple calibration points should be checked when source subtitles drift. Complex formulas and polyphonic words need explicit spoken overrides.

## Caching and inference

Per-project cache identity includes actual spoken text, selected model, engine, synthesis settings, reference audio hash and take number. Global offset and speed ceiling do not invalidate source speech. One model object is retained; switching variants releases the old object. Heavy inference is lazy and never runs during application import.

Both model backends follow their upstream Python interfaces. These adapters are not hardware-validated in this build environment. Seed reuse improves reproducibility but is not a promise of bit-identical results across package versions or devices. Engine dependencies use compatibility ranges; freeze the environment after validating a hardware deployment.

## Security and limits

Local startup binds loopback. Production requires a strong shared key and HTTPS. Session signatures are HMACs with a 24-hour expiry; cookies are HttpOnly/SameSite and Secure in public mode. API and media routes are authenticated. Mutations reject cross-origin requests. Uploaded filenames are not used as storage paths. Resolved media paths must remain inside the project directory. Public reverse proxies enforce body limits before multipart spooling.

This release does not implement multi-user identity, tenant ACLs, encrypted application-level media, streaming large uploads to S3, per-user quotas or distributed job claims. Do not expose it as a public SaaS without those changes. Logs may include local paths and model errors; operators should treat them as workspace data.

## Deployment evolution

The first AWS option is one GPU EC2 machine with Docker Compose, encrypted EBS and Caddy. Model weights and project data are separate named volumes. A future distributed design would replace SQLite/local files with PostgreSQL + S3 and a queue/worker service. HTTP API and engine interfaces can remain, but distributed locking and tenant access must be redesigned explicitly.
