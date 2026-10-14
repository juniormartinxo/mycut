"""Projects and durable jobs share one transactional SQLite store."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import DATA, configure


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


def uid():
    return uuid.uuid4().hex


def script(project):
    return '\n\n'.join(s['narration'].strip() for s in project['scenes'])


def script_hash(project):
    return hashlib.sha256(script(project).encode()).hexdigest()


@contextmanager
def connect():
    configure()
    db = sqlite3.connect(DATA / 'studio.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, document TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                mode TEXT NOT NULL, state TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL, snapshot TEXT NOT NULL, output TEXT,
                created_at REAL NOT NULL, updated_at REAL NOT NULL);
            -- Cover chat generations run beside a production, one of each per project.
            DROP INDEX IF EXISTS one_active_job_per_project;
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_production_per_project
                ON jobs(project_id) WHERE state IN ('queued','running') AND mode != 'cover';
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_cover_per_project
                ON jobs(project_id) WHERE state IN ('queued','running') AND mode = 'cover';
            CREATE TABLE IF NOT EXISTS worker_status (id INTEGER PRIMARY KEY CHECK(id=1), heartbeat REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS job_steps (
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                name TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL,
                updated_at REAL NOT NULL, PRIMARY KEY(job_id,name));
            CREATE TABLE IF NOT EXISTS job_inputs (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                snapshot TEXT NOT NULL);
            INSERT OR IGNORE INTO job_inputs SELECT id,snapshot FROM jobs;
            CREATE TABLE IF NOT EXISTS usage (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                step TEXT NOT NULL, attempt INTEGER NOT NULL, provider TEXT NOT NULL,
                requested_model TEXT NOT NULL, state TEXT NOT NULL, entries TEXT NOT NULL DEFAULT '[]',
                credits REAL, credits_estimated INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL, updated_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS usage_by_job ON usage(job_id, created_at);
        ''')


def project_row(row):
    if row is None:
        raise Missing('Projeto não encontrado.')
    return dict(json.loads(row['document']), id=row['id'], created_at=row['created_at'], updated_at=row['updated_at'])


def get_project(project_id):
    with connect() as db:
        return project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())


def all_projects():
    with connect() as db:
        return [project_row(row) for row in db.execute('SELECT * FROM projects ORDER BY updated_at DESC')]


def create_project(document, project_id=None):
    project_id = project_id or uid()
    document = dict(document, revision=1)
    now = time.time()
    with connect() as db:
        db.execute('INSERT INTO projects VALUES(?,?,?,?)', (project_id, json.dumps(document, ensure_ascii=False), now, now))
    (DATA / 'projects' / project_id).mkdir(parents=True, exist_ok=True)
    return get_project(project_id)


def update_project(project_id, changes, revision):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
        if current['revision'] != revision:
            raise Conflict('O projeto mudou em outra tela. Reabra-o antes de salvar.')
        if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('queued','running') AND mode != 'cover'", (project_id,)).fetchone():
            raise Conflict('Espere a produção terminar ou cancele-a antes de editar.')
        current.update(changes, revision=revision + 1)
        for key in ('id', 'created_at', 'updated_at'):
            current.pop(key, None)
        db.execute('UPDATE projects SET document=?, updated_at=? WHERE id=?',
                   (json.dumps(current, ensure_ascii=False), time.time(), project_id))
    return get_project(project_id)


def job_row(row, private=False):
    if row is None:
        raise Missing('Produção não encontrada.')
    job = dict(row)
    snapshot = json.loads(job.pop('snapshot'))
    job['revision'] = snapshot['revision']
    job['kind'] = snapshot.get('_kind', 'render')
    folder = DATA / 'projects' / job['project_id'] / 'renders' / job['id']
    job['materials'] = [] if job['kind'] == 'cover' else (['input.json'] if job['kind'] != 'render' else []) + [
        name for name in ('roteiro.txt', 'publicacao.txt', 'capa.png', 'narracao.wav')
        if job['state'] in ('succeeded', 'failed', 'cancelled') and (folder / name).is_file()]
    with connect() as db:
        job['steps'] = [dict(s) for s in db.execute('SELECT name,state,message,updated_at FROM job_steps WHERE job_id=? ORDER BY rowid', (job['id'],))]
    if private:
        job['snapshot'] = snapshot
    job['output'] = json.loads(job['output']) if job['output'] else None
    return job


def jobs(project_id=None, covers=False):
    """Productions only; cover chat generations are listed by cover_jobs and, with covers=True, for costs."""
    kinds = '' if covers else " AND mode != 'cover'"
    with connect() as db:
        rows = db.execute(f'SELECT * FROM jobs WHERE project_id=?{kinds} ORDER BY created_at DESC', (project_id,)) if project_id else db.execute(f'SELECT * FROM jobs WHERE 1{kinds} ORDER BY created_at DESC LIMIT 100')
        return [job_row(row) for row in rows]


def cover_jobs(project_id, private=False):
    with connect() as db:
        rows = db.execute("SELECT * FROM jobs WHERE project_id=? AND mode='cover' ORDER BY created_at", (project_id,))
        return [job_row(row, private) for row in rows]


def get_job(job_id, private=False):
    with connect() as db:
        return job_row(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone(), private)


def enqueue(project_id, mode, revision, kind='render', settings=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        project = project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
        if project['revision'] != revision:
            raise Conflict('Salve e atualize o projeto antes de produzir.')
        if kind in ('render', 'voice') and any(not s['narration'].strip() or not s['title'].strip() for s in project['scenes']):
            raise Conflict('Preencha o título e a narração de todas as cenas.')
        if kind == 'scenes' and any(not s['narration'].strip() for s in project['scenes']):
            raise Conflict('Gere ou salve o roteiro antes de criar as cenas com agentes.')
        if len(script(project).split()) > 500:
            raise Conflict('Use até 500 palavras por Short nesta versão.')
        if kind == 'render' and mode == 'final' and not project.get('audio'):
            raise Conflict('Importe a narração antes de gerar o vídeo final.')
        if kind == 'render' and project.get('audio') and project['audio']['script_hash'] != script_hash(project):
            raise Conflict('O roteiro mudou. Confira a narração na aba Áudio e confirme a correspondência.')
        if kind in ('pipeline', 'plan') and not project.get('brief', '').strip():
            raise Conflict('Informe a pauta ou o link na aba Pauta para iniciar os agentes.')
        if kind != 'render':
            project['_kind'] = kind
            project['_agents'] = (settings or {}).get('agents', {})
            project['_voice'] = {k: v for k,v in (settings or {}).get('elevenlabs', {}).items() if k != 'api_key'}
        job_id, now = uid(), time.time()
        try:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (job_id, project_id, mode, 'queued', 0, 'Aguardando o worker', json.dumps(project, ensure_ascii=False), None, now, now))
            db.execute('INSERT INTO job_inputs VALUES(?,?)', (job_id, json.dumps(project, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise Conflict('Este projeto já tem uma produção em andamento.') from exc
    return get_job(job_id)


def enqueue_cover(project_id, request, job_id=None):
    """A cover chat turn: snapshot of the project plus the message, never blocked by edits."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        project = project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
        project['_kind'] = 'cover'
        project['_cover'] = request
        job_id, now = job_id or uid(), time.time()
        try:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (job_id, project_id, 'cover', 'queued', 0, 'Aguardando o worker', json.dumps(project, ensure_ascii=False), None, now, now))
            db.execute('INSERT INTO job_inputs VALUES(?,?)', (job_id, json.dumps(project, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise Conflict('Espere a imagem atual ficar pronta antes de enviar outra mensagem.') from exc
    return get_job(job_id)


def job_input(job_id):
    with connect() as db:
        row = db.execute('SELECT snapshot FROM job_inputs WHERE job_id=?', (job_id,)).fetchone()
        if row is None:
            raise Missing('Entrada da produção não encontrada.')
        return json.loads(row['snapshot'])


def claim(covers=False):
    """Productions and cover generations are claimed by separate worker lanes."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute(f"SELECT * FROM jobs WHERE state='queued' AND mode {'=' if covers else '!='} 'cover' ORDER BY created_at LIMIT 1").fetchone()
        if row is None:
            return None
        db.execute("UPDATE jobs SET state='running', message='Preparando produção', updated_at=? WHERE id=?", (time.time(), row['id']))
        return job_row(row, True)


def progress(job_id, percent, message):
    with connect() as db:
        db.execute("UPDATE jobs SET progress=?, message=?, updated_at=? WHERE id=? AND state='running'", (percent, message, time.time(), job_id))


def finish(job_id, state, message, output=None):
    with connect() as db:
        db.execute("UPDATE jobs SET state=?, progress=?, message=?, output=?, updated_at=? WHERE id=? AND state IN ('running','queued')",
                   (state, 100 if state == 'succeeded' else 0, message, json.dumps(output) if output else None, time.time(), job_id))


def cancel(job_id):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        job = job_row(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
        if job['state'] not in ('running', 'queued'):
            raise Conflict('Esta produção já foi encerrada.')
        db.execute("UPDATE jobs SET state='cancelled', message='Produção cancelada', updated_at=? WHERE id=?", (time.time(), job_id))
    return get_job(job_id)


def heartbeat():
    with connect() as db:
        db.execute('INSERT INTO worker_status VALUES(1,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat', (time.time(),))


def worker_online():
    with connect() as db:
        row = db.execute('SELECT heartbeat FROM worker_status WHERE id=1').fetchone()
        return bool(row and time.time() - row['heartbeat'] < 15)


def recover():
    with connect() as db:
        db.execute("UPDATE jobs SET state='failed', message='Worker reiniciado durante a produção. Gere uma nova versão para tentar novamente.', updated_at=? WHERE state='running'", (time.time(),))


def step(job_id, name, state, message):
    with connect() as db:
        db.execute('INSERT INTO job_steps VALUES(?,?,?,?,?) ON CONFLICT(job_id,name) DO UPDATE SET state=excluded.state,message=excluded.message,updated_at=excluded.updated_at',
                   (job_id, name, state, message, time.time()))


def checkpoint(job_id, changes):
    """Only the active job can publish its intermediate artifacts to its project."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['state'] != 'running':
            raise Conflict('A produção foi encerrada antes de salvar esta etapa.')
        snapshot = json.loads(row['snapshot'])
        current = project_row(db.execute('SELECT * FROM projects WHERE id=?', (row['project_id'],)).fetchone())
        if current['revision'] != snapshot['revision']:
            raise Conflict('A revisão mudou durante a produção.')
        current.update(changes, revision=current['revision']+1)
        snapshot.update(changes, revision=current['revision'])
        document = {k: v for k,v in current.items() if k not in ('id','created_at','updated_at')}
        db.execute('UPDATE projects SET document=?,updated_at=? WHERE id=?', (json.dumps(document,ensure_ascii=False),time.time(),current['id']))
        db.execute('UPDATE jobs SET snapshot=?,updated_at=? WHERE id=?', (json.dumps(snapshot,ensure_ascii=False),time.time(),job_id))
    return get_job(job_id, private=True)


def usage_start(usage_id, job_id, step, attempt, provider, model):
    """Recorded before the call, so a killed production still shows that it spent something."""
    with connect() as db:
        db.execute("INSERT INTO usage(id,job_id,step,attempt,provider,requested_model,state,created_at,updated_at) "
                   "VALUES(?,?,?,?,?,?, 'running', ?, ?)", (usage_id, job_id, step, attempt, provider, model or '', time.time(), time.time()))


def usage_finish(usage_id, state, entries=None, credits=None, estimated=False):
    with connect() as db:
        db.execute("UPDATE usage SET state=?, entries=?, credits=?, credits_estimated=?, updated_at=? WHERE id=? AND state='running'",
                   (state, json.dumps(entries or []), credits, int(estimated), time.time(), usage_id))


def usage_rows(project_id):
    with connect() as db:
        return [dict(row) for row in db.execute(
            'SELECT usage.* FROM usage JOIN jobs ON jobs.id=usage.job_id WHERE jobs.project_id=? ORDER BY usage.created_at',
            (project_id,))]
