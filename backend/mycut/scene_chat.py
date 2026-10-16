"""Durable scene conversations. Agents propose; only an explicit choice edits."""
import copy
import json
import sqlite3
import sys
import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from . import store, bridge, integrations, agent_models
from .config import DATA
from .scene_layout import Id, SceneBlock, scoped_blocks, target, validate_assets, shot_of, shot_view, with_shot_blocks, shots
from .models import Scene, ProjectInput


class ThreadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scene_id: Id
    scope: Literal['object', 'block', 'scene']
    target_id: Id
    marked: bool = True
    resolved: bool = False


class MessageRequest(ThreadRequest):
    text: str = Field(min_length=1, max_length=4000)
    revision: int = Field(ge=1)


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reply: str = Field(min_length=1, max_length=4000)
    blocks: list[SceneBlock] | None = Field(default=None, min_length=1, max_length=100)


def scene_in(project, scene_id):
    scene = next((s for s in project['scenes'] if s.get('id') == scene_id), None)
    if scene is None or scene.get('blocks') is None:
        raise ValueError('Salve uma cena com blocos antes de conversar com o agente.')
    return scene


def scope_snapshot(project, scene, scope, target_id):
    blocks = shot_of(scene, scope, target_id)['blocks']
    return {'target': copy.deepcopy(target(scene, scope, target_id)),
            'style': project.get('visual_style'), 'accent': project.get('accent'),
            'narration': scene['narration'],
            'structure': [[b['id'], b['width'], b['height'], b['align']] for b in blocks]}


def thread(project_id, body):
    project = store.get_project(project_id)
    scene = scene_in(project, body.scene_id)
    target(scene, body.scope, body.target_id)
    with store.connect() as db:
        db.execute('INSERT INTO scene_threads VALUES(?,?,?,?,?,?,?) '
                   'ON CONFLICT(project_id,scene_id,scope,target_id) DO UPDATE SET marked=excluded.marked,resolved=excluded.resolved',
                   (store.uid(), project_id, body.scene_id, body.scope, body.target_id, body.marked, body.resolved))
        return dict(db.execute('SELECT * FROM scene_threads WHERE project_id=? AND scene_id=? AND scope=? AND target_id=?',
                               (project_id, body.scene_id, body.scope, body.target_id)).fetchone())


def messages(project_id):
    project = store.get_project(project_id)
    with store.connect() as db:
        threads = [dict(r) for r in db.execute('SELECT * FROM scene_threads WHERE project_id=?', (project_id,))]
        rows = db.execute("SELECT * FROM jobs WHERE project_id=? AND mode='scene_edit' ORDER BY created_at", (project_id,)).fetchall()
        decisions = {r['job_id']: r['decision'] for r in db.execute('SELECT scene_decisions.* FROM scene_decisions JOIN jobs ON jobs.id=scene_decisions.job_id WHERE jobs.project_id=?', (project_id,))}
    for item in threads:
        try:
            target(scene_in(project, item['scene_id']), item['scope'], item['target_id'])
            item['archived'] = False
        except ValueError:
            item['archived'] = True
    result = []
    for row in rows:
        snapshot = json.loads(row['snapshot'])
        request = snapshot['_scene_edit']
        output = json.loads(row['output']) if row['output'] else None
        stale = False
        try:
            scene = scene_in(project, request['scene_id'])
            stale = scope_snapshot(project, scene, request['scope'], request['target_id']) != request['baseline']
        except ValueError:
            stale = True
        result.append({'id': row['id'], 'thread_id': request['thread_id'], 'text': request['text'],
                       'created_at': row['created_at'], 'state': row['state'], 'status': row['message'],
                       'stale': stale, 'decision': decisions.get(row['id']),
                       'reply': (output or {}).get('reply', ''), 'blocks': (output or {}).get('blocks')})
    return {'threads': threads, 'messages': result}


def enqueue(project_id, body):
    if not body.text.strip():
        raise ValueError('Escreva sua mensagem para o agente.')
    settings = integrations.read()
    config = settings['agents']['director']
    bridge.require([config['provider']])
    agent_models.validate(config)
    current_thread = thread(project_id, body)
    history = messages(project_id)['messages']
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        project = store.project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
        if project['revision'] != body.revision:
            raise store.Conflict('O projeto mudou. Atualize antes de enviar a mensagem.')
        scene = scene_in(project, body.scene_id)
        project['_kind'] = 'scene_edit'
        project['_agents'] = settings['agents']
        project['_scene_edit'] = {**body.model_dump(), 'thread_id': current_thread['id'],
            'baseline': scope_snapshot(project, scene, body.scope, body.target_id),
            'history': [{'user': m['text'], 'assistant': m['reply']} for m in history if m['thread_id'] == current_thread['id']][-12:]}
        identity, now = store.uid(), time.time()
        try:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',
                (identity, project_id, 'scene_edit', 'queued', 0, 'Aguardando o agente', json.dumps(project, ensure_ascii=False), None, now, now))
            db.execute('INSERT INTO job_inputs VALUES(?,?)', (identity, json.dumps(project, ensure_ascii=False)))
        except sqlite3.IntegrityError:
            raise store.Conflict('Espere a proposta atual terminar ou cancele-a antes de enviar outra mensagem.') from None
    return {'id': identity}


