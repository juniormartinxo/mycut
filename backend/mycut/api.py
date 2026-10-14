import os
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from PIL import UnidentifiedImageError, Image
from . import store, media
from .config import ROOT, DATA, UPLOAD_LIMIT
from .models import CreateProject, ProjectInput, RenderRequest, AgentRunRequest, AgentSettings, AgentTestRequest, ElevenConnect, ElevenSettings
from . import integrations, elevenlabs, bridge, agent_models, agent_tests
from .seed import blank, claude, initialize_example


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    if os.environ.get('MYCUT_SEED', '1') == '1':
        initialize_example()
    yield


app = FastAPI(title='MyCut Studio', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver', 'api'])
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type'])


@app.middleware('http')
async def local_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        allowed = {'http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8321', 'http://127.0.0.1:8321', 'http://testserver'}
        if origin not in allowed:
            return JSONResponse({'detail': 'Origem não autorizada para alterar projetos.'}, status_code=403)
    return await call_next(request)


@app.exception_handler(store.Missing)
async def missing(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=404)


@app.exception_handler(store.Conflict)
async def conflict(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=409)


@app.exception_handler(ValueError)
async def invalid_operation(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=422)


@app.exception_handler(RequestValidationError)
async def validation(request, exc):
    # Pydantic's default input field could echo an invalid API key.
    return JSONResponse({'detail': [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]}, status_code=422)


def present(project):
    project = dict(project)
    project.setdefault('brief', '')
    project['jobs'] = store.jobs(project['id'])
    for key in ['audio', 'cover']:
        if project.get(key):
            project[key] = {k: v for k, v in project[key].items() if k not in ('path', 'alignment')}
            project[key]['url'] = f'/api/projects/{project["id"]}/assets/{key}?v={project["revision"]}'
    project['audio_matches_script'] = bool(project.get('audio') and project['audio']['script_hash'] == store.script_hash(project))
    return project


@app.get('/api/health')
def health():
    return {'status': 'ok', 'worker_online': store.worker_online(), 'ffmpeg': bool(shutil.which('ffmpeg'))}


@app.get('/api/projects')
def projects():
    return [present(p) for p in store.all_projects()]


@app.post('/api/projects', status_code=201)
def create(body: CreateProject):
    if body.automation != 'none':
        if not body.brief.strip():
            raise ValueError('Informe a pauta ou link para iniciar os agentes.')
        settings = ready_for(body.automation)
    document = claude() if body.template == 'claude-cloud' else blank(body.title)
    document['title'] = body.title.strip() or 'Novo Short'
    document['brief'] = body.brief
    result = store.create_project(document)
    if body.automation != 'none':
        store.enqueue(result['id'], 'final', result['revision'], body.automation, settings)
    return present(result)


def ready_for(kind):
    settings = integrations.read()
    if kind in ('pipeline', 'plan'):
        bridge.require(v['provider'] for v in settings['agents'].values())
    if kind in ('pipeline', 'voice'):
        integrations.require_voice()
    return settings


@app.get('/api/integrations')
def integration_status():
    return integrations.public()


@app.put('/api/integrations/agents')
def configure_agents(body: AgentSettings):
    for choice in body.model_dump().values():
        agent_models.validate(choice)
    return integrations.save_section('agents', body.model_dump())


@app.post('/api/integrations/agents/models/refresh', status_code=202)
def refresh_agent_models():
    bridge.require([])
    if bridge.status().get('protocol', 0) < 2:
        raise ValueError('Reinicie bash scripts/agents.sh no WSL para carregar os modelos.')
    (bridge.BRIDGE / 'refresh-models').touch()
    return {'message': 'Lista será atualizada quando o executor estiver livre.'}


@app.post('/api/integrations/agents/tests', status_code=202)
def test_agent(body: AgentTestRequest):
    return agent_tests.start(body.model_dump())


@app.get('/api/integrations/agents/tests')
def latest_agent_tests():
    return agent_tests.latest()


@app.get('/api/integrations/agents/tests/{test_id}')
def agent_test(test_id: str):
    return agent_tests.get(test_id)


@app.post('/api/integrations/agents/tests/{test_id}/cancel')
def cancel_agent_test(test_id: str):
    return agent_tests.cancel(test_id)


@app.post('/api/integrations/elevenlabs/connect')
def connect_elevenlabs(body: ElevenConnect):
    key = body.api_key.get_secret_value().strip()
    catalog = elevenlabs.catalog(key)
    # Changing account clears the selected voice; never silently use another voice.
    changed = integrations.read()['elevenlabs']['api_key'] != key
    values = {'api_key': key}
    if changed:
        values.update(voice_id='', voice_name='')
    return {'settings': integrations.save_section('elevenlabs', values), **catalog}


@app.get('/api/integrations/elevenlabs/catalog')
def eleven_catalog():
    key = integrations.read()['elevenlabs']['api_key']
    if not key:
        raise ValueError('Conecte sua chave da ElevenLabs primeiro.')
    return elevenlabs.catalog(key)


@app.put('/api/integrations/elevenlabs')
def configure_elevenlabs(body: ElevenSettings):
    catalog = eleven_catalog()
    if body.voice_id not in {v['id'] for v in catalog['voices']} or body.model_id not in {m['id'] for m in catalog['models']}:
        raise ValueError('Selecione uma voz e um modelo disponíveis na sua conta.')
    values = body.model_dump()
    values['voice_name'] = next(v['name'] for v in catalog['voices'] if v['id'] == body.voice_id)
    return integrations.save_section('elevenlabs', values)


@app.post('/api/integrations/elevenlabs/disconnect')
def disconnect_elevenlabs():
    return integrations.save_section('elevenlabs', {'api_key': '', 'voice_id': '', 'voice_name': ''})


@app.post('/api/projects/{project_id}/run', status_code=202)
def run_agents(project_id: str, body: AgentRunRequest):
    settings = ready_for(body.kind)
    return store.enqueue(project_id, body.mode, body.revision, body.kind, settings)


@app.get('/api/projects/{project_id}')
def project(project_id: str):
    return present(store.get_project(project_id))


@app.put('/api/projects/{project_id}')
def update(project_id: str, body: ProjectInput):
    values = body.model_dump()
    revision = values.pop('revision')
    return present(store.update_project(project_id, values, revision))


@app.post('/api/projects/{project_id}/assets/{kind}')
def upload(project_id: str, kind: str, file: UploadFile, revision: int = Query(ge=1)):
    project = store.get_project(project_id)
    if kind not in ('audio', 'cover'):
        raise HTTPException(404, 'Tipo de material não encontrado.')
    if kind == 'audio' and any(not s['narration'].strip() for s in project['scenes']):
        raise HTTPException(422, 'Preencha e salve a narração de todas as cenas antes de importar a voz.')
    extension = Path(file.filename or '').suffix.lower()
    allowed = {'.mp3', '.m4a', '.wav', '.flac', '.ogg'} if kind == 'audio' else {'.png', '.jpg', '.jpeg', '.webp'}
    if extension not in allowed:
        raise HTTPException(422, 'Formato não aceito. Use áudio MP3/WAV/M4A/FLAC/OGG ou capa PNG/JPG/WebP.')
    folder = DATA / 'projects' / project_id / 'uploads'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (store.uid() + extension)
    saved = target
    try:
        size = 0
        with target.open('xb') as stream:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > (UPLOAD_LIMIT if kind == 'audio' else 15*1024*1024):
                    raise ValueError('Arquivo muito grande. Limite: 100 MB para áudio e 15 MB para capa.')
                stream.write(chunk)
        record = {'name': (file.filename or 'arquivo')[:240]}
        if kind == 'audio':
            record.update(duration=media.probe(target), script_hash=store.script_hash(project), normalized=False)
        else:
            saved = target.with_name(target.stem + '-cover.png')
            media.cover(target, saved)
            target.unlink()
        record.update(path=str(saved.relative_to(DATA)), sha256=media.digest(saved))
        return present(store.update_project(project_id, {kind: record}, revision))
    except (ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        target.unlink(missing_ok=True)
        saved.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except BaseException:
        target.unlink(missing_ok=True)
        saved.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@app.post('/api/projects/{project_id}/confirm-audio')
def confirm_audio(project_id: str, revision: int = Query(ge=1)):
    project = store.get_project(project_id)
    if not project.get('audio'):
        raise HTTPException(422, 'Importe uma narração primeiro.')
    record = dict(project['audio'], script_hash=store.script_hash(project))
    return present(store.update_project(project_id, {'audio': record}, revision))


@app.get('/api/projects/{project_id}/assets/{kind}')
def asset(project_id: str, kind: str):
    project = store.get_project(project_id)
    if kind not in ('audio', 'cover') or not project.get(kind):
        raise HTTPException(404, 'Material não encontrado.')
    path = media.data_path(project[kind]['path'])
    if not path.is_file():
        raise HTTPException(404, 'O material não está mais disponível no disco.')
    return FileResponse(path)


@app.post('/api/projects/{project_id}/renders', status_code=202)
def render(project_id: str, body: RenderRequest):
    return store.enqueue(project_id, body.mode, body.revision)


@app.get('/api/jobs')
def all_jobs():
    return store.jobs()


@app.post('/api/jobs/{job_id}/cancel')
def cancel(job_id: str):
    return store.cancel(job_id)


@app.get('/api/jobs/{job_id}/materials/{name}')
def job_material(job_id: str, name: str):
    job = store.get_job(job_id)
    if name not in job['materials']:
        raise HTTPException(404, 'Material desta versão não encontrado.')
    if name == 'input.json':
        snapshot = store.job_input(job_id)
        value = {key: snapshot.get(key, field.default) for key, field in ProjectInput.model_fields.items()}
        return JSONResponse(value, headers={'Content-Disposition': 'attachment; filename="antes-dos-agentes.json"'})
    path = media.data_path(f'projects/{job["project_id"]}/renders/{job_id}/{name}')
    return FileResponse(path, filename=name)


EXPORTS = {'short.mp4', 'capa.png', 'legendas.srt', 'publicacao.txt', 'roteiro.txt', 'render-manifest.json'}


def completed(job_id):
    job = store.get_job(job_id)
    if job['state'] != 'succeeded' or not job['output']:
        raise HTTPException(409, 'A produção ainda não tem arquivos concluídos.')
    return media.data_path(job['output']['directory'])


@app.get('/api/jobs/{job_id}/files/{name}')
def output_file(job_id: str, name: str, download: bool = False):
    if name not in EXPORTS:
        raise HTTPException(404, 'Arquivo não encontrado.')
    path = completed(job_id) / name
    if not path.is_file():
        raise HTTPException(404, 'Arquivo não encontrado.')
    return FileResponse(path, filename=name if download else None)


@app.get('/api/jobs/{job_id}/package')
def package(job_id: str):
    folder = completed(job_id)
    target = folder / 'mycut.zip'
    # A unique staging file avoids partial ZIP downloads during concurrent requests.
    with tempfile.NamedTemporaryFile(dir=folder, suffix='.zip', delete=False) as temp:
        staging = Path(temp.name)
    try:
        with zipfile.ZipFile(staging, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(EXPORTS):
                if (folder / name).is_file():
                    archive.write(folder / name, name)
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)
    return FileResponse(target, filename=f'mycut-{job_id[:8]}.zip')


# Production uses the same origin for frontend, API and range-enabled video files.
web = Path(os.environ.get('MYCUT_WEB_DIR', ROOT / 'web/dist'))
if web.is_dir():
    app.mount('/', StaticFiles(directory=web, html=True), name='web')
