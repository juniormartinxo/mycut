import os
import shutil
import tempfile
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from PIL import UnidentifiedImageError, Image
from . import store, media
from .config import ROOT, DATA, UPLOAD_LIMIT
from .models import CreateProject, ProjectInput, RenderRequest, AgentRunRequest, AgentSettings, AgentCommands, AgentTestRequest, BrowserSettings, PricingSettings, ElevenConnect, ElevenSettings, CoverChoice
from . import integrations, elevenlabs, bridge, agent_models, agent_tests, commands, costs
from . import voice_tests, covers, endings, flow
from . import visuals, scene_layout, scene_media, google_fonts
from .scene_api import router as scene_router
from .models import ScenePreview
from .seed import blank, initialize_example


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
        port = int(os.environ.get('MYCUT_PORT', '8321'))
        allowed = {'http://localhost:5173', 'http://127.0.0.1:5173', 'http://testserver',
                   f'http://localhost:{port}', f'http://127.0.0.1:{port}'}
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
    project.setdefault('visual_style', None)
    project.setdefault('ending_id', None)
    project['jobs'] = store.jobs(project['id'])
    for key in ['audio', 'cover']:
        if project.get(key):
            project[key] = {k: v for k, v in project[key].items() if k not in ('path', 'alignment')}
            project[key]['url'] = f'/api/projects/{project["id"]}/assets/{key}?v={project["revision"]}'
    project['videos'] = [scene_media.public(project['id'], item) for item in project.get('videos', [])]
    project['usage_total'] = costs.project(project['id'], integrations.read()['pricing'])['total']
    project['audio_matches_script'] = bool(project.get('audio') and project['audio']['script_hash'] == store.script_hash(project))
    project['images'] = [{k: v for k, v in item.items() if k != 'path'} |
                         {'url': f'/api/projects/{project["id"]}/images/{item["id"]}'}
                         for item in project.get('images', [])]
    return project


@app.get('/api/short-formats')
def short_formats():
    return {'formats': [{k: v for k, v in item.items() if k != 'direction'} |
                        {'preview_url': f'/api/short-formats/{item["id"]}/preview.png'}
                        for item in visuals.FORMATS], 'fonts': visuals.FONT_NAMES}


@app.get('/api/short-formats/{format_id}/preview.png')
def format_preview(format_id: str):
    if format_id not in {item['id'] for item in visuals.FORMATS}:
        raise HTTPException(404, 'Formato não encontrado.')
    sample = {'title': 'Da ideia à ação', 'layout': 'flow',
              'items': ['Você define a tarefa', 'O agente executa', 'Você revisa o resultado'], 'narration': ''}
    selected = visuals.preset(format_id)
    return Response(visuals.preview_png(sample, {'visual_style': {'format_id': format_id}, 'accent': selected['accent']}, 270),
                    media_type='image/png', headers={'Cache-Control': 'public, max-age=3600'})


@app.post('/api/scene-preview')
def scene_preview(body: ScenePreview):
    document = body.model_dump()
    scene = body.scene.model_dump()
    clock = flow.estimate_clock(scene['narration'])
    if body.project_id:
        owner = store.get_project(body.project_id)
        document['images'] = owner.get('images', [])
        document['videos'] = owner.get('videos', [])
        clock = flow.scene_clock(owner, scene)
    width = 1080 if body.width == 'full' else 360
    return Response(visuals.preview_png(scene, document, width, body.elapsed, clock), media_type='image/png')


@app.post('/api/projects/{project_id}/images')
def upload_scene_image(project_id: str, file: UploadFile, revision: int = Query(ge=1)):
    from .scene_images import import_image
    project = store.get_project(project_id)
    if len(project.get('images', [])) >= 24:
        raise ValueError('Use até 24 imagens por produção.')
    try:
        content = file.file.read(15 * 1024 * 1024 + 1)
        record = import_image(content, project_id, file.filename or 'Imagem')
        try:
            return present(store.update_project(project_id, {'images': [*project.get('images', []), record]}, revision))
        except BaseException:
            media.data_path(record['path']).unlink(missing_ok=True)
            raise
    finally:
        file.file.close()


@app.get('/api/projects/{project_id}/images/{image_id}')
def project_image(project_id: str, image_id: str):
    record = next((item for item in store.get_project(project_id).get('images', []) if item['id'] == image_id), None)
    if record is None:
        raise HTTPException(404, 'Imagem não encontrada.')
    return FileResponse(media.data_path(record['path']), media_type='image/png')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'worker_online': store.worker_online(), 'ffmpeg': bool(shutil.which('ffmpeg')),
            'instance': os.environ.get('MYCUT_INSTANCE', os.environ.get('HOSTNAME', 'local'))}


