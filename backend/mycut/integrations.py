"""Local integration settings. Secrets never enter project snapshots or API responses."""
import copy
import fcntl
import json
import os
import tempfile
from .config import DATA, configure

ROLES = ('research', 'writer', 'director', 'reviewer')
DEFAULTS = {
    'agents': {role: {'provider': provider, 'model': ''} for role, provider in zip(
        ROLES, ('grok', 'claude', 'codex', 'codex'))},
    'elevenlabs': {'api_key': '', 'voice_id': '', 'voice_name': '',
                  'model_id': 'eleven_multilingual_v2', 'stability': .5,
                  'similarity_boost': .75, 'speed': 1.0},
}


def read():
    path = DATA / 'private/integrations.json'
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(DEFAULTS)


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
    from .bridge import status
    from .agent_models import catalog
    settings = read()
    eleven = settings['elevenlabs']
    return {'agents': settings['agents'], 'runner': status(), 'agent_models': catalog(),
            'elevenlabs': {**{k: v for k, v in eleven.items() if k != 'api_key'},
                          'connected': bool(eleven['api_key'])}}


def require_voice():
    settings = read()['elevenlabs']
    if not settings['api_key'] or not settings['voice_id']:
        raise ValueError('Conecte a ElevenLabs e selecione sua voz em Conexões.')
    return settings
