# Verification record

Date: 2026-10-29. Build environment: Linux x86_64, Python 3.12.

## Completed

- 21 pytest checks passed: subtitle parsing and invalid timing rejection; pronunciation precedence; cache identity; optimistic revisions; preview approval invalidation; queue guards and restart recovery; API upload constraints; path containment; same-origin writes; access-key authentication; final-render approval gate; cancellation; project deletion guard; actual FFmpeg duration fitting; and video preview/final composition with a deterministic test tone.
- `node --check app/static/app.js` passed.
- Python module compilation and POSIX startup shell syntax checks passed.
- Docker Compose and GitHub Actions YAML parsed successfully.
- Media integration checked a positive 0.5-second offset, correct silent lead-in, exact WAV duration, output MP4 duration and cache reuse from preview to full render.
- Overlong test speech produced a diagnostic report and no final video. Cancellation before inference loaded no model.

## Not verified

- Real Qwen3-TTS model downloads and inference on MLX, CUDA or CPU. This build environment did not run those models.
- Windows/macOS execution. A CI matrix is supplied but has not been run on GitHub.
- Browser interaction, responsiveness and visual QA. The managed preview service could not find the project's Python virtual-environment executable in its runtime. This infrastructure failure was not bypassed by introducing a second server.
- Terraform provider validation, Docker image build, NVIDIA device access, TLS provisioning, AWS deployment or performance benchmarks. Docker/Terraform executables were unavailable.
- OCR accuracy on real burned-in captions, ASR accuracy and exact word-level timing. These remain human-reviewed outputs.
- A live GitHub repository. The current connector lacked repository-creation capability; a private-repository publication script is included.

## Target-hardware acceptance checklist

1. Start with the platform launcher; inspect Environment and verify FFmpeg/FFprobe.
2. Install the platform engine; on Windows/Linux verify CUDA detection when using NVIDIA.
3. Upload a short H.264/AAC MP4 plus a matching SRT.
4. Generate one preset audition. Check intelligibility, latency and memory.
5. Upload the approved reference recording and its exact transcript; generate a second audition.
6. Add a formula reading rule and a cue-specific override; verify actual speech and unchanged subtitle text.
7. Calibrate an on-screen caption anchor; compare the beginning and end of a 30-second preview.
8. Cancel and retry a job; verify cached cues are reused.
9. Approve the preview; render and inspect full MP4, WAV and SRT exports.
10. Restart the application and confirm project persistence and interrupted-job recovery.

The frontend is connected to actual API routes; there is no selectable mock/demo speech engine. Passing synthetic media tests does not establish naturalness, voice similarity or cross-platform GPU stability.
