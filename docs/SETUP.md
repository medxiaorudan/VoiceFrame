# Setup and troubleshooting

**EN** · [中文](SETUP.zh-CN.md) · [Home](../README.md)

## Download

```bash
git clone https://github.com/medxiaorudan/VoiceFrame.git voiceframe
cd voiceframe
```

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

