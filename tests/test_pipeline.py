from pathlib import Path
import shutil
import subprocess
import numpy as np
import pytest
import soundfile as sf
from app.media import fit_audio, probe
from app.models import Settings, JobRequest
from app.store import Store
from app.jobs import Worker

pytestmark = pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')


class TestSynth:
    __test__ = False
    def __init__(self): self.calls = 0; self.texts = []
    def synthesize(self,text,settings,reference,destination,attempt=0):
        self.calls += 1
        self.texts.append(text)
        rate=24000
        a=.2*np.sin(2*np.pi*440*np.arange(7200)/rate)
        sf.write(str(destination),a,rate,subtype='PCM_16')


def test_fit_and_block_overlong_speech(tmp_path):
    rate=24000
    source=tmp_path/'source.wav'
    sf.write(str(source),.2*np.sin(2*np.pi*230*np.arange(rate)/rate),rate)
    data,info=fit_audio(source,tmp_path/'fit.wav',.95,1.15)
    assert data is not None and len(data)<=round(.95*rate)
    assert info['speed']<=1.15
    data,info=fit_audio(source,tmp_path/'blocked.wav',.2,1.15)
    assert data is None
    assert sf.info(str(source)).frames==rate


def test_real_ffmpeg_render_offset_cache_and_revision(tmp_path):
    store=Store(tmp_path);p=store.create('Lesson',Settings(offset=.5, rules=[dict(source='Hello', replacement='你好'), dict(source='World', replacement='世界')]).model_dump())
    source=tmp_path/p['id']/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=25','-t','5','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    p=store.update(p['id'],0,dict(video=dict(file='source.mp4',**probe(source)),cues=[dict(id=1,start=.2,end=1.2,text='Hello',spoken_text=''),dict(id=2,start=2,end=3,text='World',spoken_text='单句读法')]))
    synth=TestSynth();worker=Worker(store,synth)
    req=JobRequest(kind='preview',revision=p['revision'],duration=300).model_dump()
    j=store.enqueue(p,req);worker.process(j['id']);j=store.job(j['id'])
    assert j['status']=='completed',j['error']
    wav=tmp_path/p['id']/j['result']['audio']
    audio,rate=sf.read(str(wav))
    assert len(audio)==5*rate
    assert np.max(np.abs(audio[:round(.7*rate)]))==0
    assert np.max(np.abs(audio[round(.7*rate):rate]))>.1
    assert abs(probe(tmp_path/p['id']/j['result']['video'])['duration']-5)<.1
    assert synth.calls==2
    assert synth.texts==['你好', '单句读法']
    p=store.approve(p['id'],j)
    final=store.enqueue(p,JobRequest(kind='final',revision=p['revision']).model_dump())
    worker.process(final['id'])
    assert store.job(final['id'])['status']=='completed'
    assert synth.calls==2
    assert synth.texts==['你好', '单句读法']
    assert sf.info(str(tmp_path/p['id']/store.job(final['id'])['result']['audio'])).duration==5


def test_failed_render_keeps_diagnostics_not_partial_video(tmp_path):
    store=Store(tmp_path);p=store.create('Too short',Settings().model_dump())
    p=store.update(p['id'],0,dict(video=dict(file='unused.mp4',duration=5),
        cues=[dict(id=1,start=0,end=.1,text='Hello',spoken_text='')]))
    synth=TestSynth();worker=Worker(store,synth)
    j=store.enqueue(p,JobRequest(kind='preview',revision=p['revision'],duration=3).model_dump())
    worker.process(j['id']);j=store.job(j['id'])
    assert j['status']=='failed'
    assert j['result']['issues'][0]['id']==1
    assert synth.calls==3
    folder=tmp_path/p['id']/'jobs'/j['id']
    assert (folder/'timing_review.json').is_file()
    assert not (folder/'dubbed.mp4').exists()
    assert not (folder/'voiceover.wav').exists()


def test_worker_observes_cancel_before_loading_model(tmp_path):
    store=Store(tmp_path);p=store.create('Cancelled',Settings().model_dump())
    synth=TestSynth();worker=Worker(store,synth)
    j=store.enqueue(p,JobRequest(kind='voice',revision=0).model_dump())
    store.patch_job(j['id'],cancelled=True)
    worker.process(j['id'])
    assert store.job(j['id'])['status']=='cancelled'
    assert synth.calls==0



def test_dictionary_reaches_audition_engine_and_changed_reading_invalidates_cache(tmp_path):
    store = Store(tmp_path)
    p = store.create('Dictionary', Settings(rules=[dict(source='银行', replacement='银航')]).model_dump())
    synth = TestSynth()
    worker = Worker(store, synth)
    for replacement in ['银航', '银航呀']:
        settings = dict(p['settings'], rules=[dict(source='银行', replacement=replacement)])
        p = store.update(p['id'], p['revision'], dict(settings=settings))
        job = store.enqueue(p, JobRequest(kind='voice', revision=p['revision'], text='银行').model_dump())
        worker.process(job['id'])
        assert store.job(job['id'])['status'] == 'completed'
    assert synth.texts == ['银航', '银航呀']


def test_fit_audio_above_double_speed(tmp_path):
    rate = 24000
    source = tmp_path / 'long.wav'
    sf.write(str(source), .2 * np.sin(2 * np.pi * 230 * np.arange(rate * 3) / rate), rate)
    data, details = fit_audio(source, tmp_path / 'fast.wav', 1.2, 3)
    assert data is not None
    assert len(data) <= round(1.2 * rate)
    assert 2.5 <= details['speed'] <= 3
    assert sf.info(str(source)).frames == rate * 3
