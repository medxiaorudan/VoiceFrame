import csv
import io
from pathlib import Path
import re
import shutil
from .media import executable, run
from .subtitles import parse_subtitles


def extract(video, index):
    text = run([executable('ffmpeg'), '-v', 'error', '-i', video, '-map', f'0:{index}', '-f', 'srt', '-']).decode('utf-8')
    return parse_subtitles(text)


def ocr(video, metadata, options, folder, progress, check):
    if not shutil.which('tesseract'):
        raise RuntimeError('Install Tesseract plus chi_sim/eng language data to recognize burned-in captions.')
    top, bottom, interval = options['crop_top'], options['crop_bottom'], options['interval']
    frame_dir = folder / 'ocr-frames'
    frame_dir.mkdir()
    run([executable('ffmpeg'), '-v', 'error', '-i', video, '-vf',
         f'fps=1/{interval},crop=iw:ih*{bottom-top}:0:ih*{top},scale=1280:-1', frame_dir/'%06d.png'], 7200)
    files = sorted(frame_dir.glob('*.png'))
    cues, current = [], None
    languages = run(['tesseract', '--list-langs']).decode(errors='replace')
    language = 'chi_sim+eng' if 'chi_sim' in languages else 'eng'
    try:
        for i, frame in enumerate(files):
            check()
            output = run(['tesseract', frame, 'stdout', '-l', language, '--psm', '6'], 60).decode(errors='replace')
            text = ' '.join(output.split()).strip()
            # OCR boundaries are estimates at the configured sampling interval.
            start = i * interval
            end = min(metadata['duration'], (i+1)*interval)
            if text and current and current['text'] == text:
                current['end'] = end
            else:
                if current:
                    cues.append(current)
                current = dict(start=start, end=end, text=text, spoken_text='') if text else None
            progress((i+1)/max(1, len(files)), 'Recognizing burned-in captions; review text and timing afterward.')
        if current:
            cues.append(current)
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)
    for i, cue in enumerate(cues):
        cue['id'] = i+1
    if not cues:
        raise ValueError('No captions detected. Adjust the crop region or upload subtitles.')
    if len(cues) > 5000:
        raise ValueError('OCR produced too many fragments. Use a tighter crop or a larger sample interval.')
    return cues


def transcribe(video, folder, progress, check):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError('Install the optional speech recognition package: pip install faster-whisper') from None
    wav = folder / 'source.wav'
    run([executable('ffmpeg'), '-v', 'error', '-i', video, '-vn', '-ar', '16000', '-ac', '1', wav])
    model = WhisperModel('small', device='cpu', compute_type='int8')
    segments, info = model.transcribe(str(wav), vad_filter=True)
    cues = []
    for segment in segments:
        check()
        if segment.text.strip():
            cues.append(dict(id=len(cues)+1, start=segment.start, end=segment.end, text=segment.text.strip(), spoken_text=''))
        progress(min(.99, segment.end/max(1, info.duration)), 'Transcribing original audio; not reading on-screen captions.')
    if not cues:
        raise ValueError('No speech was detected.')
    return cues
