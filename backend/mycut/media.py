"""Bounded, local-only media handling. Uploaded names never become paths."""
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageOps
from .config import DATA

Image.MAX_IMAGE_PIXELS = 20_000_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                             '-show_entries', 'stream=codec_type,codec_name,width,height,duration:format=duration',
                             '-of', 'json', str(path)], capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError('Não foi possível ler este áudio. Use um MP3, WAV, M4A ou FLAC válido.')
    info = json.loads(result.stdout)
    if not any(s['codec_type'] == 'audio' for s in info.get('streams', [])):
        raise ValueError('O arquivo não contém uma faixa de áudio.')
    duration = float(info.get('format', {}).get('duration', 0))
    if not 1 <= duration <= 180:
        raise ValueError('A narração deve ter entre 1 e 180 segundos.')
    return duration


def cover(source, target):
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((1080, 1920), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1080, 1920), '#f7f3eb')
        canvas.paste(image, ((1080-image.width)//2, (1920-image.height)//2))
        canvas.save(target)


def data_path(relative):
    path = (DATA / relative).resolve()
    if not path.is_relative_to(DATA):
        raise ValueError('Caminho de arquivo inválido.')
    return path
