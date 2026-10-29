import io
import wave
from fastapi.testclient import TestClient
from app.main import create_app


def project(client):
    return client.post('/api/projects', json={'name':'Math lesson'}).json()


def test_api_conflict_subtitles_and_xss(tmp_path):
    with TestClient(create_app(tmp_path, False)) as c:
        p=project(c)
        upload=c.post(f"/api/projects/{p['id']}/subtitles", files={'file':('test.srt',b'1\n00:00:00,200 --> 00:00:01,200\nHello')},data={'revision':0})
        assert upload.status_code==200
        p=upload.json()
        body={k:p[k] for k in ('revision','name','settings','cues')}
        body['name']='<img src=x onerror=alert(1)>'
        assert c.put(f"/api/projects/{p['id']}",json=body).status_code==200
        assert c.put(f"/api/projects/{p['id']}",json=body).status_code==409
        assert c.get('/').headers['content-security-policy'].startswith("default-src 'self'")
        assert c.post('/api/projects',headers={'Origin':'https://evil.example'},json={'name':'x'}).status_code==403


def test_media_traversal_and_invalid_upload(tmp_path):
    with TestClient(create_app(tmp_path, False)) as c:
        p=project(c)
        assert c.get(f"/media/{p['id']}/%2e%2e/voiceframe.sqlite3").status_code==404
        r=c.post(f"/api/projects/{p['id']}/video",files={'file':('script.html',b'text')},data={'revision':0})
        assert r.status_code==422
        assert c.get('/api/projects/not-real').status_code==404


def test_final_requires_current_approval(tmp_path):
    app=create_app(tmp_path, False)
    with TestClient(app) as c:
        p=project(c)
        p=app.state.store.update(p['id'],0,{'video':{'duration':10,'file':'fake.mp4'}})
        assert c.post(f"/api/projects/{p['id']}/jobs",json={'kind':'final','revision':p['revision']}).status_code==409


def test_authentication_protects_api_and_media(tmp_path,monkeypatch):
    monkeypatch.setenv('VOICEFRAME_ACCESS_KEY','a'*32)
    with TestClient(create_app(tmp_path,False)) as c:
        assert c.get('/api/projects').status_code==401
        assert c.get('/media/fake/file.wav').status_code==401
        assert c.post('/api/login',json={'token':'wrong'}).status_code==401
        response=c.post('/api/login',json={'token':'a'*32})
        assert response.status_code==200 and 'HttpOnly' in response.headers['set-cookie']
        assert c.get('/api/projects').status_code==200
        c.post('/api/logout')
        assert c.get('/api/projects').status_code==401


def test_public_requires_strong_key(tmp_path,monkeypatch):
    monkeypatch.setenv('VOICEFRAME_PUBLIC','1')
    monkeypatch.delenv('VOICEFRAME_ACCESS_KEY',raising=False)
    import pytest
    with pytest.raises(RuntimeError): create_app(tmp_path,False)


def test_cancel_queued_job(tmp_path):
    with TestClient(create_app(tmp_path, False)) as c:
        p=project(c)
        r=c.post(f"/api/projects/{p['id']}/jobs",json={'kind':'voice','revision':0})
        assert r.status_code==202
        jid=r.json()['id']
        assert c.post(f'/api/jobs/{jid}/cancel').status_code==200
        assert c.get(f"/api/projects/{p['id']}/jobs").json()[0]['status']=='cancelled'


def test_delete_guard(tmp_path):
    with TestClient(create_app(tmp_path,False)) as c:
        p=project(c)
        j=c.post(f"/api/projects/{p['id']}/jobs",json={'kind':'voice','revision':0}).json()
        assert c.delete(f"/api/projects/{p['id']}").status_code==409
        c.post(f"/api/jobs/{j['id']}/cancel")
        assert c.delete(f"/api/projects/{p['id']}").status_code==200
        assert c.get(f"/api/projects/{p['id']}").status_code==404
