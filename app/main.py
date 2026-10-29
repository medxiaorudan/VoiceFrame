import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import time
import uuid
from filelock import FileLock, Timeout
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engines import available, engine_name
from .jobs import Worker
from .media import normalize_reference, probe
from .models import Settings, ProjectEdit, JobRequest
from .store import Store, Conflict
from .subtitles import parse_subtitles, spoken_text


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class Login(BaseModel):
    token: str = Field(max_length=256)


class Approval(BaseModel):
    job_id: str


def create_app(data_dir=None, worker_enabled=True):
    root = Path(data_dir or os.getenv('VOICEFRAME_DATA', 'data')).resolve()
    store = Store(root)
    worker = Worker(store)
    token = os.getenv('VOICEFRAME_ACCESS_KEY', '')
    public = os.getenv('VOICEFRAME_PUBLIC', '0') == '1'
    if public and len(token) < 32:
        raise RuntimeError('Public mode requires VOICEFRAME_ACCESS_KEY with at least 32 characters.')
    login_attempts = {}
    def cookie_value():
        expiry = str(int(time.time()) + 86400)
        signature = hmac.new(token.encode(), expiry.encode(), hashlib.sha256).hexdigest()
        return expiry+'.'+signature
    def authenticated(value):
        try:
            expiry, signature = value.split('.')
            return int(expiry) > time.time() and hmac.compare_digest(signature, hmac.new(token.encode(), expiry.encode(), hashlib.sha256).hexdigest())
        except (ValueError, AttributeError):
            return False

    @asynccontextmanager
    async def lifespan(app):
        lock = FileLock(str(root/'worker.lock'))
        if worker_enabled:
            try:
                lock.acquire(timeout=0)
            except Timeout:
                raise RuntimeError('Another VoiceFrame process owns this data folder. Use one server worker.') from None
            worker.start()
        yield
        worker.stop.set()
        if worker.thread:
            worker.thread.join(timeout=2)
        if worker_enabled:
            lock.release()

    app = FastAPI(title='VoiceFrame', version='0.1.0', lifespan=lifespan)
    app.state.store, app.state.worker = store, worker

    @app.middleware('http')
    async def boundary(request, call_next):
        host = request.url.hostname or ''
        allowed = os.getenv('VOICEFRAME_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1,testserver').split(',')
        if '*' not in allowed and host not in allowed:
            return JSONResponse({'detail': 'Host not allowed. Configure VOICEFRAME_ALLOWED_HOSTS.'}, 400)
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Cross-origin writes are not allowed.'}, 403)
        protected = request.url.path.startswith(('/api/', '/media/')) and request.url.path not in ('/api/session', '/api/login')
        if token and protected and not authenticated(request.cookies.get('voiceframe_session')):
            return JSONResponse({'detail': 'Sign in to access this workspace.'}, 401)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.url.path.startswith(('/api/', '/media/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': str(exc)}, 404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, 409)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, 422)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, exc):
        return JSONResponse({'detail': str(exc)}, 422)

    @app.get('/api/session')
    def session(request: Request):
        return dict(required=bool(token), authenticated=not token or authenticated(request.cookies.get('voiceframe_session')))

    @app.post('/api/login')
    def login(body: Login, request: Request):
        key = request.client.host
        now = time.time()
        attempts = [t for t in login_attempts.get(key, []) if now-t < 60]
        if len(attempts) >= 10:
            raise HTTPException(429, 'Too many attempts. Try again in a minute.')
        if not token or not secrets.compare_digest(body.token, token):
            login_attempts[key] = attempts+[now]
            raise HTTPException(401, 'Invalid access key.')
        login_attempts.pop(key, None)
        response = JSONResponse(dict(ok=True))
        response.set_cookie('voiceframe_session', cookie_value(), httponly=True, secure=public, samesite='strict', max_age=86400)
        return response

    @app.post('/api/logout')
    def logout():
        response = JSONResponse(dict(ok=True))
        response.delete_cookie('voiceframe_session')
        return response

    @app.get('/api/system')
    def system():
        return dict(platform=platform.system(), architecture=platform.machine(), engine=engine_name(),
            ffmpeg=bool(shutil.which('ffmpeg') or os.getenv('FFMPEG_PATH')),
            ffprobe=bool(shutil.which('ffprobe') or os.getenv('FFPROBE_PATH')),
            mlx=available('mlx_audio'), torch=available('qwen_tts'), asr=available('faster_whisper'),
            ocr=bool(shutil.which('tesseract')), version='0.1.0')

    @app.get('/api/projects')
    def projects():
        return store.projects()

    @app.post('/api/projects', status_code=201)
    def create(body: NewProject):
        return store.create(body.name, Settings().model_dump())

    @app.get('/api/projects/{pid}')
    def get(pid: str):
        return store.project(pid)

    @app.delete('/api/projects/{pid}')
    def delete(pid: str):
        store.delete(pid)
        shutil.rmtree(root/pid, ignore_errors=True)
        return dict(ok=True)

    @app.put('/api/projects/{pid}')
    def edit(pid: str, body: ProjectEdit):
        p = store.project(pid)
        cues = [c.model_dump() for c in body.cues]
        if p['video'] and cues and cues[-1]['end'] > p['video']['duration']+.1:
            raise ValueError('Subtitle times exceed video duration.')
        return store.update(pid, body.revision, dict(name=body.name, cues=cues, settings=body.settings.model_dump()))

    async def upload(file, folder, limit, suffix):
        destination = folder/(uuid.uuid4().hex+suffix)
        size = 0
        digest = hashlib.sha256()
        try:
            with destination.open('wb') as output:
                while chunk := await file.read(1024*1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, f'File exceeds {limit//1048576} MB limit.')
                    digest.update(chunk)
                    output.write(chunk)
            if not size:
                raise ValueError('Uploaded file is empty.')
            return destination, digest.hexdigest()
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.post('/api/projects/{pid}/video')
    async def video(pid: str, file: UploadFile = File(...), revision: int = Form(...)):
        p = store.project(pid)
        if revision != p['revision']:
            raise Conflict('Reload the project before uploading.')
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in ('.mp4', '.mov', '.mkv', '.webm', '.m4v'):
            raise ValueError('Upload MP4, MOV, MKV, WEBM or M4V.')
        name = Path(file.filename).name
        dest, sha = await upload(file, root/pid, int(os.getenv('VOICEFRAME_MAX_UPLOAD_MB', '1024'))*1048576, suffix)
        try:
            import asyncio
            meta = await asyncio.to_thread(probe, dest)
            if not any(s['type'] == 'video' for s in meta['streams']):
                raise ValueError('File contains no video stream.')
            return store.update(pid, revision, dict(video=dict(file=dest.name, name=name, sha256=sha, **meta), cues=[]))
        except Exception:
            dest.unlink(missing_ok=True)
            raise

    @app.post('/api/projects/{pid}/subtitles')
    async def subtitles(pid: str, file: UploadFile = File(...), revision: int = Form(...)):
        store.project(pid)
        content = await file.read(2*1048576+1)
        await file.close()
        if len(content) > 2*1048576:
            raise HTTPException(413, 'Subtitle file exceeds 2 MB.')
        cues = parse_subtitles(content.decode('utf-8-sig'))
        p = store.project(pid)
        if p['video'] and cues[-1]['end'] > p['video']['duration']+.1:
            raise ValueError('Subtitles exceed video duration. Check that they belong to this video.')
        return store.update(pid, revision, dict(cues=cues))

    @app.post('/api/projects/{pid}/reference')
    async def reference(pid: str, file: UploadFile = File(...), revision: int = Form(...)):
        store.project(pid)
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in ('.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4'):
            raise ValueError('Upload WAV, MP3, M4A, FLAC, OGG or MP4 reference.')
        dest, _ = await upload(file, root/pid, 30*1048576, suffix)
        target = root/pid/(uuid.uuid4().hex+'.wav')
        try:
            import asyncio
            await asyncio.to_thread(normalize_reference, dest, target)
            sha = hashlib.sha256(target.read_bytes()).hexdigest()
            return store.update(pid, revision, dict(reference=dict(file=target.name, sha256=sha)))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            dest.unlink(missing_ok=True)

    @app.post('/api/projects/{pid}/jobs', status_code=202)
    def job(pid: str, body: JobRequest):
        p = store.project(pid)
        if p['revision'] != body.revision:
            raise Conflict('Save or reload the latest project before generating.')
        if body.kind != 'voice' and not p['video']:
            raise ValueError('Upload a video first.')
        if body.kind == 'final' and p['approved_revision'] != p['revision']:
            raise Conflict('Generate and approve a preview with the current settings first.')
        if body.kind in ('voice', 'preview', 'final') and p['settings']['mode'] == 'reference' and (not p['reference'] or not p['settings']['reference_text'].strip()):
            raise ValueError('Reference audio and its exact transcript are required.')
        if body.kind == 'extract' and not any(s['type']=='subtitle' and s['index']==body.stream_index for s in p['video']['streams']):
            raise ValueError('Choose a detected subtitle stream.')
        return store.enqueue(p, body.model_dump())

    @app.get('/api/projects/{pid}/jobs')
    def jobs(pid: str):
        store.project(pid)
        return [{k:v for k,v in j.items() if k not in ('snapshot',)} for j in store.jobs(pid)]

    @app.post('/api/jobs/{jid}/cancel')
    def cancel(jid: str):
        j = store.job(jid)
        if j['status'] not in ('queued', 'running'):
            return dict(ok=True)
        fields = dict(cancelled=True)
        if j['status'] == 'queued':
            fields['status'] = 'cancelled'
        store.patch_job(jid, **fields)
        return dict(ok=True)

    @app.post('/api/jobs/{jid}/retry', status_code=202)
    def retry(jid: str):
        j = store.job(jid)
        if j['status'] not in ('failed', 'cancelled', 'interrupted'):
            raise Conflict('Only failed, cancelled or interrupted jobs can be retried.')
        p = store.project(j['project_id'])
        if p['revision'] != j['snapshot']['revision']:
            raise Conflict('Settings changed. Create a new job using current settings instead.')
        return store.enqueue(p, j['request'])

    @app.post('/api/projects/{pid}/approve')
    def approve(pid: str, body: Approval):
        return store.approve(pid, store.job(body.job_id))

    @app.get('/media/{pid}/{path:path}')
    def media(pid: str, path: str):
        store.project(pid)
        base = (root/pid).resolve()
        dest = (base/path).resolve()
        if not dest.is_relative_to(base) or not dest.is_file() or dest.suffix.lower() not in ('.mp4','.m4v','.mov','.mkv','.webm','.wav','.srt','.json'):
            raise HTTPException(404, 'Media not found.')
        return FileResponse(dest, filename=dest.name, content_disposition_type='inline')

    static = Path(__file__).parent/'static'
    app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
    return app


app = create_app(worker_enabled=os.getenv('VOICEFRAME_NO_WORKER') != '1')
