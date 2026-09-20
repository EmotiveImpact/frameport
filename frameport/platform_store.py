"""Durable queue and session operations, sharing the existing SQLite transactions.

One persistent volume and one supervisor. This is an authenticated private
workspace, not a shared multi-tenant service.
"""
import hashlib
import json
import secrets
import time
import uuid


class QueueFull(ValueError): pass
class Conflict(ValueError): pass


class PlatformStore:
    def migrate_platform(self):
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, job_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, expires REAL NOT NULL, credential TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts (bucket TEXT PRIMARY KEY, started REAL NOT NULL, attempts INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (job_id TEXT, revision INTEGER, created REAL, summary TEXT, PRIMARY KEY(job_id,revision));
                CREATE TABLE IF NOT EXISTS runtime (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,created);
            ''')

    @staticmethod
    def _new_record(request):
        now = time.time()
        return dict(id=uuid.uuid4().hex, created=now, updated=now, status='queued', stage='Queued', progress=0,
                    request=request, events=[], error=None, report=None, revision=0, cancelled=False, attempts=0)

    @staticmethod
    def _save(db, record):
        record['updated'] = time.time()
        db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)',
                   (record['id'], record['created'], record['updated'], record['status'], json.dumps(record)))

    def enqueue(self, request, limit=12, key=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if key:
                row = db.execute('SELECT j.record FROM requests r JOIN jobs j ON j.id=r.job_id WHERE r.key=?', (key,)).fetchone()
                if row:
                    previous = json.loads(row[0])
                    if previous['request'] != request:
                        raise Conflict('An idempotency key cannot be reused for different input.')
                    return previous
            if db.execute("SELECT count(*) FROM jobs WHERE status='queued'").fetchone()[0] >= limit:
                raise QueueFull('The conversion queue is full. Try again after a job completes.')
            record = self._new_record(request)
            self._save(db, record)
            if key:
                db.execute('INSERT OR REPLACE INTO requests VALUES(?,?)', (key, record['id']))
            return record

    def claim_next(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT record FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            record = json.loads(row[0])
            record.update(status='running', stage='Starting', attempts=record.get('attempts', 0) + 1)
            self._save(db, record)
            return record

    def interrupt(self, ident):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                return
            record = json.loads(row[0])
            if record['status'] != 'running':
                return
            retry = not record.get('cancelled') and record.get('attempts', 0) < 2
            record.update(status='queued' if retry else 'failed', stage='Queued' if retry else 'Interrupted',
                          error=None if retry else 'Worker interrupted twice. Retry the conversion.')
            self._save(db, record)

    def counts(self):
        with self.connect() as db:
            return {row[0]: row[1] for row in db.execute('SELECT status,count(*) FROM jobs GROUP BY status')}

    def queue_edits(self, ident, patches, expected, limit=12):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise Conflict('Project no longer exists.')
            record = json.loads(row[0])
            if record['status'] != 'completed' or (expected is not None and record['revision'] != expected):
                raise Conflict('This project changed in another tab. Reload before saving.')
            if db.execute("SELECT count(*) FROM jobs WHERE status='queued'").fetchone()[0] >= limit:
                raise QueueFull('The conversion queue is full.')
            self._record_revision(db, record)
            record.update(status='queued', stage='Queued', progress=0, cancelled=False, attempts=0,
                          revision=record['revision']+1, pendingPatches=patches, report=None, error=None)
            self._save(db, record)
            return record

    def _record_revision(self, db, record):
        report = record.get('report') or {}
        summary = dict(revision=record['revision'], finishedAt=record['updated'],
                       pages=len(report.get('pages', [])), visualPassed=report.get('visualPassed'),
                       componentCount=len(report.get('components', [])),
                       issues=len(report.get('issues', [])))
        db.execute('INSERT OR REPLACE INTO revisions VALUES(?,?,?,?)',
                   (record['id'], record['revision'], record['updated'], json.dumps(summary)))

    def record_revision(self, ident):
        with self.connect() as db:
            row = db.execute('SELECT record FROM jobs WHERE id=?', (ident,)).fetchone()
            if row:
                record = json.loads(row[0])
                if record['status'] == 'completed':
                    self._record_revision(db, record)

    def revisions(self, ident):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT summary FROM revisions WHERE job_id=? ORDER BY revision DESC', (ident,))]

    def rename(self, ident, name):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise Conflict('Project no longer exists.')
            record = json.loads(row[0]); record['request']['name'] = name
            self._save(db, record)
            return record

    def create_session(self, credential, days=7):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),
                       time.time()+days*86400, hashlib.sha256(credential.encode()).hexdigest()))
        return token

    def valid_session(self, token, credential):
        if not token or len(token) > 128:
            return False
        with self.connect() as db:
            row = db.execute('SELECT expires,credential FROM sessions WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return bool(row and row[0] > time.time() and row[1] == hashlib.sha256(credential.encode()).hexdigest())

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def allow_login(self, bucket):
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_attempts WHERE started < ?', (now-300,))
            row = db.execute('SELECT attempts FROM login_attempts WHERE bucket=?', (bucket,)).fetchone()
            count = row[0] if row else 0
            if count >= 20:
                return False
            db.execute('INSERT INTO login_attempts VALUES(?,?,1) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1', (bucket, now))
        return True
