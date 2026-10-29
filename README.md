# VoiceFrame

**A local-first video dubbing studio. Shape the voice. Keep the timing.**

[简体中文](README.zh-CN.md) · [Project plan](docs/PROJECT_PLAN.md) · [Architecture](docs/ARCHITECTURE.md) · [AWS deployment](deploy/aws/README.md)

VoiceFrame turns the command-line dubbing workflow into a browser workspace: upload a video, prepare captions, choose a voice, control pronunciation, calibrate timing, approve a preview and export the finished video.

## 🌍 One World, Many Voices

**10 languages · 10 scenes · A world of greetings.**

A creative storyboard for the *One World, Many Voices* showcase: pair each place with a greeting and a distinct voice direction.

| Language | Featured scene | Subtitle / spoken greeting | Voice direction |
| :--- | :--- | :---: | :--- |
| **English** | London beside the Thames | Hello | Male · warm |
| **Mandarin Chinese** | Guilin’s mountains and river | 你好 | Female · gentle |
| **Hindi** | Taj Mahal at sunrise | नमस्ते | Male · welcoming |
| **Spanish** | Seville’s sunlit plazas | Hola | Female · playful |
| **French** | Paris beside the Seine | Bonjour | Male · soft and elegant |
| **Arabic** | Petra’s sandstone architecture | <span dir="rtl">مرحبًا</span> | Female · confident |
| **Bengali** | Bangladesh’s rivers and green countryside | নমস্কার | Male · reflective |
| **Portuguese** | Rio’s coastline | Olá | Female · joyful |
| **Russian** | Saint Petersburg’s canals | Привет | Male · rich and cinematic |
| **Urdu** | Lahore’s illuminated architecture | <span dir="rtl">السلام علیکم</span> | Female · warm |

> [!NOTE]
> This is a creative brief, not a verified language-support matrix or a claim that this video was generated with VoiceFrame. Language availability and voice control depend on the selected engine and model; audition each language before rendering.

## Status

Version 0.1 is a **single-user, self-hosted implementation**, not a hosted multi-tenant service. API, subtitle processing, cache behavior and actual FFmpeg rendering are tested with synthetic test audio. Real MLX/PyTorch inference must be smoke-tested on the target hardware. Windows/macOS CI is configured but is not claimed to have run before the repository is pushed. AWS resources have not been created.

Priority platforms: Apple Silicon Mac, Windows and Linux. Intel Mac support is deferred.

## What works

- Project library with durable SQLite state and explicit save/revision checking.
- Video upload with real FFprobe validation; MP4, MOV, MKV, WEBM and M4V containers. Browser playback depends on the source codec; H.264/AAC MP4 is recommended.
- SRT/WebVTT import, embedded text subtitle extraction, optional burned-in caption OCR and optional original-audio transcription.
- Editable original captions and separate spoken-text overrides. Project pronunciation rules use longest match, without recursive replacement.
- Qwen3-TTS preset voices and reference cloning. Reference audio requires 3–30 seconds and an exact transcript.
- Voice-only auditions, video previews, positive/negative timing offsets and a playhead-to-cue calibration anchor.
- Persistent queued jobs, stage/progress reporting, cancellation, retry and per-cue caching. One speech job runs at a time.
- Final rendering requires an approved preview of the current project revision. Editing settings invalidates approval.
- MP4, WAV and calibrated SRT outputs. Original media is preserved.
- Chinese/English interface; English code and API fields.
- Optional access-key login, authenticated media, same-origin write checks and file path containment.

## Quick start

Prerequisites: **Python 3.11 or newer**, FFmpeg **including ffprobe**, and free disk space for model weights and video outputs. The interface itself does not require Node.js or an API key. Internet is required to install packages and download model weights the first time.

### Apple Silicon Mac

Install Python and FFmpeg using your preferred package manager, or their official installers. With Homebrew:

```bash
brew install python@3.12 ffmpeg
cd voiceframe
bash start.sh --install-engine
```

The launcher creates `.venv`, installs the core and MLX-Audio packages and opens `http://127.0.0.1:8765`. Later starts only need:

```bash
bash start.sh
```

