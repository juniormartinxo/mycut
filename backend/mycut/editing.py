"""Editing document of a horizontal project and the operations that change it (ADR 0014).

Humans and agents change the document only through operations: one request is validated, applied and recorded in
the history inside the same transaction, and is undone as a whole. The history keeps, for each entity it touched,
the value before and after, so undo and redo restore exactly those entities and survive a restart.
"""
import copy
import json
import math
import time
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from . import store
from .models import ElevenSettings

SCHEMA_VERSION = 2
# Contents of the timeline (ADR 0006); a project starts with one track of each.
TRACKS = {'visual': 'Visuais', 'text': 'Textos', 'narration': 'Narração', 'music': 'Música', 'effects': 'Efeitos'}
AUDIO = {'narration', 'music', 'effects'}
# What an item shows until it has its own choice; templates (MYC-25) will be the source of these values (Q65).
LOOK = {'scale': 1.0, 'rotation': 0.0, 'brightness': 1.0, 'contrast': 1.0, 'saturation': 1.0, 'blur': 0.0}
TEMPLATE = {
    'visual': {'opacity': 1.0, 'fit': 'cover', **LOOK, 'zoom': 1.0, 'pan_x': 0.0, 'pan_y': 0.0},
    'text': {'opacity': 1.0, 'color': '#ffffff', 'font_family': 'Manrope', 'font_size': 64, 'align': 'center', **LOOK},
    'audio': {'volume': 1.0},
}
# Properties that change over an item through points in time (Q22); x and y move the item's box in the space.
ANIMATED = {'visual': ('x', 'y', 'opacity', *LOOK, 'zoom', 'pan_x', 'pan_y'), 'text': ('x', 'y', 'opacity', *LOOK), 'audio': ()}
# Composition space (Q64): items may sit past the frame, but not at absurd distances.
SPACE_LIMIT = 100_000
LONGEST = 6 * 3600 * 1000

