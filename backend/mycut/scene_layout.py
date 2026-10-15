"""Spatial contract shared by manual edits, agent proposals and rendering."""
import copy
import math
import uuid
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Id = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{32}$')]
Percent = Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)]
Color = Annotated[str, StringConstraints(pattern=r'^#[a-fA-F0-9]{6}$')]


def new_id():
    return uuid.uuid4().hex


class VisualObject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Id = Field(default_factory=new_id)
    type: Literal['title', 'paragraph', 'image', 'video']
    width: Percent = 100
    height: Percent = 100
    horizontal: Literal['left', 'center', 'right'] = 'center'
    vertical: Literal['top', 'center', 'bottom'] = 'center'
    text: str = Field(default='', max_length=6000)
    font: str | None = Field(default=None, min_length=1, max_length=150)
    font_size: float = Field(default=48, ge=8, le=400, allow_inf_nan=False)
    color: Color | None = None
    align: Literal['left', 'center', 'right'] = 'left'
    text_vertical: Literal['top', 'center', 'bottom'] = 'top'
    asset_id: Id | None = None
    fit: Literal['contain', 'cover'] = 'contain'
    zoom: float = Field(default=1, ge=1, le=5, allow_inf_nan=False)
    crop_x: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    crop_y: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)


class SceneBlock(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Id = Field(default_factory=new_id)
    width: Percent = 100
    height: Percent
    align: Literal['left', 'center', 'right'] = 'center'
    object: VisualObject | None = None


def validate_blocks(blocks):
    if not blocks or not math.isclose(sum(b.height for b in blocks), 100, abs_tol=.01):
        raise ValueError('As alturas dos blocos devem somar 100%.')
    ids = [b.id for b in blocks] + [b.object.id for b in blocks if b.object]
    if len(ids) != len(set(ids)):
        raise ValueError('Cada bloco e objeto deve ter uma identificação única.')
    return blocks


def empty_blocks():
    return [SceneBlock(height=h).model_dump() for h in (20, 60, 20)]


def new_scene(title='Nova cena', narration=''):
    return {'id': new_id(), 'title': title, 'narration': narration,
            'layout': 'statement', 'items': [], 'blocks': empty_blocks()}


# Geometry is measured in the final 1080x1920 frame, independent of preview size.
AREA = (70, 220, 940, 1360)


def geometry(blocks):
    x, y, width, height = AREA
    result = []
    for block in blocks:
        bw, bh = width * block['width'] / 100, height * block['height'] / 100
        bx = x + (width - bw) * {'left': 0, 'center': .5, 'right': 1}[block['align']]
        obj = block.get('object')
        box = None
        if obj:
            ow, oh = bw * obj['width'] / 100, bh * obj['height'] / 100
            box = (bx + (bw-ow) * {'left': 0, 'center': .5, 'right': 1}[obj['horizontal']],
                   y + (bh-oh) * {'top': 0, 'center': .5, 'bottom': 1}[obj['vertical']], ow, oh)
        result.append({'block_id': block['id'], 'block': (bx, y, bw, bh), 'object': box})
        y += bh
    return result


def validate_assets(scene, project):
    images = {a['id'] for a in project.get('images', [])}
    videos = {a['id'] for a in project.get('videos', [])}
    for block in scene.get('blocks') or []:
        obj = block.get('object')
        if obj and obj.get('asset_id') and obj['type'] in ('image', 'video'):
            if obj['asset_id'] not in (images if obj['type'] == 'image' else videos):
                raise ValueError('Escolha uma mídia da biblioteca desta produção.')


def target(scene, scope, target_id):
    if scope == 'scene':
        return scene
    for block in scene.get('blocks') or []:
        if scope == 'block' and block['id'] == target_id:
            return block
        if scope == 'object' and block.get('object') and block['object']['id'] == target_id:
            return block  # Geometry of the containing block is part of the conflict check.
    raise ValueError('O alvo da conversa foi removido da cena.')


def scoped_blocks(scene, proposed, scope, target_id):
    """Reject scope escalation; only one adjacent block may compensate height."""
    proposed = [b.model_dump() for b in validate_blocks([SceneBlock.model_validate(b) for b in proposed])]
    if scope == 'scene':
        return proposed
    original = [SceneBlock.model_validate(b).model_dump() for b in scene['blocks']]
    if [b['id'] for b in original] != [b['id'] for b in proposed]:
        raise ValueError('A proposta alterou blocos fora do alcance escolhido.')
    selected = target(scene, scope, target_id)
    changed = next(b for b in proposed if b['id'] == selected['id'])
    if scope == 'object' and (not changed.get('object') or changed['object']['id'] != target_id):
        raise ValueError('A proposta deve preservar a identificação do objeto selecionado.')
    selected_index = next(i for i, b in enumerate(original) if b['id'] == selected['id'])
    resized_neighbors = []
    for index, (before, after) in enumerate(zip(original, proposed)):
        if before['id'] == selected['id']:
            continue
        expected = copy.deepcopy(before)
        if not math.isclose(after['height'], before['height'], abs_tol=.000001):
            resized_neighbors.append(index)
        expected['height'] = after['height']
        if expected != after:
            raise ValueError('A proposta alterou um objeto fora do alcance escolhido.')
    if len(resized_neighbors) > 1 or any(abs(i-selected_index) != 1 for i in resized_neighbors):
        raise ValueError('Ajuste uma borda por vez, compensando a altura apenas no bloco vizinho.')
    return proposed
