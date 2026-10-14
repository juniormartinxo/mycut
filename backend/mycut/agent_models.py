"""Host model discovery. Export only model IDs and labels, never cache credentials."""
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from .bridge import BRIDGE, PROVIDERS, atomic_json

MODEL_ID = re.compile(r'^[a-zA-Z0-9._:/-]{1,150}$')
_refreshed = 0


def item(model_id, label):
    if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
        return None
    return {'id': model_id, 'name': str(label or model_id)[:150]}


def cached_models(provider, path):
    data = json.loads(path.read_text())
    entries = []
    if provider == 'codex':
        for model in data.get('models', []):
            if model.get('visibility') == 'list':
                entries.append(item(model.get('slug'), model.get('display_name')))
    elif provider == 'grok':
        for model_id, model in data.get('models', {}).items():
            info = model.get('info', {})
            if not info.get('hidden', False):
                entries.append(item(model_id, info.get('name')))
    return [entry for entry in entries if entry]


def claude_models():
    """Initialize the CLI's control protocol without sending a user/inference prompt."""
    executable = shutil.which('claude')
    if not executable:
        return []
    args = [executable, '-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
            '--verbose', '--restricted', '--no-session-persistence', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--tools', '']
    with tempfile.TemporaryDirectory(prefix='mycut-catalog-') as directory:
        with subprocess.Popen(args, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, start_new_session=True) as process:
            try:
                message = {'type': 'control_request', 'request_id': 'mycut-catalog',
                           'request': {'subtype': 'initialize', 'hooks': {}}}
                process.stdin.write((json.dumps(message)+'\n').encode())
                process.stdin.flush()
                buffer = b''
                deadline = time.monotonic()+8
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while time.monotonic() < deadline:
                        if not selector.select(.1):
                            continue
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        buffer += chunk
                        if len(buffer) > 1_000_000:
                            break
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            value = json.loads(line)
                            if value.get('type') != 'control_response':
                                continue
                            response = value.get('response', {}).get('response', {})
                            entries = {}
                            for model in response.get('models', []):
                                # Pin the resolved model instead of a moving alias or a display name.
                                if model.get('value') == 'default':
                                    continue
                                entry = item(model.get('resolvedModel'), model.get('displayName'))
                                if entry:
                                    entries[entry['id']] = entry
                            return list(entries.values())
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
    return []


def catalog():
    try:
        data = json.loads((BRIDGE / 'models.json').read_text())
        return {p: data.get(p, {'models': [], 'checked_at': None, 'source': '', 'error': ''}) for p in PROVIDERS}
    except (OSError, ValueError):
        return {p: {'models': [], 'checked_at': None, 'source': '', 'error': ''} for p in PROVIDERS}


def refresh():
    """Called while idle; discovery never interrupts an inference or its heartbeat."""
    global _refreshed
    marker = BRIDGE / 'refresh-models'
    if time.monotonic()-_refreshed < 60 and not marker.exists():
        return
    marker.unlink(missing_ok=True)
    _refreshed = time.monotonic()
    data = catalog()
    paths = {'codex': Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'models_cache.json',
             'grok': Path.home()/'.grok/models_cache.json'}
    for provider in PROVIDERS:
        try:
            models = claude_models() if provider == 'claude' else cached_models(provider, paths[provider])
            if not models:
                raise ValueError('empty catalog')
            data[provider] = {'models': models, 'checked_at': time.time(),
                              'source': 'cli' if provider == 'claude' else 'cache', 'error': ''}
        except (OSError, ValueError, TypeError, AttributeError):
            data[provider]['error'] = 'Lista indisponível. Abra este CLI no WSL, confira o login e atualize a lista.'
    atomic_json(BRIDGE / 'models.json', data)


def validate(choice):
    if choice['model'] and choice['model'] not in {m['id'] for m in catalog()[choice['provider']]['models']}:
        raise ValueError('Modelo fora da lista deste CLI. Atualize os modelos e selecione novamente em Conexões.')


def reported_models(provider, stdout):
    """Only CLI envelope metadata counts. Never inspect model-authored JSON/text."""
    if provider not in ('claude', 'grok'):
        return []
    try:
        envelope = json.loads(stdout)
        usage = envelope.get('modelUsage', {})
        return sorted(model for model, stats in usage.items()
                      if MODEL_ID.fullmatch(model) and isinstance(stats, dict)
                      and (stats.get('inputTokens', 0) > 0 or stats.get('outputTokens', 0) > 0))
    except (ValueError, TypeError, AttributeError):
        return []
