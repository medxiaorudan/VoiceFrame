import json
import sqlite3
import time
import uuid
from pathlib import Path


class Conflict(Exception):
    pass


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'voiceframe.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    status TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
            ''')

    def connect(self):
        return sqlite3.connect(self.db, timeout=30)

    def project(self, pid):
        with self.connect() as db:
            row = db.execute('SELECT body FROM projects WHERE id=?', (pid,)).fetchone()
        if not row:
            raise KeyError('Project not found.')
        return json.loads(row[0])

    def projects(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM projects ORDER BY rowid DESC')]

    def delete(self, pid):
        self.project(pid)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT count(*) FROM jobs WHERE project_id=? AND status IN ('queued','running')", (pid,)).fetchone()[0]:
                raise Conflict('Cancel active jobs before deleting the project.')
            db.execute('DELETE FROM jobs WHERE project_id=?', (pid,))
            db.execute('DELETE FROM projects WHERE id=?', (pid,))

    def create(self, name, settings):
        p = dict(id=uuid.uuid4().hex, name=name, revision=0, created=time.time(), settings=settings,
                 cues=[], video=None, reference=None, approved_revision=None)
        with self.connect() as db:
            db.execute('INSERT INTO projects VALUES (?, ?)', (p['id'], json.dumps(p)))
        (self.root / p['id']).mkdir()
        return p

    def update(self, pid, revision, fields):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM projects WHERE id=?', (pid,)).fetchone()
            if not row:
                raise KeyError('Project not found.')
            p = json.loads(row[0])
            if p['revision'] != revision:
                raise Conflict('Project changed. Reload before saving; your edits were not applied.')
            p.update(fields)
            p['revision'] += 1
            p['approved_revision'] = None
            db.execute('UPDATE projects SET body=? WHERE id=?', (json.dumps(p), pid))
        return p

    def approve(self, pid, job):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM projects WHERE id=?', (pid,)).fetchone()
            if not row:
                raise KeyError('Project not found.')
            p = json.loads(row[0])
            if job['project_id'] != pid or job['kind'] != 'preview' or job['status'] != 'completed' or job['snapshot']['revision'] != p['revision']:
                raise Conflict('Approve a completed preview of the current project revision.')
            p['approved_revision'] = p['revision']
            db.execute('UPDATE projects SET body=? WHERE id=?', (json.dumps(p), pid))
        return p

    def enqueue(self, project, request):
        j = dict(id=uuid.uuid4().hex, project_id=project['id'], kind=request['kind'],
                 snapshot=project, request=request, status='queued', progress=0,
                 stage='Queued', error=None, result=None, cancelled=False, created=time.time())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute("SELECT count(*) FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project['id'],)).fetchone()[0]
            if active:
                raise Conflict('This project already has an active job. Wait or cancel it first.')
            db.execute('INSERT INTO jobs VALUES (?, ?, ?, ?, ?)', (j['id'], project['id'], 'queued', json.dumps(j), j['created']))
        return j

    def job(self, jid):
        with self.connect() as db:
            row = db.execute('SELECT body FROM jobs WHERE id=?', (jid,)).fetchone()
        if not row:
            raise KeyError('Job not found.')
        return json.loads(row[0])

    def jobs(self, pid):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 30', (pid,))]

    def patch_job(self, jid, **fields):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM jobs WHERE id=?', (jid,)).fetchone()
            if not row:
                raise KeyError('Job not found.')
            j = json.loads(row[0])
            j.update(fields)
            db.execute('UPDATE jobs SET status=?, body=? WHERE id=?', (j['status'], json.dumps(j), jid))
        return j

    def next_job(self):
        with self.connect() as db:
            row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        return row[0] if row else None

    def recover(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM jobs WHERE status='running'")]
        for jid in ids:
            self.patch_job(jid, status='interrupted', error='Server restarted. Retry to reuse completed audio.')