Use native ARM64 Python, not a Rosetta terminal. On an M3 with 18 GB, start with short previews and keep other large model processes closed. No real-time speed or memory benchmark is claimed.

### Windows

Install Python 3.11+ with **Add Python to PATH** enabled, and install FFmpeg. Open a new terminal and check `python --version`, `ffmpeg -version`, and `ffprobe -version`.

From PowerShell in the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 --install-engine
```

Alternatively, double-click `start.bat` to open the UI, then install the voice engine from a terminal:

```powershell
.\.venv\Scripts\python.exe scripts\install_engine.py --engine torch
```

NVIDIA users should use the PyTorch build appropriate for their CUDA driver from the [official PyTorch installer](https://pytorch.org/get-started/locally/). Verify the project environment:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

`False` means CPU inference, which may be very slow. AMD/DirectML/ROCm acceleration is not implemented in this release. NVIDIA support requires a compatible CUDA-enabled PyTorch installation; package installation alone does not prove that the GPU is available.

### Linux

On Debian/Ubuntu with Python 3.11+ available:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg libsndfile1
cd voiceframe
bash start.sh --install-engine
```

For NVIDIA, install a matching PyTorch CUDA build into `.venv` and verify `torch.cuda.is_available()`. CPU fallback exists but is slow. Use the native MLX path on Apple Silicon; Docker does not expose Apple's Metal GPU to this Linux container.

### Reuse existing model downloads

Point `HF_HOME` to the existing Hugging Face cache **before starting**. For the earlier QwenVoice setup:

```bash
export HF_HOME="$HOME/Documents/QwenVoice/.cache/huggingface"
bash start.sh --install-engine
```

The application keeps its own Python environment by default. `VOICEFRAME_PYTHON=/path/to/python` optionally uses an existing environment, but the launcher installs core dependencies there; avoid this if other applications depend on its current package versions. Model downloads remain outside Git.

To use the approved voice from the earlier workflow, upload its `reference.wav` in the Voice tab and paste its exact transcript from that project's `voice_config.json`. The source repository does not include your private recordings or videos.

## Workflow

1. **Create a project and upload the original video.** A replacement video clears the old cues. Files remain local to the server you run.
2. **Import or detect captions.** Embedded subtitle tracks, burned-in OCR and audio transcription are different operations. Detection results require manual review; they are not automatically perfect timestamps.
3. **Choose the voice.** Presets use CustomVoice. Reference cloning uses Base and ignores preset speaker/style instructions. First use downloads the selected model; switching voice mode may download a second model.
4. **Set pronunciation.** For example, `2^n => 二的n次幂`. Use a cue's spoken override when a formula or polyphonic word needs context. The original subtitle text stays separate. Spelling substitutions guide TTS; phoneme-level control is not guaranteed.
5. **Calibrate picture sync.** Select a cue, pause the original video on the frame where that caption appears, and click **Align selected cue to this frame**. A positive offset delays the voice. Check another point later in the video. If drift is nonuniform, edit individual cue times instead of applying one global offset.
6. **Generate a preview.** Choose a start time and 3–90 seconds. The selection expands to include intersecting cues completely. This is cue-level alignment, not word-level forced alignment.
7. **Approve and export.** Only a preview from the current revision can be approved. Final rendering reuses matching cue audio and replaces the entire original soundtrack, including music. Independent background-music mixing is deferred.

The service never silently cuts speech to fit a window. It tries up to three speech takes and bounded FFmpeg time stretching. Cues that still do not fit produce a downloadable diagnostic report. Review timing, the spoken reading, or the speed ceiling; never shorten text blindly when matching burned-in captions.

## Optional caption tools

### Burned-in captions: Tesseract OCR

Install Tesseract and Chinese `chi_sim` language data if needed. The Environment panel checks the executable. On macOS, Homebrew packages include `tesseract` and `tesseract-lang`. On Ubuntu use `tesseract-ocr` and `tesseract-ocr-chi-sim`. On Windows install a Tesseract distribution and add its executable directory to PATH.

Choose a crop containing only captions, using top/bottom fractions of the frame height. Sampling defaults to 0.5 seconds, so boundaries are approximate. Complex mathematical notation can require substantial correction. OCR currently performs exact-text adjacent-frame merging; it does not implement confidence-aware fuzzy reconciliation.

