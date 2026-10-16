"""Local deterministic bridge for browser tests; never executes a provider CLI.

Besides the scene proposals, it answers a Short livre's agents with the reference prompt's script and direction, and
the Arte with a plain image, as the backend's end-to-end test does."""
import io
import json
import os
from pathlib import Path
import signal
import sys
import time
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend' / 'tests'))
import reference_agents as reference

root = Path(os.environ['MYCUT_BLOCK_TEST_DATA']).resolve()
if not root.is_relative_to('/tmp'):
    raise SystemExit('This fixture only accepts isolated /tmp data.')
bridge = root / 'agent-bridge'
bridge.mkdir(parents=True, exist_ok=True)
active = True


def reference_flow(narration):
    """Usuário → Agente de IA → Ferramenta → Resposta, anchored to words present in the narration."""
    words = {w.strip('.,').lower() for w in narration.split()}
    anchor = lambda word: word if word in words else None
    node = lambda id, label, icon, x, y, size=22, shape='circle', chart=None: {
        'id': id, 'label': label, 'icon': icon, 'shape': shape, 'x': x, 'y': y, 'size': size, 'chart': chart}
    return {'nodes': [node('usuario', 'Usuário', 'user', 20, 14), node('agente', 'Agente de IA', 'bot', 50, 46, 24, 'rounded'),
                      node('ferramenta', 'Ferramenta', 'wrench', 80, 14),
                      node('resposta', 'Resposta', None, 50, 84, 56, 'rounded',
                           {'kind': 'bars', 'values': [12, 30, 54], 'labels': ['seg', 'ter', 'qua'], 'maximum': None, 'unit': '%'})],
            'links': [{'source': 'usuario', 'target': 'agente'}, {'source': 'agente', 'target': 'ferramenta'},
                      {'source': 'agente', 'target': 'resposta'}],
            'steps': [{'source': 'usuario', 'target': 'agente', 'kind': 'request', 'anchor': anchor('pedido')},
                      {'source': 'agente', 'target': 'ferramenta', 'kind': 'request', 'anchor': anchor('chama')},
                      {'source': 'ferramenta', 'target': 'agente', 'kind': 'result', 'anchor': anchor('devolve')},
                      {'source': 'agente', 'target': 'resposta', 'kind': 'result', 'anchor': anchor('resposta')}]}


def proposal(request):
    payload = json.loads(request['prompt'].split('\nDADOS:\n', 1)[1])
    blocks = payload['scene']['blocks']
    for block in blocks:
        if (block.get('object') or {}).get('id') == payload['target_id']:
            if block['object']['type'] == 'flow':
                block['object']['flow'] = reference_flow(payload['scene']['narration'])
            else:
                block['object']['text'] = 'Uma ideia mais clara'
    return {'reply': 'Proposta simulada para verificar a revisão no editor.', 'blocks': blocks}


def picture(folder):
    """The Arte's image, saved where the runner saves what the CLI generated."""
    count = len(list((bridge / 'requests').glob('*/outputs/1.png')))
    (folder / 'outputs').mkdir(exist_ok=True)
    out = io.BytesIO()
    Image.new('RGB', (96, 160), (40 + 30 * count % 200, 90, 120)).save(out, format='PNG')
    (folder / 'outputs' / '1.png').write_bytes(out.getvalue())
    return {'message': 'Imagem criada.'}


ANSWERS = {'Proposal': proposal, 'FreeScript': lambda _: reference.script(), 'FreeDirection': lambda _: reference.direction(),
           'Review': lambda _: reference.APPROVED}


def stop(*_):
    global active
    active = False


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    while active:
        heartbeat = {'time': time.time(), 'protocol': 4, 'providers': {'codex': True, 'claude': True, 'grok': True}}
        temporary = bridge / 'test-heartbeat.tmp'
        temporary.write_text(json.dumps(heartbeat))
        temporary.replace(bridge / 'heartbeat.json')
        for path in (bridge / 'requests').glob('*/request.json'):
            response = path.with_name('response.json')
            if response.exists():
                continue
            request = json.loads(path.read_text())
            if request.get('kind') == 'image':
                result = {'result': picture(path.parent), 'usage': []}
            elif request.get('schema', {}).get('title') in ANSWERS:
                result = {'result': ANSWERS[request['schema']['title']](request)}
            else:
                continue
            tmp = response.with_suffix('.tmp')
            tmp.write_text(json.dumps(result, ensure_ascii=False))
            tmp.replace(response)
        time.sleep(.25)
finally:
    (bridge / 'heartbeat.json').unlink(missing_ok=True)
