import json
import threading
from pathlib import Path
import pytest
from app.models import ProjectEdit, Settings
from app.subtitles import parse_subtitles, spoken_text, export_srt
from app.engines import audio_key
from app.store import Store, Conflict


def test_srt_vtt():
    cues = parse_subtitles('\ufeff1\r\n00:00:00,200 --> 00:00:02,020\r\n我们学过子集的概念\r\n')
    assert cues[0]['start'] == .2
    assert parse_subtitles('WEBVTT\n\n00:00.200 --> 00:02.020 align:start\n<b>Hello</b>')[0]['text'] == 'Hello'
    assert '00:00:02,320' in export_srt(cues, 2.12)


@pytest.mark.parametrize('text', ['1\n00:00:01,000 --> 00:00:00,000\nx',
    '1\n00:00:00,000 --> 00:00:02,000\nx\n\n2\n00:00:01,000 --> 00:00:03,000\ny',
    '1\n00:00:00,000 --> 00:99:02,000\nx', 'not subtitles'])
def test_invalid_subtitles(text):
    with pytest.raises(ValueError): parse_subtitles(text)


def test_rules_are_longest_nonrecursive_and_overrides_win():
    rules = [dict(source='2', replacement='二'), dict(source='2^n', replacement='2 的 n 次幂')]
    assert spoken_text(dict(text='2^n + 2'), rules) == '2 的 n 次幂 + 二'
    assert spoken_text(dict(text='2^n', spoken_text='二的恩次幂'), rules) == '二的恩次幂'


def test_audio_cache_ignores_timing_but_not_voice():
    cfg = Settings().model_dump()
    first = audio_key('Hello', cfg)
    assert first == audio_key('Hello', dict(cfg, offset=2.12, max_speed=1.25))
    assert first != audio_key('Hello', dict(cfg, seed=43))
    assert first != audio_key('Goodbye', cfg)
    ref = dict(cfg, mode='reference')
    assert audio_key('x', ref, 'a') != audio_key('x', ref, 'b')


def test_revision_and_approval(tmp_path):
    s = Store(tmp_path)
    p = s.create('test', Settings().model_dump())
    j = s.enqueue(p, dict(kind='preview'))
    j = s.patch_job(j['id'], status='completed')
    assert s.approve(p['id'], j)['approved_revision'] == 0
    p = s.update(p['id'], 0, dict(name='changed'))
    assert p['approved_revision'] is None
    with pytest.raises(Conflict): s.update(p['id'], 0, dict(name='stale'))
    with pytest.raises(Conflict): s.approve(p['id'], j)


def test_queue_guard_and_restart(tmp_path):
    s = Store(tmp_path);p = s.create('test', Settings().model_dump())
    j = s.enqueue(p, dict(kind='voice'))
    with pytest.raises(Conflict): s.enqueue(p, dict(kind='voice'))
    s.patch_job(j['id'], status='running');s.recover()
    assert s.job(j['id'])['status'] == 'interrupted'


def test_nonfinite_and_duplicate_validation():
    with pytest.raises(ValueError): Settings(offset=float('nan'))
    with pytest.raises(ValueError):
        ProjectEdit(revision=0,name='x',cues=[dict(id=1,start=0,end=1,text='x'),dict(id=1,start=2,end=3,text='y')])



def test_preview_duration_bounds():
    from app.models import JobRequest
    assert JobRequest(kind='preview', revision=0, duration=7200).duration == 7200
    for duration in (2, 7201, float('inf')):
        with pytest.raises(ValueError):
            JobRequest(kind='preview', revision=0, duration=duration)
