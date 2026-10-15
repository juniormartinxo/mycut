"""HTTP adapters for the block editor; rendering and conversations own the rules."""
import io
import shutil
from typing import Literal
from fastapi import APIRouter, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from . import store, google_fonts, scene_media, scene_chat, block_render, visuals, flow
from .models import ScenePreview
from .scene_layout import new_id, empty_blocks, VisualObject
from .media import data_path

router = APIRouter(prefix='/api')


class FontRequest(BaseModel):
    family: str = Field(min_length=1, max_length=150)


class ChoiceRequest(BaseModel):
    decision: Literal['accepted', 'discarded']
    revision: int = Field(ge=1)


def preview_project(body):
    project = store.get_project(body.project_id) if body.project_id else {}
    return {**project, 'accent': body.accent, 'visual_style': body.visual_style.model_dump() if body.visual_style else None}


@router.get('/google-fonts')
def font_catalog():
    return google_fonts.catalog()


@router.post('/google-fonts/install')
def prepare_font(body: FontRequest):
    google_fonts.install(body.family)
    return {'family': body.family}


@router.get('/google-fonts/file')
def font_file(family: str = Query(max_length=150)):
    return FileResponse(google_fonts.install(family), media_type='font/ttf',
                        headers={'Cache-Control': 'private, max-age=31536000, immutable'})


@router.post('/scene-layout/inspect')
def inspect_layout(body: ScenePreview):
    if body.scene.blocks is None:
        return {'issues': [], 'warnings': [], 'geometry': []}
    scene = body.scene.model_dump()
    owner = store.get_project(body.project_id) if body.project_id else {}
    clock = flow.scene_clock(owner, scene)
    return {**block_render.inspect(scene, preview_project(body), clock),
            'clock': {'duration': clock['duration'], 'source': clock['source']}}


@router.post('/projects/{project_id}/scene-videos')
def upload_video(project_id: str, file: UploadFile, revision: int = Query(ge=1)):
    from .api import present
    project = store.get_project(project_id)
    record = None
    try:
        record = scene_media.import_video(file.file, file.filename or 'video.mp4', project_id)
        return present(store.update_project(project_id, {'videos': [*project.get('videos', []), record]}, revision))
    except BaseException:
        if record:
            shutil.rmtree(data_path(record['path']).parent)
        raise
    finally:
        file.file.close()


@router.get('/projects/{project_id}/scene-videos/{asset_id}/{kind}')
def video_file(project_id: str, asset_id: str, kind: Literal['video', 'poster']):
    project = store.get_project(project_id)
    record = next((r for r in project.get('videos', []) if r['id'] == asset_id), None)
    if not record:
        raise store.Missing('Vídeo não encontrado nesta produção.')
    return FileResponse(data_path(record['path' if kind == 'video' else 'poster_path']),
                        media_type='video/mp4' if kind == 'video' else 'image/png')


@router.post('/projects/{project_id}/scene-layout/convert')
def convert_scene(project_id: str, body: ScenePreview, revision: int = Query(ge=1)):
    from .api import present
    from .scene_images import import_image
    from .production import scene_image
    project = store.get_project(project_id)
    if project['revision'] != revision:
        raise store.Conflict('Salve e atualize o projeto antes de converter a cena.')
    original = body.scene.model_dump()
    if original['blocks'] is not None:
        raise ValueError('Esta cena já usa blocos.')
    blocks = empty_blocks()
    blocks[0]['object'] = VisualObject(type='title', text=original['title'], font_size=64).model_dump()
    image_id = original.get('image_id')
    if image_id and image_id not in {r['id'] for r in project.get('images', [])}:
        raise ValueError('A imagem original não está disponível.')
    if not image_id:
        rendering = {**project, 'accent': body.accent, 'visual_style': body.visual_style.model_dump() if body.visual_style else None}
        drawing = visuals.Composition({**original, 'title': ''}, rendering).frame() if rendering.get('visual_style') else scene_image({**original, 'title': ''}, rendering['accent'])
        stream = io.BytesIO()
        drawing.crop((70, 640, 1010, 1580)).save(stream, 'PNG')
        record = import_image(stream.getvalue(), project_id, 'Diagrama da cena · conversão')
        try:
            project = store.update_project(project_id, {'images': [*project.get('images', []), record]}, revision)
        except BaseException:
            data_path(record['path']).unlink(missing_ok=True)
            raise
        image_id = record['id']
    blocks[1]['object'] = VisualObject(type='image', asset_id=image_id).model_dump()
    proposed = {**original, 'id': original.get('id') or new_id(), 'blocks': blocks}
    return {'project': present(project), 'scene': proposed}


@router.get('/projects/{project_id}/scene-conversations')
def conversations(project_id: str):
    return scene_chat.messages(project_id)


@router.put('/projects/{project_id}/scene-conversations')
def mark_thread(project_id: str, body: scene_chat.ThreadRequest):
    return scene_chat.thread(project_id, body)


@router.post('/projects/{project_id}/scene-conversations', status_code=202)
def send_message(project_id: str, body: scene_chat.MessageRequest):
    return scene_chat.enqueue(project_id, body)


@router.post('/projects/{project_id}/scene-proposals/{job_id}')
def choose_proposal(project_id: str, job_id: str, body: ChoiceRequest):
    from .api import present
    return present(scene_chat.choose(project_id, job_id, body.decision, body.revision))
