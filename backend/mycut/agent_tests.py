"""Bounded, asynchronous probes through the same host queue as production."""
import fcntl
import json
import re
import secrets
import time
import uuid
from . import bridge, agent_models, store


def location(test_id):
    if not re.fullmatch(r'[0-9a-f]{32}', test_id):
        raise store.Missing('Teste não encontrado.')
    folder = bridge.BRIDGE / 'requests' / test_id
    try:
        request = json.loads((folder / 'request.json').read_text())
        if request.get('kind') != 'probe':
            raise ValueError()
        return folder, request
    except (OSError, ValueError):
        raise store.Missing('Teste não encontrado.') from None


def get(test_id):
    folder, request = location(test_id)
    response = json.loads((folder / 'response.json').read_text()) if (folder / 'response.json').exists() else None
    state = 'running' if (folder / 'started').exists() else 'queued'
    result = {'id': test_id, 'role': request['role'], 'provider': request['provider'], 'model': request['model'],
              'created_at': request['created_at'], 'state': state, 'reply': '',
              'reported_models': [], 'verification': 'unknown', 'error': '', 'elapsed': None}
    if response:
        result['elapsed'] = response.get('elapsed')
        if response.get('error'):
            result.update(state='failed', error=response['error'])
        else:
            result.update(state='succeeded', reply=response['result']['reply'],
                          reported_models=response.get('reported_models', []))
            reported = result['reported_models']
            if reported:
                result['verification'] = ('resolved' if not request['model'] else
                                          'match' if reported == [request['model']] else 'mismatch')
        if (folder / 'cancel').exists():
            result.update(state='cancelled', error='Teste cancelado.', reply='',
                          reported_models=[], verification='unknown')
    elif time.time() >= request['expires']:
        result.update(state='expired', error='O teste excedeu 3 minutos. Confira a fila, o login e o limite de uso do CLI.')
    elif (folder / 'cancel').exists():
        result['state'] = 'cancelling'
    return result


def latest():
    results = {}
    for file in (bridge.BRIDGE / 'requests').glob('*/request.json'):
        request = json.loads(file.read_text())
        if request.get('kind') == 'probe':
            previous = results.get(request['role'])
            if previous is None or request['created_at'] > previous['created_at']:
                results[request['role']] = get(file.parent.name)
    return results


def start(choice):
    bridge.require([choice['provider']])
    if bridge.status().get('protocol', 0) < 2:
        raise ValueError('Atualize o executor: encerre e rode novamente bash scripts/agents.sh no WSL.')
    agent_models.validate(choice)
    bridge.BRIDGE.mkdir(parents=True, exist_ok=True)
    with (bridge.BRIDGE / 'probe.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for file in (bridge.BRIDGE / 'requests').glob('*/request.json'):
            if json.loads(file.read_text()).get('kind') == 'probe':
                if get(file.parent.name)['state'] in ('queued', 'running', 'cancelling'):
                    raise store.Conflict('Já existe um teste em andamento. Aguarde ou cancele antes de testar outro agente.')
        challenge = secrets.token_hex(12)
        number = secrets.randbelow(1000)
        schema = {'type': 'object', 'properties': {'challenge': {'type': 'string'},
                  'answer': {'type': 'integer'}, 'reply': {'type': 'string'}},
                  'required': ['challenge', 'answer', 'reply'], 'additionalProperties': False}
        prompt = (f'Teste de conexão MyCut. Retorne somente o JSON solicitado. Copie challenge="{challenge}". '
                  f'Calcule {number}+17 e coloque o inteiro em answer. Em reply, escreva uma frase curta '
                  'em português confirmando que recebeu esta solicitação. Não use ferramentas.')
        test_id = uuid.uuid4().hex
        bridge.atomic_json(bridge.BRIDGE / 'requests' / test_id / 'request.json',
                           {**choice, 'kind': 'probe', 'created_at': time.time(),
                            'expires': time.time()+180, 'prompt': prompt, 'schema': schema, 'web': False,
                            'challenge': challenge, 'answer': number+17})
        return get(test_id)


def cancel(test_id):
    folder, _ = location(test_id)
    if get(test_id)['state'] in ('queued', 'running', 'cancelling'):
        (folder / 'cancel').touch()
        if not (folder / 'started').exists():
            bridge.atomic_json(folder / 'response.json', {'error': 'Teste cancelado.'})
    return get(test_id)


def validate_response(request, result):
    if (result.get('challenge') != request['challenge'] or type(result.get('answer')) is not int
            or result['answer'] != request['answer'] or not isinstance(result.get('reply'), str)
            or not 1 <= len(result['reply'].strip()) <= 1000):
        raise ValueError('O CLI respondeu, mas não cumpriu o teste. Confira o modelo e tente novamente.')
