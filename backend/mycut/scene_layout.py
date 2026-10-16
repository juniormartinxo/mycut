"""Spatial contract shared by manual edits, agent proposals and rendering."""
import copy
import math
import uuid
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from .flow import FlowSpec

Id = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{32}$')]
Percent = Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)]
Color = Annotated[str, StringConstraints(pattern=r'^#[a-fA-F0-9]{6}$')]
# Camera motion over a plano's duration (ADR 0004); 'none' keeps the authored framing still.
Motion = Literal['none', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'pan_up', 'pan_down']
Playback = Literal['once', 'loop']
MAX_SHOTS = 12
MAX_PROJECT_SHOTS = 60


def new_id():
    return uuid.uuid4().hex


class VisualObject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Id = Field(default_factory=new_id)
    type: Literal['title', 'paragraph', 'image', 'video', 'flow']
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
    # Only animated flows carry this; omitted elsewhere so older objects keep their stored shape.
    flow: FlowSpec | None = Field(default=None, exclude_if=lambda value: value is None)
    # Behaviour in time (ADR 0004), omitted while unused so older objects keep their stored shape.
    reveal: Literal['none', 'lines', 'typing'] = Field(default='none', exclude_if=lambda value: value == 'none')
    motion: Motion = Field(default='none', exclude_if=lambda value: value == 'none')
    # An animated GIF plays once and holds its last frame, or loops until the plano ends.
    playback: Playback = Field(default='once', exclude_if=lambda value: value == 'once')

    @model_validator(mode='after')
    def flow_only_in_flow_objects(self):
        if self.flow is not None and self.type != 'flow':
            raise ValueError('Somente um Fluxo animado contém nós e etapas.')
        if self.reveal != 'none' and self.type not in ('title', 'paragraph'):
            raise ValueError('Somente título e parágrafo têm revelação progressiva.')
        if self.motion != 'none' and self.type != 'image':
            raise ValueError('O movimento de câmera vale para imagens; vídeos já têm o próprio movimento.')
        if self.playback != 'once' and self.type != 'image':
            raise ValueError('A repetição em loop vale para GIFs animados.')
        return self