def proposed_scene(current, job):
    request, output = job['snapshot']['_scene_edit'], job['output']
    scene = scene_in(current, request['scene_id'])
    if scope_snapshot(current, scene, request['scope'], request['target_id']) != request['baseline']:
        raise store.Conflict('Proposta desatualizada. Peça uma nova considerando a edição atual.')
    if job['state'] != 'succeeded' or not output or output.get('blocks') is None:
        raise ValueError('Esta mensagem não tem uma proposta pronta para aceitar.')
    blocks = scoped_blocks(scene, output['blocks'], request['scope'], request['target_id'])
    plano = shot_of(scene, request['scope'], request['target_id'])['id']
    proposed = Scene.model_validate(with_shot_blocks(scene, plano, blocks)).model_dump()
    validate_assets(proposed, current)
    return proposed


def choose(project_id, job_id, decision, revision):
    job = store.get_job(job_id, private=True)
    if job['project_id'] != project_id or job['kind'] != 'scene_edit':
        raise store.Missing('Proposta não encontrada neste projeto.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM scene_decisions WHERE job_id=?', (job_id,)).fetchone():
            raise store.Conflict('Esta proposta já foi aceita ou descartada.')
        current = store.project_row(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
        if decision == 'accepted':
            if current['revision'] != revision:
                raise store.Conflict('Salve e atualize o projeto antes de aceitar.')
            if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('queued','running') AND mode NOT IN ('cover','scene_edit')", (project_id,)).fetchone():
                raise store.Conflict('Espere a produção terminar antes de aceitar a proposta.')
            scene = proposed_scene(current, job)
            current['scenes'] = [scene if s.get('id') == scene['id'] else s for s in current['scenes']]
            ProjectInput.model_validate({k: current.get(k, f.default) for k, f in ProjectInput.model_fields.items()})
            current['revision'] += 1
            document = {k: v for k, v in current.items() if k not in ('id', 'created_at', 'updated_at')}
            db.execute('UPDATE projects SET document=?,updated_at=? WHERE id=?', (json.dumps(document, ensure_ascii=False), time.time(), project_id))
        db.execute('INSERT INTO scene_decisions VALUES(?,?)', (job_id, decision))
    return store.get_project(project_id)


def run(job):
    from .pipeline import agent
    from .block_render import inspect
    from . import flow
    project = job['snapshot']
    request = project['_scene_edit']
    scene = scene_in(project, request['scene_id'])
    planos = shots(scene)
    plano = shot_of(scene, request['scope'], request['target_id'])['id']
    position = next(i for i, shot in enumerate(planos) if shot['id'] == plano)
    corrections = []
    for attempt in (1, 2):
        proposal = agent(job, 'director',
            'Converse sobre a composição da cena. Se não houver pedido de mudança, responda com blocks=null. '
            'Para mudar, entregue TODOS os blocos do plano em blocks, mas altere somente o alvo e alcance escolhidos. '
            'A cena pode ter vários planos; você vê e altera somente o plano informado em shot. '
            'Um bloco tem zero ou um objeto: title, paragraph, image, video ou flow. Alturas somam 100. '
            'Ao mudar altura do alvo, mova apenas uma borda: compense a diferença em um único bloco vizinho imediato; não altere seus outros campos. '
            'Mantenha IDs existentes, inclusive ao trocar tipo; novos blocos/objetos recebem IDs hexadecimais de 32 caracteres únicos. '
            'Não altere narração nem marca/legendas. Use somente asset_id disponíveis e fontes Google Fonts conhecidas, '
            'ou font=null para herdar. Nunca prometa geração de arquivo ou mudança já aplicada. '
            'O usuário aceitará a proposta na prévia. Priorize texto conciso que caiba na área. '
            'Se o alvo for um objeto flow ainda sem flow (ausente ou null), monte agora um Fluxo animado completo a partir da narração da cena, '
            'mesmo que a mensagem não detalhe nada: você decide nós, posições, conexões, etapas, âncoras e animação. '
            'Quando o alcance for a cena inteira e o pedido permitir, prefira transformar o conteúdo central em um Fluxo animado. '
            'Objetos que não são flow usam flow=null. ' + flow.GUIDE + ' Corrija os problemas em issues_to_fix.',
            {'scene': shot_view(scene, plano), 'scope': request['scope'], 'target_id': request['target_id'],
             'shot': {'number': position+1, 'count': len(planos), 'anchor': planos[position].get('anchor')},
             'message': request['text'], 'history': request['history'], 'style': project.get('visual_style'),
             'flow_icons': flow.icon_names(), 'issues_to_fix': corrections,
             'images': [{k: v for k, v in r.items() if k != 'path'} for r in project.get('images', [])],
             'videos': [{k: v for k, v in r.items() if k not in ('path', 'poster_path')} for r in project.get('videos', [])]},
            Proposal, attempt=attempt)
        output = proposal.model_dump()
        if output['blocks'] is None:
            break
        blocks = scoped_blocks(scene, output['blocks'], request['scope'], request['target_id'])
        changed = Scene.model_validate(with_shot_blocks(scene, plano, blocks)).model_dump()
        validate_assets(changed, project)
        report = inspect(changed, project)
        corrections = [item['message'] for item in report['issues'] + report['warnings']]
        if not corrections:
            break
        if attempt == 2 and report['issues']:
            raise ValueError('A proposta não cabe na cena: '+report['issues'][0]['message']+' Peça uma proposta mais concisa.')
    folder = DATA / 'projects' / project['id'] / 'renders' / job['id']
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'result.json').write_text(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    run(store.get_job(sys.argv[1], private=True))
