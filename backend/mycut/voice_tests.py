"""Short, explicitly requested voice tests, cached locally for free replay."""
import base64
import fcntl
import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from . import elevenlabs, integrations, store
from .config import DATA
from .models import ElevenSettings


class VoiceTestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=300)
    settings: ElevenSettings

    @field_validator('text')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Escreva uma frase para testar a voz.')
        return value.strip()


def account_folder():
    key = integrations.read()['elevenlabs']['api_key']
    if not key:
        raise ValueError('Conecte sua chave da ElevenLabs primeiro.')
    # Namespace by credential without storing or returning it in test records.
    account = hmac.new(key.encode(), b'mycut-voice-tests-v1', hashlib.sha256).hexdigest()
    folder = DATA / 'voice-tests' / account
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return key, folder


def public(record, cached=True):
    return {**record, 'cached': cached,
            'url': f'/api/integrations/elevenlabs/tests/{record["id"]}/audio'}


def latest():
    _, folder = account_folder()
    records = [json.loads(path.read_text()) for path in folder.glob('*.json')]
    return [public(r) for r in sorted(records, key=lambda r: r['created_at'], reverse=True)[:5]]


def audio(test_id):
    if not re.fullmatch(r'[a-f0-9]{64}', test_id):
        raise store.Missing('Teste de voz não encontrado.')
    _, folder = account_folder()
    path = folder / f'{test_id}.mp3'
    if not path.is_file() or not (folder / f'{test_id}.json').is_file():
        raise store.Missing('Teste de voz não encontrado.')
    return path


def duration_of(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                             '-show_entries', 'stream=codec_name:format=duration', '-of', 'json', str(path)],
                            capture_output=True, timeout=20)
    try:
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        if result.returncode == 0 and 0 < duration <= 180 and any(
                s.get('codec_name') == 'mp3' for s in info.get('streams', [])):
            return duration
    except (ValueError, KeyError, TypeError):
        pass
    raise ValueError('A ElevenLabs não retornou um MP3 válido para o teste.')


def generate(body: VoiceTestRequest):
    key, folder = account_folder()
    settings = body.settings.model_dump(exclude={'voice_name'})
    payload = {'text': body.text, 'settings': settings}
    test_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    record_path = folder / f'{test_id}.json'
    audio_path = folder / f'{test_id}.mp3'
    with (folder / 'generation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise store.Conflict('Um teste de voz já está em andamento. Aguarde o resultado.') from None
        if record_path.is_file() and audio_path.is_file():
            return public(json.loads(record_path.read_text()))
        catalog = elevenlabs.catalog(key)
        voice = next((v for v in catalog['voices'] if v['id'] == settings['voice_id']), None)
        model = next((m for m in catalog['models'] if m['id'] == settings['model_id']), None)
        if not voice or not model:
            raise ValueError('Selecione uma voz e um modelo disponíveis na sua conta.')
        # No retry: each POST may consume credits even when the connection fails.
        result = elevenlabs.api(key, 'POST', f'/v1/text-to-speech/{settings["voice_id"]}/with-timestamps',
                               params={'output_format': 'mp3_44100_128'}, json={
                                   'text': body.text, 'model_id': settings['model_id'],
                                   'voice_settings': {k: settings[k] for k in ('stability', 'similarity_boost', 'speed')},
                               })
        try:
            content = base64.b64decode(result['audio_base64'], validate=True)
        except (ValueError, KeyError, TypeError):
            raise ValueError('A ElevenLabs não retornou um áudio válido para o teste.') from None
        # Publish only complete, playable audio and an atomic metadata record.
        with tempfile.TemporaryDirectory(dir=folder) as staging:
            temp_audio = Path(staging) / 'sample.mp3'
            temp_audio.write_bytes(content)
            duration = duration_of(temp_audio)
            record = {'id': test_id, **payload, 'voice_name': voice['name'], 'model_name': model['name'],
                      'created_at': time.time(), 'duration': duration}
            temp_record = Path(staging) / 'record.json'
            temp_record.write_text(json.dumps(record, ensure_ascii=False))
            os.replace(temp_audio, audio_path)
            os.replace(temp_record, record_path)
        return public(record, cached=False)