class SceneBlock(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Id = Field(default_factory=new_id)
    width: Percent = 100
    height: Percent
    align: Literal['left', 'center', 'right'] = 'center'
    object: VisualObject | None = None


class Background(BaseModel):
    """Full-frame layer behind a plano's blocks; without one the project background is used."""
    model_config = ConfigDict(extra='forbid')
    kind: Literal['color', 'gradient', 'image', 'video']
    color: Color | None = None
    color_to: Color | None = None
    # CSS convention: 180 runs from top to bottom.
    angle: float = Field(default=180, ge=0, le=360, allow_inf_nan=False)
    asset_id: Id | None = None
    zoom: float = Field(default=1, ge=1, le=5, allow_inf_nan=False)
    crop_x: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    crop_y: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    motion: Motion = 'none'
    playback: Playback = Field(default='once', exclude_if=lambda value: value == 'once')
    # Darkens media so text and captions stay readable on top of it.
    dim: float = Field(default=0, ge=0, le=80, allow_inf_nan=False)

    @model_validator(mode='after')
    def complete(self):
        if self.kind == 'color' and not self.color:
            raise ValueError('Escolha a cor do fundo.')
        if self.kind == 'gradient' and not (self.color and self.color_to):
            raise ValueError('Um degradê precisa das duas cores.')
        if self.motion != 'none' and self.kind != 'image':
            raise ValueError('O movimento de câmera vale para fundos de imagem.')
        if self.playback != 'once' and self.kind != 'image':
            raise ValueError('A repetição em loop vale para fundos com GIF animado.')
        return self


def validate_blocks(blocks):
    if not blocks or not math.isclose(sum(b.height for b in blocks), 100, abs_tol=.01):
        raise ValueError('As alturas dos blocos devem somar 100%.')
    ids = [b.id for b in blocks] + [b.object.id for b in blocks if b.object]
    if len(ids) != len(set(ids)):
        raise ValueError('Cada bloco e objeto deve ter uma identificação única.')
    return blocks


class Shot(BaseModel):
    """A plano after the first: the first plano is the scene's own composition (ADR 0004)."""
    model_config = ConfigDict(extra='forbid')
    id: Id = Field(default_factory=new_id)
    anchor: str | None = Field(default=None, max_length=200)
    transition: Literal['cut', 'fade'] = 'cut'
    background: Background | None = None
    brand: bool = True
    blocks: list[SceneBlock] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_blocks(self):
        validate_blocks(self.blocks)
        return self


def shots(scene):
    """Every plano of a block scene in order, the first being the scene's own composition."""
    first = {'id': scene.get('id'), 'anchor': None, 'transition': 'cut', 'background': scene.get('background'),
             'brand': scene.get('brand', True), 'blocks': scene['blocks']}
    return [first, *(scene.get('shots') or [])]


def shot_view(scene, shot_id):
    """The scene as seen in one plano: that plano's composition, no later planos."""
    shot = next((s for s in shots(scene) if s['id'] == shot_id), None)
    if shot is None:
        raise ValueError('O plano foi removido da cena.')
    view = {k: v for k, v in scene.items() if k not in ('shots', 'background', 'brand')}
    view.update(blocks=shot['blocks'], brand=shot.get('brand', True))
    if shot.get('background'):
        view['background'] = shot['background']
    return view


def with_shot_blocks(scene, shot_id, blocks):
    if shot_id == scene.get('id'):
        return {**scene, 'blocks': blocks}
    if not any(s['id'] == shot_id for s in scene.get('shots') or []):
        raise ValueError('O plano foi removido da cena.')
    return {**scene, 'shots': [{**s, 'blocks': blocks} if s['id'] == shot_id else s for s in scene['shots']]}


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
    if scene.get('blocks') is None:
        return
    for shot in shots(scene):
        background = shot.get('background') or {}
        if background.get('asset_id') and background['kind'] in ('image', 'video'):
            if background['asset_id'] not in (images if background['kind'] == 'image' else videos):
                raise ValueError('Escolha uma mídia da biblioteca desta produção para o fundo.')
        for block in shot['blocks']:
            obj = block.get('object')
            if obj and obj.get('asset_id') and obj['type'] in ('image', 'video'):
                if obj['asset_id'] not in (images if obj['type'] == 'image' else videos):
                    raise ValueError('Escolha uma mídia da biblioteca desta produção.')


def shot_of(scene, scope, target_id):
    """The plano a conversation works on: the one holding its block or object, or the plano itself."""
    for shot in shots(scene):
        if scope == 'scene' and shot['id'] == target_id:
            return shot
        for block in shot['blocks']:
            if (scope == 'block' and block['id'] == target_id or
                    scope == 'object' and block.get('object') and block['object']['id'] == target_id):
                return shot
    raise ValueError('O alvo da conversa foi removido da cena.')


def target(scene, scope, target_id):
    if scope == 'scene':
        if target_id == scene.get('id'):
            return scene
        return shot_of(scene, scope, target_id)
    for block in shot_of(scene, scope, target_id)['blocks']:
        if block['id'] == target_id or block.get('object') and block['object']['id'] == target_id:
            return block  # Geometry of the containing block is part of the conflict check.
    raise ValueError('O alvo da conversa foi removido da cena.')


def scoped_blocks(scene, proposed, scope, target_id):
    """Reject scope escalation; only one adjacent block may compensate height."""
    proposed = [b.model_dump() for b in validate_blocks([SceneBlock.model_validate(b) for b in proposed])]
    if scope == 'scene':
        return proposed
    original = [SceneBlock.model_validate(b).model_dump() for b in shot_of(scene, scope, target_id)['blocks']]
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