@app.get('/api/projects')
def projects():
    return [present(p) for p in store.all_projects()]


@app.post('/api/projects', status_code=201)
def create(body: CreateProject):
    if body.automation != 'none':
        if not body.brief.strip():
            raise ValueError('Informe a pauta ou link para iniciar os agentes.')
        settings = ready_for(body.automation)
    document = blank(body.title)
    document['title'] = body.title.strip() or 'Novo Short'
    document['brief'] = body.brief
    document['accent_locked'] = body.accent is not None
    if body.visual_style is not None:
        document['visual_style'] = body.visual_style.model_dump()
        document['accent'] = body.accent or visuals.preset(body.visual_style.format_id)['accent']
        document['accent_locked'] = True
    if body.accent is not None:
        document['accent'] = body.accent
    result = store.create_project(document)
    if body.automation != 'none':
        store.enqueue(result['id'], 'final', result['revision'], body.automation, settings)
    return present(result)


def ready_for(kind):
    settings = integrations.read()
    if kind in ('pipeline', 'plan'):
        bridge.require(v['provider'] for v in settings['agents'].values())
    if kind == 'scenes':
        bridge.require(settings['agents'][role]['provider'] for role in ('director', 'reviewer'))
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


@app.put('/api/integrations/commands')
def configure_commands(body: AgentCommands):
    # Runs on the host as the user's own shell would; origin checks above keep it local.
    values = {provider: text.strip() for provider, text in body.model_dump().items()}
    for text in values.values():
        commands.parse(text)
    result = integrations.save_section('commands', values)
    bridge.BRIDGE.mkdir(parents=True, exist_ok=True)
    # Another login or config dir may expose another model list.
    (bridge.BRIDGE / 'refresh-models').touch()
    return result


@app.put('/api/integrations/pricing')
def configure_pricing(body: PricingSettings):
    return integrations.save_section('pricing', body.model_dump())


@app.get('/api/projects/{project_id}/usage')
def project_usage(project_id: str):
    store.get_project(project_id)
    return costs.project(project_id, integrations.read()['pricing'])


@app.put('/api/integrations/browser')
def configure_browser(body: BrowserSettings):
    values = body.model_dump()
    values['chrome_path'] = values['chrome_path'].strip()
    return integrations.save_section('browser', values)


@app.post('/api/integrations/browser/test', status_code=202)
def test_browser():
    bridge.require([])
    if not integrations.read()['browser']['enabled']:
        raise ValueError('Ative o navegador antes de testar.')
    if bridge.status().get('protocol', 0) < 3:
        raise ValueError('Reinicie bash scripts/agents.sh no WSL para habilitar o navegador.')
    test_id = uuid.uuid4().hex
    bridge.atomic_json(bridge.BRIDGE / 'browser-test', {'id': test_id})
    return {'id': test_id, 'message': 'O executor vai abrir o Chrome e testar o navegador quando estiver livre.'}


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


@app.get('/api/integrations/elevenlabs/tests')
def latest_voice_tests():
    return voice_tests.latest()


@app.post('/api/integrations/elevenlabs/tests')
def test_voice(body: voice_tests.VoiceTestRequest):
    return voice_tests.generate(body)


@app.get('/api/integrations/elevenlabs/tests/{test_id}/audio')
def voice_test_audio(test_id: str):
    return FileResponse(voice_tests.audio(test_id), media_type='audio/mpeg',
                        headers={'Cache-Control': 'private, no-store'})


@app.post('/api/projects/{project_id}/run', status_code=202)
def run_agents(project_id: str, body: AgentRunRequest):
    if body.kind == 'scenes' and any(s.get('blocks') is not None for s in store.get_project(project_id)['scenes']):
        raise store.Conflict('Use a conversa da cena para revisar e aceitar alterações nos blocos.')
    settings = ready_for(body.kind)
    return store.enqueue(project_id, body.mode, body.revision, body.kind, settings)


@app.get('/api/projects/{project_id}')
def project(project_id: str):
    return present(store.get_project(project_id))


