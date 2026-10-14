"""ElevenLabs adapter: account voices and speech with provider timestamps."""
import base64
import json
import math
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from .media import digest, probe
from .config import DATA
from . import store

BASE = 'https://api.elevenlabs.io'


def api(key, method, path, meta=None, **kwargs):
    """`meta` receives only the billed credits header, never the rest of the provider headers."""
    try:
        with httpx.Client(base_url=BASE, timeout=180, follow_redirects=False) as client:
            response = client.request(method, path, headers={'xi-api-key': key}, **kwargs)
    except httpx.HTTPError as exc:
        # Provider bodies and headers may contain sensitive data; do not relay them.
        raise ValueError('Não foi possível conectar à ElevenLabs. Confira sua rede e tente novamente.') from None
    if response.status_code in (401, 403):
        raise ValueError('A ElevenLabs recusou a chave ou suas permissões. Libere leitura de vozes/modelos e geração de fala.')
    if response.status_code in (402, 429):
        raise ValueError('A ElevenLabs informou limite de créditos ou de solicitações. Confira sua conta antes de tentar novamente.')
    if response.is_error:
        raise ValueError(f'A ElevenLabs recusou a operação (HTTP {response.status_code}). Confira voz, modelo e permissões.')
    if meta is not None:
        try:
            meta['credits'] = float(response.headers.get('character-cost', ''))
        except ValueError:
            pass
    try:
        return response.json()
    except ValueError:
        raise ValueError('A ElevenLabs retornou uma resposta inválida.') from None


def preview_url(value):
    """Only expose HTTPS audio links; the browser never receives our API key."""
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if url.scheme == 'https' and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return None


def voice_language(value):
    # Use the voice's registered language, not every language a model can speak.
    if not isinstance(value, str):
        return None
    code = value.strip().lower().replace('_', '-')
    if re.fullmatch(r'[a-z]{2,3}(?:-[a-z0-9]{2,8})*', code):
        return code.split('-')[0]
    return None


def voice_summary(voice):
    labels = voice.get('labels') or {}
    accent = labels.get('accent')
    return {'id': voice['voice_id'], 'name': voice['name'], 'category': voice.get('category', ''),
            'preview_url': preview_url(voice.get('preview_url')),
            'language': voice_language(labels.get('language')),
            'accent': accent.strip()[:100] if isinstance(accent, str) and accent.strip() else None}


def catalog(key):
    voices, cursor = [], None
    for _ in range(20):
        params = {'page_size': 100}
        if cursor:
            params['next_page_token'] = cursor
        page = api(key, 'GET', '/v2/voices', params=params)
        voices.extend(voice_summary(v) for v in page.get('voices', []))
        cursor = page.get('next_page_token')
        if not page.get('has_more') or not cursor:
            break
    models = api(key, 'GET', '/v1/models')
    return {'voices': voices, 'models': [{'id': m['model_id'], 'name': m['name']}
            for m in models if m.get('can_do_text_to_speech')]}


def transcript_from_characters(value, audio):
    if not isinstance(value, dict):
        raise ValueError('A ElevenLabs não retornou os tempos da fala. A produção parou para evitar legendas inventadas.')
    chars = value.get('characters', [])
    starts = value.get('character_start_times_seconds', [])
    ends = value.get('character_end_times_seconds', [])
    if not chars or not len(chars) == len(starts) == len(ends):
        raise ValueError('Os tempos da narração retornados pela ElevenLabs estão incompletos.')
    words, current, begin, end = [], '', 0.0, 0.0
    previous_start = previous_end = 0.0
    for char, start, stop in zip(chars, starts, ends):
        if not isinstance(char, str) or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in (start, stop)) or start < 0 or stop < start:
            raise ValueError('Os tempos da narração retornados pela ElevenLabs são inválidos.')
        if start < previous_start or stop < previous_end:
            raise ValueError('Os tempos da narração retornados pela ElevenLabs estão fora de ordem.')
        previous_start, previous_end = start, stop
        if char.isspace():
            if current:
                words.append({'word': current, 'start': begin, 'end': end})
                current = ''
        else:
            if not current:
                begin = start
            current += char
            end = stop
    if current:
        words.append({'word': current, 'start': begin, 'end': end})
    if not words:
        raise ValueError('A ElevenLabs não retornou palavras para sincronizar.')
    return {'audio_sha256': digest(audio), 'provider': 'elevenlabs', 'segments': [
        {'start': words[0]['start'], 'end': words[-1]['end'],
         'text': ' '.join(w['word'] for w in words), 'words': words}]}


def synthesize(project, settings, folder, spent=None):
    text = store.script(project)
    if not text.strip() or len(text) > 4000:
        raise ValueError('A narração deve ter de 1 a 4.000 caracteres para gerar voz.')
    body = {'text': text, 'model_id': settings['model_id'], 'voice_settings': {
        k: settings[k] for k in ('stability', 'similarity_boost', 'speed')}}
    # One request for the complete script preserves natural phrase transitions.
    meta = {}
    result = api(settings['api_key'], 'POST', f'/v1/text-to-speech/{settings["voice_id"]}/with-timestamps',
                 meta=meta, params={'output_format': 'mp3_44100_128'}, json=body)
    if spent:
        # Without the header, one credit per character is the usual rate for the multilingual models.
        spent(meta.get('credits', float(len(text))), 'credits' not in meta)
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / 'elevenlabs.mp3'
    try:
        raw.write_bytes(base64.b64decode(result['audio_base64'], validate=True))
    except (ValueError, KeyError):
        raise ValueError('A ElevenLabs não retornou um áudio válido.') from None
    probe(raw)
    wav = folder / 'narracao.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(raw), '-vn',
                    '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'pcm_s24le', str(wav)],
                   check=True, timeout=180)
    transcript = transcript_from_characters(result.get('normalized_alignment') or result.get('alignment'), wav)
    if transcript['segments'][-1]['end'] > probe(wav) + .25:
        raise ValueError('Os tempos da narração excedem a duração do áudio retornado.')
    aligned = folder / 'alignment.json'
    aligned.write_text(json.dumps(transcript, ensure_ascii=False))
    return {'path': str(wav.relative_to(DATA)), 'name': f'ElevenLabs · {settings["voice_name"] or settings["voice_id"]}',
            'sha256': digest(wav), 'duration': probe(wav), 'normalized': True,
            'script_hash': store.script_hash(project), 'alignment': str(aligned.relative_to(DATA)),
            'provider': 'elevenlabs', 'voice_id': settings['voice_id'], 'model_id': settings['model_id']}
