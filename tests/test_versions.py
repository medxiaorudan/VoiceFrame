from fastapi.testclient import TestClient
from app.main import create_app
from app.models import Settings


def completed(store, p, kind='preview'):
    job = store.enqueue(p, dict(kind=kind, revision=p['revision']))
    return store.patch_job(job['id'], status='completed', result={'video':f"jobs/{job['id']}/dubbed.mp4"})


def test_history_keeps_stars_approved_active_and_cleans_files(tmp_path):
    app = create_app(tmp_path, False)
    store = app.state.store
    p = store.create('Versions', Settings().model_dump())
    jobs = [completed(store, p) for _ in range(32)]
    approved, starred, removed = jobs[:3]
    store.approve(p['id'], approved)
    folder = tmp_path / p['id'] / 'jobs' / removed['id']
    folder.mkdir(parents=True); (folder/'dubbed.mp4').write_bytes(b'video')
    cache = tmp_path / p['id'] / 'cache'; cache.mkdir(); (cache/'keep.wav').write_bytes(b'audio')
    with TestClient(app) as c:
        assert len(c.get(f"/api/projects/{p['id']}/jobs").json()) == 32
        assert c.patch(f"/api/jobs/{starred['id']}/favorite", json={'favorite':True}).status_code == 200
        assert store.job(starred['id'])['favorite']
        active = store.enqueue(p, dict(kind='voice', revision=p['revision']))
        for protected in (approved, starred, active):
            assert c.delete(f"/api/jobs/{protected['id']}").status_code == 409
        response = c.delete(f"/api/projects/{p['id']}/jobs/history")
        assert response.status_code == 200
        assert len(response.json()['deleted']) == 30
        assert not folder.exists()
        assert (cache/'keep.wav').exists()
        assert {j['id'] for j in store.jobs(p['id'])} == {approved['id'], starred['id'], active['id']}
        c.patch(f"/api/jobs/{starred['id']}/favorite", json={'favorite':False})
        assert c.delete(f"/api/jobs/{starred['id']}").status_code == 200
        assert c.delete(f"/api/jobs/{starred['id']}").status_code == 404


def test_selected_old_preview_restores_export_snapshot(tmp_path):
    app = create_app(tmp_path, False); store = app.state.store
    p = store.create('Versions', Settings().model_dump())
    p = store.update(p['id'], 0, dict(video={'file':'old.mp4','duration':5}, cues=[{'id':1,'start':0,'end':1,'text':'old','spoken_text':''}]))
    old = completed(store, p)
    p = store.update(p['id'], p['revision'], dict(settings=Settings(speaker='Ryan').model_dump(), cues=[], video={'file':'new.mp4','duration':10}))
    newer = completed(store, p)
    with TestClient(app) as c:
        url = f"/api/projects/{p['id']}/approve"
        assert c.post(url,json={'job_id':old['id']}).status_code == 409
        assert c.post(url,json={'job_id':old['id'],'revision':0,'restore':True}).status_code == 409
        other = store.create('Other', Settings().model_dump())
        assert c.post(f"/api/projects/{other['id']}/approve",json={'job_id':old['id'],'restore':True}).status_code == 409
        r = c.post(url,json={'job_id':old['id'],'revision':p['revision'],'restore':True})
        assert r.status_code == 200, r.text
        restored = r.json()
        assert restored['approved_job_id'] == old['id']
        assert restored['approved_revision'] == restored['revision']
        for key in ('settings','cues','video','reference'):
            assert restored[key] == old['snapshot'].get(key)
        r = c.post(f"/api/projects/{p['id']}/jobs",json={'kind':'final','revision':restored['revision']})
        assert r.status_code == 202, r.text
        final = store.job(r.json()['id'])
        assert final['snapshot']['settings']['speaker'] == 'Dylan'
        assert final['snapshot']['video']['file'] == 'old.mp4'
        assert final['snapshot']['approved_job_id'] == old['id']
        assert c.post(url,json={'job_id':newer['id'],'restore':True}).status_code == 409
