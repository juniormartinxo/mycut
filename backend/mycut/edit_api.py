"""HTTP adapters for the editing document of horizontal projects; the editing core owns the rules."""
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from . import editing, exporting, frames

router = APIRouter(prefix='/api/edit-projects')
archive_router = APIRouter(prefix='/api')


@router.get('')
def projects():
    return editing.all_projects()


@router.post('', status_code=201)
def create(body: editing.CreateRequest):
    return editing.create(body)


@router.get('/{project_id}')
def project(project_id: str):
    return editing.get(project_id)


@router.get('/{project_id}/history')
def history(project_id: str):
    return editing.history(project_id)


@router.post('/{project_id}/operations')
def operations(project_id: str, body: editing.EditRequest):
    from .api import chosen_voice
    for operation in body.operations:
        if operation.op == 'update_project' and operation.voice is not None:
            operation.voice = editing.ElevenSettings(**chosen_voice(operation.voice))
    return editing.apply(project_id, body)


@router.post('/{project_id}/undo')
def undo(project_id: str, body: editing.HistoryRequest):
    return editing.undo(project_id, body)


@router.post('/{project_id}/redo')
def redo(project_id: str, body: editing.HistoryRequest):
    return editing.redo(project_id, body)


@router.post('/{project_id}/resources')
def import_resource(project_id: str, file: UploadFile, revision: int = Form(ge=1),
                    author_kind: str = Form('human'), author_name: str = Form('Autor')):
    author = editing.Author(kind=author_kind, name=author_name)
    try:
        return editing.import_resource(project_id, revision, author, file.file, file.filename or 'Recurso', file.content_type)
    finally:
        file.file.close()


@router.get('/{project_id}/resources/{digest}')
def resource_file(project_id: str, digest: str):
    path, media_type = editing.resource_file(project_id, digest)
    # Even a mislabeled file never runs as a page of the studio.
    return FileResponse(path, media_type=media_type, headers={
        'Cache-Control': 'private, max-age=31536000, immutable', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': 'sandbox'})


def video_format(project_id, digest):
    project = editing.get(project_id)
    resource = next((r for r in project['resources'] if r['hash'] == digest), None)
    if resource is None or not resource['media_type'].startswith('video/'):
        raise HTTPException(404, 'Vídeo não encontrado neste projeto.')
    return project['format']['fps'], project['format']['width'], project['format']['height']


@router.get('/{project_id}/frames/{digest}')
def video_frames(project_id: str, digest: str):
    """The frames of a video for the preview, prepared in the background at the project's fps and size."""
    return frames.request(digest, *video_format(project_id, digest))


@router.get('/{project_id}/frames/{digest}/{index}.jpg')
def video_frame(project_id: str, digest: str, index: int):
    path = frames.frame(digest, *video_format(project_id, digest), index)
    if not path.exists():
        raise HTTPException(404, 'Quadro não encontrado.')
    return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=31536000, immutable'})


@router.post('/{project_id}/exports', status_code=201)
def export(project_id: str, body: exporting.ExportRequest):
    return exporting.create(project_id, body)


@router.get('/{project_id}/exports')
def exports(project_id: str):
    return exporting.listing(project_id)


@router.get('/{project_id}/exports/{export_id}/file')
def export_file(project_id: str, export_id: str):
    path, name = exporting.file(project_id, export_id)
    return FileResponse(path, media_type='video/mp4', filename=name)


@router.delete('/{project_id}/exports/{export_id}')
def remove_export(project_id: str, export_id: str, body: exporting.RemoveRequest):
    if body.author.kind != 'human':
        raise HTTPException(403, 'Somente o autor pode remover uma exportação.')
    return exporting.remove(project_id, export_id)


@router.get('/{project_id}/storage')
def storage(project_id: str):
    return editing.storage(project_id)


@router.post('/{project_id}/cleanup')
def cleanup(project_id: str, body: editing.CleanupRequest):
    if body.author.kind != 'human':
        raise HTTPException(403, 'Somente o autor pode apagar o histórico e liberar espaço.')
    return editing.cleanup(project_id, body)


@archive_router.get('/resources')
def archive():
    """The shared acervo: each content once, with the projects that reference it."""
    return editing.archive()
