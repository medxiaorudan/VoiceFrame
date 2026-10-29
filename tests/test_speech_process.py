import time
from pathlib import Path
import pytest
from app.speech_process import SpeechProcess
from app.jobs import Cancelled


class FakeSynth:
    def synthesize(self, text, settings, reference, destination, attempt):
        Path(destination).write_text('started')
        if text == 'block':
            while True:
                time.sleep(.05)
        elif text == 'fail':
            raise ValueError('engine failed')


def test_cancel_stops_active_process_and_allows_retry(tmp_path):
    speech = SpeechProcess(FakeSynth)
    target = tmp_path / 'result'
    deadline = time.monotonic() + 10
    def check():
        if target.exists():
            raise Cancelled('cancel')
        assert time.monotonic() < deadline
    try:
        with pytest.raises(Cancelled):
            speech.synthesize('block', {}, None, target, 0, check=check)
        assert speech.process is None
        speech.synthesize('ok', {}, None, target, 0, check=lambda: None)
        pid = speech.process.pid
        speech.synthesize('ok', {}, None, target, 0, check=lambda: None)
        assert speech.process.pid == pid
        with pytest.raises(RuntimeError, match='engine failed'):
            speech.synthesize('fail', {}, None, target, 0, check=lambda: None)
        assert speech.process is None
    finally:
        speech.close()
