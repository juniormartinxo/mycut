"""File queue between the Docker worker and authenticated CLIs on the host."""
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from .config import DATA

BRIDGE = DATA / 'agent-bridge'
PROVIDERS = ('codex', 'claude', 'grok')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
        json.dump(value, file, ensure_ascii=False)
        temp = file.name
    os.replace(temp, path)


def status():
    try:
        value = json.loads((BRIDGE / 'heartbeat.json').read_text())
        return {'online': time.time()-value['time'] < 15,
                'protocol': value.get('protocol', 1),
                'providers': {p: bool(value.get('providers', {}).get(p)) for p in PROVIDERS}}
    except (OSError, ValueError, KeyError):
        return {'online': False, 'protocol': 0, 'providers': {p: False for p in PROVIDERS}}


def require(providers):
    current = status()
    if not current['online']:
        raise ValueError('O executor de agentes está desconectado. Rode bash scripts/agents.sh no WSL.')
    missing = sorted(set(providers) - {p for p, available in current['providers'].items() if available})
    if missing:
        raise ValueError('CLI não encontrado no executor: ' + ', '.join(missing) + '. Confira Conexões.')


def invoke(config, prompt, schema, web=False, timeout=900):
    require([config['provider']])
    folder = BRIDGE / 'requests' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    lease = folder / 'lease'
    lease.touch()
    atomic_json(folder / 'request.json', {'provider': config['provider'], 'model': config['model'],
                 'prompt': prompt, 'schema': schema, 'web': web, 'expires': time.time()+timeout})
    try:
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            lease.touch()
            if (folder / 'response.json').is_file():
                result = json.loads((folder / 'response.json').read_text())
                if result.get('error'):
                    raise ValueError(result['error'])
                return result['result']
            if not status()['online']:
                raise ValueError('O executor de agentes desconectou durante a produção. Reinicie bash scripts/agents.sh e tente novamente.')
            time.sleep(.5)
        raise ValueError('O agente excedeu 15 minutos. Confira o login e o limite de uso do CLI e tente novamente.')
    finally:
        (folder / 'cancel').touch()