@app.put('/api/projects/{project_id}')
def update(project_id: str, body: ProjectInput):
    values = body.model_dump()
    revision = values.pop('revision')
    if body.ending_id:
        endings.get(body.ending_id)
    current = store.get_project(project_id)
    images = {item['id'] for item in current.get('images', [])}
    if body.visual_style and body.visual_style.google_font:
        google_fonts.entry(body.visual_style.google_font)
    for scene in body.scenes:
        scene_layout.validate_assets(scene.model_dump(), current)
        for block in [*(scene.blocks or []), *(b for shot in scene.shots for b in shot.blocks)]:
            if block.object and block.object.font:
                google_fonts.entry(block.object.font)
    if any(scene.image_id and scene.image_id not in images for scene in body.scenes):
        raise ValueError('Escolha uma imagem desta produção ou use somente animação.')
    return present(store.update_project(project_id, values, revision))


@app.get('/api/endings')
def list_endings():
    return endings.catalog()


@app.post('/api/endings', status_code=201)
def import_ending(file: UploadFile):
    try:
        return endings.import_clip(file.file, file.filename or 'video.mp4')
    finally:
        file.file.close()


@app.get('/api/endings/{ending_id}/{kind}')
def ending_asset(ending_id: str, kind: str):
    endings.get(ending_id)
    if kind not in ('video', 'poster'):
        raise HTTPException(404, 'Material do encerramento não encontrado.')
    return FileResponse(DATA / 'endings' / ending_id / ('clip.mp4' if kind == 'video' else 'poster.jpg'),
                        media_type='video/mp4' if kind == 'video' else 'image/jpeg')


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


@app.get('/api/projects/{project_id}/cover/messages')
def cover_messages(project_id: str):
    store.get_project(project_id)
    return covers.messages(project_id)


@app.post('/api/projects/{project_id}/cover/messages', status_code=202)
def send_cover_message(project_id: str, text: str = Form(max_length=2000), provider: str = Form(),
                       model: str = Form('', max_length=150), files: list[UploadFile] | None = File(None)):
    """One chat turn: the chosen agent creates one image; nothing in the project changes until one is chosen."""
    files = files or []
    try:
        store.get_project(project_id)
        if not text.strip():
            raise ValueError('Escreva o que você quer na capa.')
        if provider not in bridge.PROVIDERS:
            raise ValueError('Escolha um agente válido.')
        choice = {'provider': provider, 'model': model.strip()}
        agent_models.validate(choice)
        bridge.require_images()
        bridge.require([provider])
        if len(files) > covers.MAX_ATTACHMENTS:
            raise ValueError(f'Envie até {covers.MAX_ATTACHMENTS} imagens por mensagem.')
        job_id = store.uid()
        folder = DATA / 'projects' / project_id / 'renders' / job_id
        try:
            attachments = []
            for index, upload in enumerate(files, 1):
                path = folder / 'attachments' / f'{index}.png'
                covers.import_attachment(upload.file.read(15 * 1024 * 1024 + 1), path)
                attachments.append({'name': (upload.filename or f'Imagem {index}')[:200], 'path': str(path.relative_to(DATA))})
            turns, reference = covers.history(project_id)
            store.enqueue_cover(project_id, {'text': text.strip(), **choice, 'attachments': attachments,
                                             'history': turns, 'reference': reference}, job_id)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return covers.public(store.get_job(job_id, private=True))
    finally:
        for upload in files:
            upload.file.close()


@app.get('/api/projects/{project_id}/cover/{job_id}/{kind}/{name}')
def cover_file(project_id: str, job_id: str, kind: str, name: str):
    if kind not in ('attachments', 'images'):
        raise HTTPException(404, 'Imagem não encontrada.')
    return FileResponse(covers.file(project_id, job_id, kind, name), media_type='image/png')


@app.post('/api/projects/{project_id}/cover/select')
def select_cover(project_id: str, body: CoverChoice):
    job, record = covers.image(project_id, body.job_id, body.image_id)
    folder = DATA / 'projects' / project_id / 'uploads'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (store.uid() + '-cover.png')
    try:
        media.cover(media.data_path(record['path']), target)
        provider = job['snapshot']['_cover']['provider']
        cover = {'name': f'Capa criada no chat · {covers.NAMES[provider]}', 'path': str(target.relative_to(DATA)),
                 'sha256': media.digest(target), 'chat_image': f'{body.job_id}/{body.image_id}'}
        return present(store.update_project(project_id, {'cover': cover}, body.revision))
    except BaseException:
        target.unlink(missing_ok=True)
        raise


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


app.include_router(scene_router)

# Production uses the same origin for frontend, API and range-enabled video files.
web = Path(os.environ.get('MYCUT_WEB_DIR', ROOT / 'web/dist'))
if web.is_dir():
    app.mount('/', StaticFiles(directory=web, html=True), name='web')
