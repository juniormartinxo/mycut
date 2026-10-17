"""HTTP adapters for the editing document of horizontal projects; the editing core owns the rules."""
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from . import editing

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
    return FileResponse(path, media_type=media_type, headers={'Cache-Control': 'private, max-age=31536000, immutable'})


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
