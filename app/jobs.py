import json
from pathlib import Path
import threading
import time
import traceback
import numpy as np
import soundfile as sf
from . import detection
from .engines import Synthesizer, audio_key
from .speech_process import SpeechProcess
from .media import TimingError, fit_audio, mux
from .models import Cue, validate_cues
from .store import Conflict
from .subtitles import spoken_text, export_srt


class Cancelled(Exception):
    pass


class Worker:
    def __init__(self, store, synthesizer=None):
        self.store = store
        self.synth = synthesizer or SpeechProcess(Synthesizer)
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        self.store.recover()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        try:
            while not self.stop.wait(.5):
                jid = self.store.next_job()
                if jid:
                    self.process(jid)
        finally:
            if isinstance(self.synth, SpeechProcess):
                self.synth.close()

    def check(self, jid):
        if self.stop.is_set() or self.store.job(jid)['cancelled']:
            raise Cancelled('Cancelled. Completed audio remains cached.')

    def process(self, jid):
        j = self.store.patch_job(jid, status='running', stage='Preparing')
        p, request = j['snapshot'], j['request']
        folder = self.store.root / p['id'] / 'jobs' / jid
        folder.mkdir(parents=True, exist_ok=True)
        def progress(value, stage):
            self.store.patch_job(jid, progress=round(value, 4), stage=stage)
        def check():
            self.check(jid)
        try:
            check()
            if j['kind'] in ('extract', 'ocr', 'transcribe'):
                video = self.store.root / p['id'] / p['video']['file']
                if j['kind'] == 'extract':
                    cues = detection.extract(video, request['stream_index'])
                elif j['kind'] == 'ocr':
                    cues = detection.ocr(video, p['video'], request, folder, progress, check)
                else:
                    cues = detection.transcribe(video, folder, progress, check)
                cues = [Cue(**c).model_dump() for c in cues]
                validate_cues(cues)
                if cues[-1]['end'] > p['video']['duration'] + .1:
                    raise ValueError('Detected subtitles exceed the video duration.')
                check()
                # Keep detected cues even when optimistic locking protects newer user edits.
                (folder/'detected.srt').write_text(export_srt(cues), encoding='utf-8')
                (folder/'detected.json').write_text(json.dumps(cues, ensure_ascii=False), encoding='utf-8')
                self.store.update(p['id'], p['revision'], dict(cues=cues))
                result = dict(subtitles=f"jobs/{jid}/detected.srt", count=len(cues), review_required=True)
            elif j['kind'] == 'voice':
                text = spoken_text(dict(text=request['text']), p['settings']['rules'])
                progress(0, 'Loading model / generating voice; first use may download model files')
                source = self.generate(p, text, 0, progress, check)
                import shutil
                shutil.copy2(source, folder/'voice.wav')
                result = dict(audio=f'jobs/{jid}/voice.wav')
            else:
                result = self.render(j, folder, progress, check)
            check()
            self.store.patch_job(jid, status='completed', progress=1, stage='Ready', result=result)
        except Cancelled as exc:
            self.store.patch_job(jid, status='cancelled', error=str(exc), stage='Cancelled')
        except TimingError as exc:
            (folder/'timing_review.json').write_text(json.dumps(exc.details, ensure_ascii=False, indent=2), encoding='utf-8')
            self.store.patch_job(jid, status='failed', error=str(exc), stage='Timing needs attention',
                result=dict(issues=exc.details, report=f'jobs/{jid}/timing_review.json'))
        except Exception as exc:
            traceback.print_exc()
            result = dict(subtitles=f'jobs/{jid}/detected.srt') if (folder/'detected.srt').exists() else None
            self.store.patch_job(jid, status='failed', error=str(exc)[:2000], stage='Action needed', result=result)

    def generate(self, p, text, attempt, progress, check):
        settings = p['settings']
        reference = p.get('reference') if settings['mode'] == 'reference' else None
        key = audio_key(text, settings, reference['sha256'] if reference else None, attempt)
        cache = self.store.root / p['id'] / 'cache'
        cache.mkdir(exist_ok=True)
        target = cache / (key+'.wav')
        check()
        if target.exists():
            try:
                if sf.info(str(target)).frames > 0:
                    return target
            except Exception:
                pass
            target.unlink(missing_ok=True)
        args = (text, settings, self.store.root/p['id']/reference['file'] if reference else None, target, attempt)
        try:
            if isinstance(self.synth, SpeechProcess):
                self.synth.synthesize(*args, check=check)
            else:
                self.synth.synthesize(*args)
        finally:
            target.with_suffix('.partial.wav').unlink(missing_ok=True)
        check()
        return target

    def render(self, j, folder, progress, check):
        p, request = j['snapshot'], j['request']
        settings, cues = p['settings'], p['cues']
        offset = settings['offset']
        total = p['video']['duration']
        if not cues:
            raise ValueError('Import or detect subtitles first.')
        if any(c['start']+offset < 0 or c['end']+offset > total+.001 for c in cues):
            raise ValueError('Shifted subtitles fall outside the video. Adjust timing or the global offset.')
        start, end = 0., total
        if j['kind'] == 'preview':
            selected = [c for c in cues if c['end']+offset > request['start'] and c['start']+offset < request['start']+request['duration']]
            if not selected:
                raise ValueError('No subtitle cues in the selected preview range.')
            cues = selected
            start = max(0., min(request['start'], cues[0]['start']+offset))
            end = min(total, max(request['start']+request['duration'], cues[-1]['end']+offset))
        # Disk-backed WAV keeps long videos from allocating a full audio timeline in memory.
        wav = folder / 'voiceover.wav'
        rate = 24000
        total_frames = round((end-start)*rate)
        issues, fitted = [], []
        with sf.SoundFile(str(wav), 'w+', samplerate=rate, channels=1, subtype='PCM_16') as output:
            zero = np.zeros(rate, dtype=np.float32)
            remaining = total_frames
            while remaining:
                size = min(remaining, rate)
                output.write(zero[:size])
                remaining -= size
            for i, cue in enumerate(cues):
                check()
                text = spoken_text(cue, settings['rules'])
                best = None
                for attempt in range(3):
                    progress(.8*i/len(cues), f"Generating cue {i+1}/{len(cues)} (ID {cue['id']}); first use may download the model")
                    audio = self.generate(p, text, attempt, progress, check)
                    duration = sf.info(str(audio)).duration
                    if best is None or duration < best[0]:
                        best = (duration, audio)
                    if duration <= (cue['end']-cue['start'])*settings['max_speed']:
                        break
                target = folder/f"fit_{cue['id']:04}.wav"
                first = round((cue['start']+offset-start)*rate)
                last = round((cue['end']+offset-start)*rate)
                data, details = fit_audio(best[1], target, (last-first)/rate, settings['max_speed'], check)
                if data is None:
                    issues.append(dict(id=cue['id'], text=cue['text'], spoken_text=text, **details))
                    continue
                output.seek(first)
                output.write(data)
                fitted.append(dict(id=cue['id'], start=cue['start']+offset, **details))
                progress(.8*(i+1)/len(cues), f'Aligned {i+1}/{len(cues)} cues')
        if issues:
            wav.unlink(missing_ok=True)
            raise TimingError(issues)
        check()
        progress(.86, 'Encoding video; cancellation takes effect after this media operation')
        mux(self.store.root/p['id']/p['video']['file'], wav, folder/'dubbed.mp4', start, end-start)
        (folder/'subtitles.srt').write_text(export_srt(cues, offset-start), encoding='utf-8')
        (folder/'alignment.json').write_text(json.dumps(dict(offset=offset, preview_start=start, cues=fitted), indent=2), encoding='utf-8')
        return dict(video=f"jobs/{j['id']}/dubbed.mp4", audio=f"jobs/{j['id']}/voiceover.wav",
                    subtitles=f"jobs/{j['id']}/subtitles.srt", start=start, duration=end-start)

