"""Local integration settings. Secrets never enter project snapshots or API responses."""
import copy
import fcntl
import json
import os
import tempfile
from .config import DATA, configure
from .commands import DEFAULTS as COMMANDS
from .costs import DEFAULTS as PRICING

ROLES = ('research', 'writer', 'director', 'reviewer', 'art')
# Roles of every production; the Arte only works for a Short livre that generates images.
TEXT_ROLES = ('research', 'writer', 'director', 'reviewer')
DEFAULTS = {
    'agents': {role: {'provider': provider, 'model': ''} for role, provider in zip(
        ROLES, ('grok', 'claude', 'codex', 'codex', 'codex'))},
    'elevenlabs': {'api_key': '', 'voice_id': '', 'voice_name': '',
                  'model_id': 'eleven_multilingual_v2', 'stability': .5,
                  'similarity_boost': .75, 'speed': 1.0},
    'commands': COMMANDS,
    'browser': {'enabled': True, 'chrome_path': '', 'port': 9222},
    'pricing': PRICING,
}


def read():
    path = DATA / 'private/integrations.json'
    settings = copy.deepcopy(DEFAULTS)
    # Sections added after the file was written keep their defaults.
    for name, values in (json.loads(path.read_text()) if path.exists() else {}).items():
        settings.setdefault(name, {}).update(values)
    return settings


def save_section(name, values):
    configure()
    folder = DATA / 'private'
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    with (folder / 'integrations.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = read()
        settings[name].update(values)
        with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as file:
            json.dump(settings, file, ensure_ascii=False)
            temp = file.name
        os.chmod(temp, 0o600)
        os.replace(temp, folder / 'integrations.json')
    return public()


def public():
    from .bridge import BRIDGE, status
    from .agent_models import catalog
    settings = read()
    eleven = settings['elevenlabs']
    try:
        browser_test = json.loads((BRIDGE / 'browser-test.json').read_text())
    except (OSError, ValueError):
        browser_test = None
    return {'agents': settings['agents'], 'commands': settings['commands'], 'runner': status(),
            'browser': settings['browser'], 'browser_test': browser_test, 'pricing': settings['pricing'], 'agent_models': catalog(),
            'elevenlabs': {**{k: v for k, v in eleven.items() if k != 'api_key'},
                          'connected': bool(eleven['api_key'])}}


def require_voice():
    settings = read()['elevenlabs']
    if not settings['api_key'] or not settings['voice_id']:
        raise ValueError('Conecte a ElevenLabs e selecione sua voz em Conexões.')
    return settings