### Original audio: faster-whisper

```bash
# macOS / Linux
.venv/bin/python -m pip install 'faster-whisper>=1,<2'
# Windows
.\.venv\Scripts\python.exe -m pip install "faster-whisper>=1,<2"
```

Transcription uses the small model on CPU/int8 and downloads it on first use. It recognizes the original spoken audio, not the text in the picture.

## Running and troubleshooting

- **Missing FFmpeg:** ensure both executables are on PATH, or set `FFMPEG_PATH` and `FFPROBE_PATH` to absolute executable paths.
- **First job seems slow:** model download/loading happens inside the first job. The UI reports the stage but does not currently expose byte-level Hugging Face download progress; detailed logs are in the terminal.
- **Voice comes before captions:** measure and adjust the offset. There is no universal 2.12-second correction.
- **Cue exceeds its window:** inspect the report shown in Activity. No final video is returned with clipped or missing speech.
- **Cancel is not immediate:** cancellation takes effect between cues and media operations; an in-progress model inference or video encoding finishes first.
- **Server restarted:** running jobs become interrupted; choose Retry. Completed cue audio is reusable.
- **Settings conflict:** reload the project before saving. The API rejects stale edits instead of overwriting newer ones.
- **Native MLX errors:** confirm `python -c "import platform; print(platform.machine())"` returns `arm64` in the project environment.
- **Port in use:** `bash start.sh --port 8766` or pass `--port 8766` to the Windows launcher.
- **Source video cannot play in the browser:** convert the source to H.264/AAC MP4 without changing its start time; the generated output is already encoded for browsers.

## Storage and access

`data/voiceframe.sqlite3` contains metadata. `data/<project-id>/` contains originals, cache and job artifacts. `VOICEFRAME_DATA` changes this location. Default uploads are capped at 1 GB and media duration at two hours. `VOICEFRAME_MAX_UPLOAD_MB` changes the file cap. Multipart parsing still uses temporary disk space before application-level validation; size requests at the reverse proxy as well for public deployments.

One process and one worker own a data directory, enforced by a file lock. Do not use Uvicorn `--workers 2`, multiple replicas on the same volume or network-filesystem SQLite. This is a single-user shared workspace, not tenant-isolated SaaS.

Local startup binds to loopback. Public HTTPS hosting requires:

```text
VOICEFRAME_PUBLIC=1
VOICEFRAME_ACCESS_KEY=<32 or more random characters>
VOICEFRAME_ALLOWED_HOSTS=voice.example.com,127.0.0.1
```

Set these as real environment variables. `.env.example` is a reference; native startup does not automatically load `.env`. AWS Compose reads `deploy/aws/.env`. Do not commit keys. Public sessions use HttpOnly, Secure, SameSite=Strict cookies and expire after 24 hours. Access keys are for the entire workspace, not separate user accounts.

Back up data while the app is stopped, or use SQLite's backup API plus a consistent copy of media files. Cache may be omitted to reduce backup size. Manage disk use: per-attempt audio and previous renders remain available; automatic retention is deferred.

## Docker and AWS

Linux CPU:

```bash
docker compose up --build
```

NVIDIA host with NVIDIA Container Toolkit:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```

See [AWS deployment](deploy/aws/README.md) for EC2, Caddy HTTPS, volumes and Terraform. These are deployment templates, not a verified live AWS deployment. Infrastructure changes incur costs and require your own AWS account, region, quota and AMI selection.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check app/static/app.js  # optional Node.js syntax check
```

The test synthesizer exists only in tests and is never selectable in the product. See [verification notes](docs/VERIFICATION.md) for the actual test scope and remaining hardware checks.

## Get the source

```bash
git clone https://github.com/medxiaorudan/VoiceFrame.git voiceframe
cd voiceframe
```

Then follow the platform-specific quick start above. Private repository access requires GitHub authentication.

## Sources

- [MLX-Audio Qwen3-TTS reference](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/tts/models/qwen3_tts/README.md)
- [Qwen3-TTS official implementation](https://github.com/QwenLM/Qwen3-TTS)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Docker Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/)

## License

Source code is licensed under [Apache-2.0](LICENSE). Model weights and dependencies have their own licenses.
