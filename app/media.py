import json
import os
from pathlib import Path
import shutil
import subprocess
import numpy as np
import soundfile as sf


def executable(name):
    result = os.getenv(name.upper() + '_PATH') or shutil.which(name)
    if not result:
        raise RuntimeError(f'{name} is missing. Install FFmpeg and put ffmpeg/ffprobe on PATH.')
    return result


def run(args, timeout=600):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-1800:] or 'Media command failed.')
    return result.stdout


def probe(path):
    value = json.loads(run([executable('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path], 60))
    duration = float(value.get('format', {}).get('duration', 0))
    if not np.isfinite(duration) or not 0 < duration <= 7200:
        raise ValueError('Media must be between 0 and 7200 seconds long.')
    return dict(duration=duration, streams=[dict(index=s['index'], type=s['codec_type'], codec=s.get('codec_name'),
        width=s.get('width'), height=s.get('height'), language=s.get('tags', {}).get('language', 'und')) for s in value['streams']])


def normalize_reference(source, target):
    meta = probe(source)
    if not any(s['type'] == 'audio' for s in meta['streams']):
        raise ValueError('Reference file contains no audio.')
    if not 3 <= meta['duration'] <= 30:
        raise ValueError('Use a reference recording between 3 and 30 seconds.')
    run([executable('ffmpeg'), '-v', 'error', '-i', source, '-vn', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', target])


class TimingError(Exception):
    def __init__(self, details):
        super().__init__('Some cues cannot fit. Adjust individual timing or reading; speech was not clipped.')
        self.details = details


def fit_audio(source, target, window, max_speed, check_cancel=lambda: None):
    frames = max(1, round(window * 24000))
    duration = sf.info(str(source)).duration
    speed = max(1., duration / window)
    if speed > max_speed + .00001:
        return None, dict(original=duration, window=window, required_speed=speed)
    for _ in range(32):
        check_cancel()
        run([executable('ffmpeg'), '-v', 'error', '-y', '-i', source, '-af', f'atempo={speed:.10f}',
             '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', target])
        audio, _ = sf.read(str(target), dtype='float32')
        if len(audio) <= frames:
            return audio, dict(speed=speed, duration=len(audio)/24000)
        if speed >= max_speed - 1e-9:
            break
        speed = min(max_speed, max(speed + .005, speed * len(audio)/max(1, frames-480)))
    return None, dict(original=duration, window=window, required_speed=duration/window,
                     attempted_speed=speed, remaining_seconds=max(0, (len(audio)-frames)/24000))


def mux(video, audio, target, start, duration):
    # Re-encode previews for exact seek boundaries and broad browser compatibility.
    run([executable('ffmpeg'), '-v', 'error', '-ss', str(start), '-i', video, '-i', audio,
         '-map', '0:v:0', '-map', '1:a:0', '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast',
         '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', target], 7200)