EntityId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')]
Hash = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{64}$')]
Text = Annotated[str, StringConstraints(max_length=2000)]
Ms = Annotated[int, Field(ge=0, le=LONGEST)]
Length = Annotated[int, Field(ge=1, le=LONGEST)]
Coordinate = Annotated[float, Field(ge=-SPACE_LIMIT, le=SPACE_LIMIT, allow_inf_nan=False)]
Size = Annotated[float, Field(gt=0, le=SPACE_LIMIT, allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Author(Strict):
    kind: Literal['human', 'agent']
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class Format(Strict):
    """Proportion, resolution and fps belong to the project (Q34): 16:9 is the default, not a rule."""
    width: int = Field(default=1920, ge=16, le=7680)
    height: int = Field(default=1080, ge=16, le=7680)
    fps: int = Field(default=30, ge=1, le=120)


class Geometry(Strict):
    """Position and size in the composition space, in pixels of the frame; the frame is the default framing."""
    x: Coordinate
    y: Coordinate
    width: Size
    height: Size


class NewScene(Strict):
    id: EntityId | None = None
    title: Annotated[str, StringConstraints(max_length=100)] = ''
    duration_ms: Length = 5000


class AddScene(Strict):
    op: Literal['add_scene']
    scene: NewScene = Field(default_factory=NewScene)
    index: int | None = Field(default=None, ge=0)


class UpdateScene(Strict):
    op: Literal['update_scene']
    scene_id: EntityId
    title: Annotated[str, StringConstraints(max_length=100)] | None = None
    duration_ms: Length | None = None


class MoveScene(Strict):
    op: Literal['move_scene']
    scene_id: EntityId
    index: int = Field(ge=0)


class RemoveScene(Strict):
    op: Literal['remove_scene']
    scene_id: EntityId


class NewTrack(Strict):
    id: EntityId | None = None
    kind: Literal['visual', 'text', 'narration', 'music', 'effects']
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ''


class AddTrack(Strict):
    op: Literal['add_track']
    track: NewTrack
    index: int | None = Field(default=None, ge=0)


class RemoveTrack(Strict):
    op: Literal['remove_track']
    track_id: EntityId


class Transition(Strict):
    """How an item enters or leaves; no transition is a cut (corte seco)."""
    kind: Literal['fade', 'dissolve', 'rise', 'pop', 'type', 'sink']
    duration_ms: Annotated[int, Field(ge=1, le=60_000)]


# Which transitions each kind of content accepts: a dissolve (fusão) crosses into the item before it on the track.
TRANSITIONS = {'visual': {'enter': {'fade', 'dissolve'}, 'exit': {'fade'}},
               'text': {'enter': {'fade', 'rise', 'pop', 'type'}, 'exit': {'fade', 'sink', 'pop'}},
               'audio': {'enter': {'fade'}, 'exit': {'fade'}}}


class Freeze(Strict):
    """A frame held on screen: at this moment of the item the clip stops for duration_ms, then plays on."""
    at_ms: Ms
    duration_ms: Length


class ItemFields(Strict):
    track_id: EntityId | None = None
    scene_id: EntityId | None = None
    start_ms: Ms | None = None
    duration_ms: Length | None = None
    # Trim at the start of the media: the moment of the resource shown when the item begins.
    source_start_ms: Ms | None = None
    # Visual order: higher layers are drawn over lower ones.
    layer: int | None = Field(default=None, ge=-1000, le=1000)
    geometry: Geometry | None = None
    text: Text | None = None
    resource: Hash | None = None
    enter: Transition | None = None
    exit: Transition | None = None
    # Speed of the clip's media; with the held frame, it sets how long the clip occupies the timeline.
    speed: Annotated[float, Field(ge=0.25, le=4, allow_inf_nan=False)] | None = None
    freeze: Freeze | None = None


class NewItem(ItemFields):
    id: EntityId | None = None
    track_id: EntityId
    start_ms: Ms
    duration_ms: Length
    style: dict[str, Any] = Field(default_factory=dict)


class Keyframe(Strict):
    # Relative to the item's start, so moving the item takes its points along.
    at_ms: Ms
    value: float = Field(allow_inf_nan=False)
    # How the value travels from this point to the next one.
    easing: Literal['linear', 'ease', 'hold'] = 'linear'


class SetKeyframes(Strict):
    """All the points of one property; null removes them and the property goes back to its single value."""
    op: Literal['set_keyframes']
    item_id: EntityId
    property: Annotated[str, StringConstraints(max_length=20)]
    points: list[Keyframe] | None = Field(default=None, max_length=200)


class AddItem(Strict):
    op: Literal['add_item']
    item: NewItem


class UpdateItem(Strict):
    op: Literal['update_item']
    item_id: EntityId
    changes: ItemFields


class SetStyle(Strict):
    """A value records the choice of that property only; null removes it and the item inherits again (Q65)."""
    op: Literal['set_style']
    item_id: EntityId
    values: dict[str, Any] = Field(min_length=1, max_length=20)


class SplitItem(Strict):
    op: Literal['split_item']
    item_id: EntityId
    at_ms: Ms
    new_id: EntityId | None = None


class RemoveItem(Strict):
    op: Literal['remove_item']
    item_id: EntityId


class AddResource(Strict):
    op: Literal['add_resource']
    hash: Hash
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RemoveResource(Strict):
    op: Literal['remove_resource']
    hash: Hash


class UpdateProject(Strict):
    """Own choices of the project; null goes back to the channel's (ADR 0018)."""
    op: Literal['update_project']
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    format: Format | None = None
    channel_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    brand: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    # Checked against the connected ElevenLabs account by the HTTP adapter, as a channel's voice.
    voice: ElevenSettings | None = None


Operation = Annotated[Union[AddScene, UpdateScene, MoveScene, RemoveScene, AddTrack, RemoveTrack, AddItem, UpdateItem,
                            SetStyle, SetKeyframes, SplitItem, RemoveItem, AddResource, RemoveResource, UpdateProject],
                      Field(discriminator='op')]


class EditRequest(Strict):
    revision: int = Field(ge=1)
    author: Author
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ''
    operations: list[Operation] = Field(min_length=1, max_length=500)
    # Entities the request may change, when its author limited it (alcance); new entities are always allowed.
    scope: list[EntityId] | None = Field(default=None, max_length=500)
    # An explicit request to replace the author's choices (Q13); without it they stay protected.
    replace_human: bool = False


class HistoryRequest(Strict):
    revision: int = Field(ge=1)
    author: Author


class CreateRequest(Strict):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ''
    channel_id: str | None = None
    format: Format = Field(default_factory=Format)
    author: Author


LABELS = {'add_scene': 'Adicionar cena', 'update_scene': 'Alterar cena', 'move_scene': 'Mover cena',
          'remove_scene': 'Remover cena', 'add_track': 'Adicionar faixa', 'remove_track': 'Remover faixa',
          'add_item': 'Inserir item', 'update_item': 'Alterar item', 'set_style': 'Alterar estilo',
          'set_keyframes': 'Alterar pontos no tempo',
          'split_item': 'Cortar item', 'remove_item': 'Remover item', 'add_resource': 'Importar recurso',
          'remove_resource': 'Remover recurso', 'update_project': 'Alterar projeto'}
COLLECTIONS = {'scene': 'scenes', 'track': 'tracks', 'item': 'items', 'resource': 'resources'}
PROJECT_FIELDS = ('title', 'format', 'channel_name', 'brand', 'voice')
FIELD_NAMES = {'track_id': 'a faixa', 'scene_id': 'a cena', 'start_ms': 'o início', 'duration_ms': 'a duração',
               'source_start_ms': 'o recorte', 'layer': 'a ordem visual', 'geometry': 'a posição e o tamanho',
               'text': 'o texto', 'resource': 'a mídia', 'enter': 'a entrada', 'exit': 'a saída',
               'speed': 'a velocidade', 'freeze': 'o congelamento'}


def blank(title, format, channel_id):
    return {'schema_version': SCHEMA_VERSION, 'revision': 1, 'title': title or 'Novo vídeo', 'channel_id': channel_id,
            'format': format, 'channel_name': None, 'brand': None, 'voice': None,
            'scenes': [{'id': store.uid(), 'title': 'Cena 1', 'duration_ms': 5000}],
            'tracks': [{'id': store.uid(), 'kind': kind, 'name': name} for kind, name in TRACKS.items()],
            'items': [], 'resources': []}


def create(body: CreateRequest):
    channel_id = body.channel_id or store.DEFAULT_CHANNEL
    try:
        store.get_channel(channel_id)
    except store.Missing:
        raise ValueError('Escolha um canal existente para o projeto.') from None
    project_id, now = store.uid(), time.time()
    document = blank(body.title, body.format.model_dump(), channel_id)
    with store.connect() as db:
        db.execute('INSERT INTO edit_projects VALUES(?,?,?,?)', (project_id, dump(document), now, now))
        record(db, project_id, 'create', 1, body.author.model_dump(), 'Criar projeto', [], [])
    return get(project_id)


def dump(value):
    return json.dumps(value, ensure_ascii=False)


# What an item has before any effect is chosen; documents and history from schema 1 gain these on reading.
EFFECTS = {'keyframes': {}, 'enter': None, 'exit': None, 'speed': 1.0, 'freeze': None}


def upgrade(document):
    for item in document['items']:
        for name, value in EFFECTS.items():
            item.setdefault(name, copy.deepcopy(value))
    document['schema_version'] = SCHEMA_VERSION
    return document


def row_document(row):
    if row is None:
        raise store.Missing('Projeto não encontrado.')
    return upgrade(json.loads(row['document']))


def load(db, project_id):
    return row_document(db.execute('SELECT document FROM edit_projects WHERE id=?', (project_id,)).fetchone())


def record(db, project_id, kind, revision, author, label, targets, changes, state='done', ref=None):
    seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM edit_history WHERE project_id=?', (project_id,)).fetchone()[0]
    entry_id = store.uid()
    db.execute('INSERT INTO edit_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
               (entry_id, project_id, seq, revision, kind, state, dump(author), label, dump(targets), dump(changes),
                dump(sorted(change_resources(changes))), ref, time.time()))
    return entry_id


def change_resources(changes):
    return {value['hash'] for change in changes if change['kind'] == 'resource'
            for value in (change['before'], change['after']) if value}


def get(project_id):
    with store.connect() as db:
        row = db.execute('SELECT * FROM edit_projects WHERE id=?', (project_id,)).fetchone()
        document = row_document(row)
        undo, redo = undoable(db, project_id), redoable(db, project_id)
    return present(document, row, undo, redo)


def all_projects():
    with store.connect() as db:
        rows = db.execute('SELECT * FROM edit_projects ORDER BY updated_at DESC').fetchall()
    return [summary(row_document(row), row) for row in rows]


def summary(document, row):
    channel = store.get_channel(document['channel_id'])
    return {'id': row['id'], 'title': document['title'], 'format': document['format'], 'revision': document['revision'],
            'scenes': len(document['scenes']), 'duration_ms': duration(document),
            'channel': {key: channel[key] for key in ('id', 'name', 'brand')}, 'updated_at': row['updated_at']}


def duration(document):
    scenes = sum(scene['duration_ms'] for scene in document['scenes'])
    return max([scenes, *(item['start_ms'] + item['duration_ms'] for item in document['items'])])


def aspect(width, height):
    divisor = math.gcd(width, height)
    return f'{width // divisor}:{height // divisor}'


def present(document, row, undo=None, redo=None):
    project = copy.deepcopy(document)
    channel = store.get_channel(document['channel_id'])
    project.update(id=row['id'], created_at=row['created_at'], updated_at=row['updated_at'])
    project['channel'] = {key: channel[key] for key in ('id', 'name', 'brand', 'voice')}
    own = {'channel_name': document['channel_name'], 'brand': document['brand'], 'voice': document['voice']}
    fallback = {'channel_name': channel['name'], 'brand': channel['brand'], 'voice': channel['voice']}
    project['inherited'] = {key: {'value': fallback[key] if own[key] is None else own[key], 'inherited': own[key] is None}
                            for key in own}
    width, height = document['format']['width'], document['format']['height']
    project['aspect'] = aspect(width, height)
    # Horizontal videos keep the framing still on the frame; the camera of MYC-24 will move it over the space.
    project['framing'] = {'x': 0, 'y': 0, 'width': width, 'height': height}
    start = 0
    for scene in project['scenes']:
        scene['start_ms'] = start
        start += scene['duration_ms']
    kinds = {track['id']: track['kind'] for track in document['tracks']}
    for item in project['items']:
        item['resolved_style'] = resolved_style(item, kinds[item['track_id']])
        item['in_frame'] = placement(item.get('geometry'), width, height)
    project['duration_ms'] = duration(document)
    project['undo'] = undo and {'label': undo['label'], 'author': json.loads(undo['author'])}
    project['redo'] = redo and {'label': redo['label'], 'author': json.loads(redo['author'])}
    return project


def style_group(kind):
    return 'audio' if kind in AUDIO else kind


def resolved_style(item, kind):
    inherited = TEMPLATE[style_group(kind)]
    return {name: {'value': item['style'].get(name, value), 'inherited': name not in item['style']}
            for name, value in inherited.items()}


def placement(geometry, width, height):
    if geometry is None:
        return None
    left, top = max(geometry['x'], 0), max(geometry['y'], 0)
    right, bottom = min(geometry['x'] + geometry['width'], width), min(geometry['y'] + geometry['height'], height)
    if right <= left or bottom <= top:
        return 'outside'
    inside = geometry['x'] >= 0 and geometry['y'] >= 0 and geometry['x'] + geometry['width'] <= width \
        and geometry['y'] + geometry['height'] <= height
    return 'inside' if inside else 'partial'


def undoable(db, project_id):
    """The latest request still applied; undo walks the history back one request at a time."""
    return db.execute("SELECT * FROM edit_history WHERE project_id=? AND kind='apply' AND state='done' "
                      "ORDER BY seq DESC LIMIT 1", (project_id,)).fetchone()


def redoable(db, project_id):
    # The undone requests form a stack: the earliest of them was the last one undone.
    return db.execute("SELECT * FROM edit_history WHERE project_id=? AND kind='apply' AND state='undone' "
                      "ORDER BY seq LIMIT 1", (project_id,)).fetchone()


def history(project_id):
    with store.connect() as db:
        load(db, project_id)
        rows = db.execute('SELECT * FROM edit_history WHERE project_id=? ORDER BY seq', (project_id,)).fetchall()
    return {'entries': [{'id': row['id'], 'revision': row['revision'], 'kind': row['kind'], 'state': row['state'],
                         'author': json.loads(row['author']), 'label': row['label'], 'targets': json.loads(row['targets']),
                         'created_at': row['created_at']} for row in rows]}


def within(low, high):
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and low <= v <= high


# Ranges of every number an item can show, as a single value or at a point in time.
RANGES = {'x': within(-SPACE_LIMIT, SPACE_LIMIT), 'y': within(-SPACE_LIMIT, SPACE_LIMIT), 'opacity': within(0, 1),
          'scale': within(0.01, 20), 'rotation': within(-3600, 3600), 'brightness': within(0, 3), 'contrast': within(0, 3),
          'saturation': within(0, 3), 'blur': within(0, 100), 'zoom': within(0.1, 10), 'pan_x': within(-1, 1),
          'pan_y': within(-1, 1)}
STYLE_RULES = {
    **RANGES,
    'volume': within(0, 2),
    'font_size': within(8, 400),
    'fit': lambda v: v in ('cover', 'contain'),
    'align': lambda v: v in ('left', 'center', 'right'),
    'color': lambda v: isinstance(v, str) and len(v) == 7 and v[0] == '#' and all(c in '0123456789abcdefABCDEF' for c in v[1:]),
    'font_family': lambda v: isinstance(v, str) and 0 < len(v.strip()) <= 150,
}
NAMES = {'scene': 'A cena', 'track': 'A faixa', 'item': 'O item', 'resource': 'O recurso'}


def key(kind):
    return 'hash' if kind == 'resource' else 'id'


def locate(document, kind, entity_id):
    if kind == 'project':
        return 0, {field: document[field] for field in PROJECT_FIELDS}
    for index, value in enumerate(document[COLLECTIONS[kind]]):
        if value[key(kind)] == entity_id:
            return index, value
    return None, None


class Draft:
    """A working copy of the document that one request changes; nothing is saved unless every operation passes."""

    def __init__(self, document, author, replace_human, db):
        self.original, self.doc = document, copy.deepcopy(document)
        self.author, self.replace_human, self.db = author, replace_human, db
        self.touched = {}

    def find(self, kind, entity_id):
        index, value = locate(self.doc, kind, entity_id)
        if value is None:
            raise ValueError(f'{NAMES[kind]} {entity_id} não existe neste projeto.')
        self.touched[kind, entity_id] = True
        return index, value

    def new_id(self, wanted):
        entity_id = wanted or store.uid()
        if any(locate(self.doc, kind, entity_id)[1] is not None for kind in ('scene', 'track', 'item')):
            raise ValueError(f'Já existe um conteúdo com o identificador {entity_id}.')
        return entity_id

    def insert(self, kind, value, index=None):
        values = self.doc[COLLECTIONS[kind]]
        values.insert(len(values) if index is None else min(index, len(values)), value)
        self.touched[kind, value[key(kind)]] = True

    def remove(self, kind, entity_id):
        index, _ = self.find(kind, entity_id)
        del self.doc[COLLECTIONS[kind]][index]

    def track_kind(self, track_id):
        _, track = locate(self.doc, 'track', track_id)
        if track is None:
            raise ValueError(f'A faixa {track_id} não existe neste projeto.')
        return track['kind']

    def claim(self, item, field):
        """Who changes a field of an item; a choice of the author stays protected from the agents (Q13, ADR 0009)."""
        item['last_author'] = self.author
        if self.author['kind'] == 'human':
            item['human'] = sorted({*item['human'], field})
        elif field in item['human']:
            if not self.replace_human:
                name = FIELD_NAMES.get(field) or (f'os pontos no tempo de {field.removeprefix("keyframes.")}'
                                                  if field.startswith('keyframes.') else f'o estilo {field.removeprefix("style.")}')
                raise store.Conflict(f'O autor escolheu {name} do item {item["id"]}. Para substituir, faça um pedido explícito.')
            item['human'] = [f for f in item['human'] if f != field]

    def check_item(self, item):
        kind = self.track_kind(item['track_id'])
        if item['scene_id'] is not None and locate(self.doc, 'scene', item['scene_id'])[1] is None:
            raise ValueError(f'A cena {item["scene_id"]} não existe neste projeto.')
        if item['resource'] is not None and locate(self.doc, 'resource', item['resource'])[1] is None:
            raise ValueError('Importe o recurso no projeto antes de usá-lo num item.')
        if kind in AUDIO and item['geometry'] is not None:
            raise ValueError('Itens de áudio não têm posição nem tamanho.')
        if kind not in AUDIO and item['geometry'] is None:
            raise ValueError('Itens visuais e de texto precisam de posição e tamanho.')
        if item['text'] is not None and kind != 'text':
            raise ValueError('Somente itens de texto têm texto.')
        if kind != 'visual' and (item['speed'] != 1 or item['freeze']):
            raise ValueError('Velocidade e congelamento valem para clipes da faixa de visuais.')
        if item['freeze'] and item['freeze']['at_ms'] > item['duration_ms'] - item['freeze']['duration_ms']:
            raise ValueError('O quadro congelado precisa cair dentro do clipe.')
        for side in ('enter', 'exit'):
            if item[side] and item[side]['kind'] not in TRANSITIONS[style_group(kind)][side]:
                raise ValueError(f'Itens desta faixa não {"entram" if side == "enter" else "saem"} com {item[side]["kind"]}.')
        return kind

    def check_transitions(self, item, sides):
        for side in sides:
            if item[side] and item[side]['duration_ms'] > item['duration_ms']:
                raise ValueError('A transição não pode durar mais que o item.')

    def check_style(self, kind, name, value):
        if name not in TEMPLATE[style_group(kind)]:
            raise ValueError(f'O estilo {name} não vale para itens desta faixa.')
        if value is not None and not STYLE_RULES[name](value):
            raise ValueError(f'Valor inválido para o estilo {name}.')

    def run(self, op):
        getattr(self, op.op)(op)

    def add_scene(self, op):
        self.insert('scene', {'id': self.new_id(op.scene.id), 'title': op.scene.title, 'duration_ms': op.scene.duration_ms}, op.index)

    def update_scene(self, op):
        _, scene = self.find('scene', op.scene_id)
        for field in ('title', 'duration_ms'):
            if getattr(op, field) is not None:
                scene[field] = getattr(op, field)

    def move_scene(self, op):
        index, scene = self.find('scene', op.scene_id)
        del self.doc['scenes'][index]
        self.insert('scene', scene, op.index)

    def remove_scene(self, op):
        self.find('scene', op.scene_id)
        if len(self.doc['scenes']) == 1:
            raise ValueError('O projeto precisa de ao menos uma cena.')
        if any(item['scene_id'] == op.scene_id for item in self.doc['items']):
            raise ValueError('Remova ou desagrupe os itens da cena antes de removê-la.')
        self.remove('scene', op.scene_id)

    def add_track(self, op):
        self.insert('track', {'id': self.new_id(op.track.id), 'kind': op.track.kind,
                              'name': op.track.name or TRACKS[op.track.kind]}, op.index)

    def remove_track(self, op):
        self.find('track', op.track_id)
        if any(item['track_id'] == op.track_id for item in self.doc['items']):
            raise ValueError('Remova os itens da faixa antes de removê-la.')
        self.remove('track', op.track_id)

    def add_item(self, op):
        given = op.item.model_dump(exclude={'id', 'style'})
        effects = {name: given[name] if given.get(name) is not None else copy.deepcopy(value) for name, value in EFFECTS.items()}
        item = {**given, **effects, 'id': self.new_id(op.item.id), 'source_start_ms': op.item.source_start_ms or 0,
                'layer': op.item.layer or 0, 'style': {}, 'last_author': self.author, 'human': []}
        if item['geometry'] is None and self.track_kind(item['track_id']) not in AUDIO:
            # The frame is the default framing (Q64).
            item['geometry'] = {'x': 0, 'y': 0, 'width': self.doc['format']['width'], 'height': self.doc['format']['height']}
        kind = self.check_item(item)
        self.check_transitions(item, ('enter', 'exit'))
        for name, value in op.item.style.items():
            self.check_style(kind, name, value)
            if value is not None:
                item['style'][name] = value
        if self.author['kind'] == 'human':
            chosen = (op.item.model_fields_set - {'id', 'style'}) | {'start_ms', 'duration_ms'}
            item['human'] = sorted(chosen | {f'style.{name}' for name in item['style']})
        self.insert('item', item)

    def update_item(self, op):
        _, item = self.find('item', op.item_id)
        before = self.track_kind(item['track_id'])
        span, speed = media_span(item), item['speed']
        for field in sorted(op.changes.model_fields_set):
            value = getattr(op.changes, field)
            if value is None and field not in ('scene_id', 'geometry', 'text', 'resource', 'enter', 'exit', 'freeze'):
                raise ValueError(f'Informe {FIELD_NAMES[field]} do item.')
            self.claim(item, field)
            item[field] = value.model_dump() if isinstance(value, BaseModel) else value
        if {'speed', 'freeze'} & op.changes.model_fields_set and 'duration_ms' not in op.changes.model_fields_set:
            # The clip keeps the same stretch of media; only the time it occupies changes (the next items stay put).
            self.claim(item, 'duration_ms')
            if item['freeze'] and 'freeze' not in op.changes.model_fields_set:
                # The held frame stays on the same moment of the media.
                item['freeze'] = {**item['freeze'], 'at_ms': round(item['freeze']['at_ms'] * speed / item['speed'])}
            item['duration_ms'] = max(1, round(span / item['speed'])) + hold(item)
        if style_group(self.check_item(item)) != style_group(before):
            raise ValueError('Um item só muda para uma faixa do mesmo tipo de conteúdo.')
        self.check_transitions(item, {'enter', 'exit'} & op.changes.model_fields_set)

    def set_style(self, op):
        _, item = self.find('item', op.item_id)
        kind = self.track_kind(item['track_id'])
        for name, value in op.values.items():
            self.check_style(kind, name, value)
            self.claim(item, f'style.{name}')
            if value is None:
                item['style'].pop(name, None)
            else:
                item['style'][name] = value

    def set_keyframes(self, op):
        _, item = self.find('item', op.item_id)
        if op.property not in ANIMATED[style_group(self.track_kind(item['track_id']))]:
            raise ValueError(f'A propriedade {op.property} não muda no tempo em itens desta faixa.')
        self.claim(item, f'keyframes.{op.property}')
        if op.points is None:
            item['keyframes'].pop(op.property, None)
            return
        points = sorted((p.model_dump() for p in op.points), key=lambda p: p['at_ms'])
        if len({p['at_ms'] for p in points}) != len(points):
            raise ValueError('Dois pontos no tempo da mesma propriedade não podem cair no mesmo instante.')
        if not points or not all(RANGES[op.property](p['value']) for p in points):
            raise ValueError(f'Valor inválido num ponto no tempo de {op.property}.')
        item['keyframes'][op.property] = points

    def split_item(self, op):
        _, item = self.find('item', op.item_id)
        end = item['start_ms'] + item['duration_ms']
        if not item['start_ms'] < op.at_ms < end:
            raise ValueError('Corte o item num instante entre o início e o fim dele.')
        self.claim(item, 'duration_ms')
        rest = copy.deepcopy(item)
        cut = op.at_ms - item['start_ms']
        item['duration_ms'] = cut
        rest.update(id=self.new_id(op.new_id), start_ms=op.at_ms, duration_ms=end - op.at_ms,
                    source_start_ms=round(source_at(rest, cut)))
        # A held frame stays with the part it falls in, or is shared when the cut crosses it.
        frozen = item['freeze']
        if frozen:
            item['freeze'] = {'at_ms': frozen['at_ms'], 'duration_ms': min(frozen['duration_ms'], cut - frozen['at_ms'])} \
                if frozen['at_ms'] < cut else None
            remaining = frozen['at_ms'] + frozen['duration_ms'] - max(cut, frozen['at_ms'])
            rest['freeze'] = {'at_ms': max(0, frozen['at_ms'] - cut), 'duration_ms': remaining} if remaining > 0 else None
        # The entrance stays with the first part and the exit with the second; a ramp goes on across the cut.
        item['exit'], rest['enter'] = None, None
        for name, points in item['keyframes'].items():
            at_cut = {**next((p for p in reversed(points) if p['at_ms'] <= cut), points[0]), 'value': value_at(points, cut)}
            item['keyframes'][name] = [p for p in points if p['at_ms'] < cut] + [{**at_cut, 'at_ms': cut}]
            rest['keyframes'][name] = [{**at_cut, 'at_ms': 0}] + [{**p, 'at_ms': p['at_ms'] - cut} for p in points if p['at_ms'] > cut]
        if self.author['kind'] == 'agent':
            rest['human'] = [f for f in rest['human'] if f not in ('start_ms', 'source_start_ms')]
        self.insert('item', rest)

    def remove_item(self, op):
        _, item = self.find('item', op.item_id)
        if self.author['kind'] == 'agent' and item['human'] and not self.replace_human:
            raise store.Conflict(f'O item {item["id"]} tem escolhas do autor. Para removê-lo, faça um pedido explícito.')
        self.remove('item', op.item_id)

    def add_resource(self, op):
        row = self.db.execute('SELECT * FROM resources WHERE hash=?', (op.hash,)).fetchone()
        if row is None:
            raise ValueError('O recurso não está no acervo.')
        if locate(self.doc, 'resource', op.hash)[1] is not None:
            raise ValueError('Este recurso já está no projeto.')
        self.insert('resource', {'hash': op.hash, 'name': op.name, 'media_type': row['media_type'], 'size': row['size']})

    def remove_resource(self, op):
        self.find('resource', op.hash)
        if any(item['resource'] == op.hash for item in self.doc['items']):
            raise ValueError('O recurso ainda é usado por um item da timeline.')
        self.remove('resource', op.hash)

    def update_project(self, op):
        self.touched['project', None] = True
        for field in op.model_fields_set - {'op'}:
            value = getattr(op, field)
            if value is None and field in ('title', 'format'):
                raise ValueError('Informe o título e o formato do projeto.')
            self.doc[field] = value.model_dump() if isinstance(value, BaseModel) else value

    def changes(self):
        """Before and after of each entity the request touched, in the order of the document."""
        result = []
        for kind, entity_id in self.touched:
            index_before, before = locate(self.original, kind, entity_id)
            index_after, after = locate(self.doc, kind, entity_id)
            if (before, index_before) != (after, index_after):
                result.append({'kind': kind, 'id': entity_id, 'before': copy.deepcopy(before), 'after': copy.deepcopy(after),
                               'index_before': index_before, 'index_after': index_after})
        return result


def hold(item):
    return item['freeze']['duration_ms'] if item['freeze'] else 0


def media_span(item):
    """How much of the media the clip shows, in ms of the media."""
    return (item['duration_ms'] - hold(item)) * item['speed']


def source_at(item, local_ms):
    """Moment of the media shown at local_ms of the item, as the composition resolves it (web/src/engine/timeline.ts)."""
    played = local_ms
    if item['freeze']:
        at, length = item['freeze']['at_ms'], item['freeze']['duration_ms']
        played = local_ms if local_ms < at else max(at, local_ms - length)
    return item['source_start_ms'] + played * item['speed']


def value_at(points, local):
    """A property at local ms between its points in time, as the composition interpolates it (timeline.ts)."""
    if local <= points[0]['at_ms']:
        return points[0]['value']
    if local >= points[-1]['at_ms']:
        return points[-1]['value']
    a, b = next((a, b) for a, b in zip(points, points[1:]) if b['at_ms'] > local)
    p = (local - a['at_ms']) / (b['at_ms'] - a['at_ms'])
    eased = 0 if a['easing'] == 'hold' else p * p * (3 - 2 * p) if a['easing'] == 'ease' else p
    return round(a['value'] + (b['value'] - a['value']) * eased, 6)


def restore(document, changes, side):
    """Put back each changed entity as it was on one side of a request; the others keep their relative order."""
    for kind, collection in COLLECTIONS.items():
        mine = [c for c in changes if c['kind'] == kind]
        if not mine:
            continue
        ids = {c['id'] for c in mine}
        values = [v for v in document[collection] if v[key(kind)] not in ids]
        for change in sorted((c for c in mine if c[side] is not None), key=lambda c: c[f'index_{side}']):
            values.insert(change[f'index_{side}'], copy.deepcopy(change[side]))
        document[collection] = values
    for change in changes:
        if change['kind'] == 'project':
            document.update(copy.deepcopy(change[side]))


def locked(db, project_id, revision):
    db.execute('BEGIN IMMEDIATE')
    document = load(db, project_id)
    if document['revision'] != revision:
        raise store.Conflict('O projeto mudou depois que você o abriu. Atualize-o antes de editar.')
    return document


def save(db, project_id, document):
    document['revision'] += 1
    db.execute('UPDATE edit_projects SET document=?, updated_at=? WHERE id=?', (dump(document), time.time(), project_id))
    return document['revision']


def apply(project_id, body: EditRequest):
    """Validate, apply and record one request atomically; a refused request leaves the document as it was."""
    author = body.author.model_dump()
    with store.connect() as db:
        document = locked(db, project_id, body.revision)
        draft = Draft(document, author, body.replace_human, db)
        for operation in body.operations:
            draft.run(operation)
        changes = draft.changes()
        if body.scope is not None:
            outside = [c['id'] or 'project' for c in changes if c['before'] is not None and (c['id'] or 'project') not in body.scope]
            if outside:
                raise ValueError(f'O pedido alcança conteúdos fora do seu alcance: {", ".join(outside)}.')
        if not changes:
            raise ValueError('O pedido não altera o projeto.')
        revision = save(db, project_id, draft.doc)
        # A new request after undo closes the way back to what was undone.
        db.execute("UPDATE edit_history SET state='discarded' WHERE project_id=? AND kind='apply' AND state='undone'", (project_id,))
        label = body.label or (LABELS[body.operations[0].op] if len(body.operations) == 1 else 'Alterações')
        record(db, project_id, 'apply', revision, author, label, [c['id'] or 'project' for c in changes], changes)
    return get(project_id)


SIDES = {'undo': ('before', 'undone', undoable, 'Não há o que desfazer.'),
         'redo': ('after', 'done', redoable, 'Não há o que refazer.')}


def undo(project_id, body: HistoryRequest):
    return walk(project_id, body, 'undo')


def redo(project_id, body: HistoryRequest):
    return walk(project_id, body, 'redo')


def walk(project_id, body: HistoryRequest, kind):
    """Undo or redo one whole request; the step itself is a new revision with its own author in the history."""
    side, state, pick, nothing = SIDES[kind]
    with store.connect() as db:
        document = locked(db, project_id, body.revision)
        entry = pick(db, project_id)
        if entry is None:
            raise store.Conflict(nothing)
        if body.author.kind == 'agent' and json.loads(entry['author'])['kind'] == 'human':
            # Undoing would replace the author's choices as surely as editing them (Q13).
            raise store.Conflict(f'"{entry["label"]}" foi feito pelo autor; só ele pode desfazer ou refazer.')
        changes = json.loads(entry['changes'])
        restore(document, changes, side)
        revision = save(db, project_id, document)
        db.execute('UPDATE edit_history SET state=? WHERE id=?', (state, entry['id']))
        if kind == 'undo':
            changes = [c | {'before': c['after'], 'after': c['before'], 'index_before': c['index_after'],
                            'index_after': c['index_before']} for c in changes]
        record(db, project_id, kind, revision, body.author.model_dump(), entry['label'],
               json.loads(entry['targets']), changes, ref=entry['id'])
    return get(project_id)


def references(db):
    """Who still needs each content: a project's document, its preserved history or an export to render (ADR 0015)."""
    found = {}
    for row in db.execute('SELECT id, document FROM edit_projects'):
        for resource in json.loads(row['document'])['resources']:
            found.setdefault(resource['hash'], {}).setdefault(row['id'], set()).add('document')
    for row in db.execute('SELECT project_id, resources FROM edit_history'):
        for digest in json.loads(row['resources']):
            found.setdefault(digest, {}).setdefault(row['project_id'], set()).add('history')
    # An export still to render reads the media of its frozen revision (Q47).
    for row in db.execute("SELECT project_id, document FROM edit_exports WHERE state IN ('queued','running')"):
        for resource in json.loads(row['document'])['resources']:
            found.setdefault(resource['hash'], {}).setdefault(row['project_id'], set()).add('export')
    return found


def import_resource(project_id, revision, author, stream, name, declared):
    """Keep the file in the shared archive (acervo) and reference it from the project through an operation."""
    from . import resources
    with resources.LOCK:
        with store.connect() as db:
            load(db, project_id)
            digest, _, created = resources.keep(db, stream, declared)
        try:
            if any(r['hash'] == digest for r in get(project_id)['resources']):
                return get(project_id)
            return apply(project_id, EditRequest(revision=revision, author=author, operations=[
                AddResource(op='add_resource', hash=digest, name=name)]))
        except BaseException:
            with store.connect() as db:
                paths = resources.forget(db, [digest])[1] if created and digest not in references(db) else []
            for path in paths:
                path.unlink(missing_ok=True)
            raise


def archive():
    with store.connect() as db:
        found = references(db)
        titles = {row['id']: json.loads(row['document'])['title'] for row in db.execute('SELECT id, document FROM edit_projects')}
        rows = db.execute('SELECT * FROM resources ORDER BY created_at').fetchall()
    listed = [{'hash': row['hash'], 'size': row['size'], 'media_type': row['media_type'],
               'references': [{'project_id': pid, 'title': titles[pid], 'document': 'document' in where, 'history': 'history' in where}
                              for pid, where in sorted(found.get(row['hash'], {}).items())]} for row in rows]
    return {'resources': listed, 'total_bytes': sum(r['size'] for r in listed)}


def resource_file(project_id, digest):
    from . import resources
    with store.connect() as db:
        row = db.execute('SELECT media_type FROM resources WHERE hash=?', (digest,)).fetchone()
        if row is None or project_id not in references(db).get(digest, {}):
            raise store.Missing('Recurso não encontrado neste projeto.')
    return resources.path(digest), row['media_type']


class CleanupRequest(Strict):
    kind: Literal['history']
    revision: int = Field(ge=1)
    author: Author


def history_only(found, project_id):
    """Contents that only this project's history keeps: what deleting that history really frees."""
    return [digest for digest, users in found.items() if users == {project_id: {'history'}}]


def storage(project_id):
    with store.connect() as db:
        document = load(db, project_id)
        found = references(db)
        sizes = {row['hash']: row['size'] for row in db.execute('SELECT hash, size FROM resources')}
        entries = db.execute("SELECT COUNT(*) FROM edit_history WHERE project_id=?", (project_id,)).fetchone()[0]
    names = {r['hash']: r['name'] for r in document['resources']}
    mine = {digest: users for digest, users in found.items() if project_id in users and digest in sizes}
    listed = [{'hash': digest, 'name': names.get(digest), 'size': sizes[digest], 'in_document': 'document' in users[project_id],
               'in_history': 'history' in users[project_id], 'other_projects': len(users) - 1}
              for digest, users in sorted(mine.items())]
    return {'referenced_bytes': sum(r['size'] for r in listed),
            'shared_bytes': sum(r['size'] for r in listed if r['other_projects']),
            'resources': listed,
            'cleanups': [{'kind': 'history', 'label': 'Apagar o histórico de edição', 'entries': entries,
                          'frees_bytes': sum(sizes[d] for d in history_only(mine, project_id))}]}


def cleanup(project_id, body: CleanupRequest):
    """Only by the author's choice (Q40): the history goes, the document stays, and so does every content still used."""
    from . import resources
    with resources.LOCK:
        with store.connect() as db:
            locked(db, project_id, body.revision)
            freeable = history_only(references(db), project_id)
            db.execute('DELETE FROM edit_history WHERE project_id=?', (project_id,))
            record(db, project_id, 'cleanup', body.revision, body.author.model_dump(), 'Apagar o histórico de edição', [], [])
            freed, paths = resources.forget(db, freeable)
        for path in paths:
            path.unlink(missing_ok=True)
    return {'freed_bytes': freed, 'project': get(project_id), 'storage': storage(project_id)}
