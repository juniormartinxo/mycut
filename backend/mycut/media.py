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


COVER = (1080, 1920)
# A cover this close to 9:16 fills the frame, cropping at most this share of one side; others keep bars.
COVER_CROP = .12


def cover(source, target):
    """The cover fills the 1080×1920 frame, scaled up when the source is smaller (generators often
    deliver 576×1024 or 720×1280). Only an image far from 9:16 is letterboxed instead of cropped."""
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        ratio = image.width/image.height / (COVER[0]/COVER[1])
        if 1-COVER_CROP <= ratio <= 1/(1-COVER_CROP):
            canvas = ImageOps.fit(image, COVER, Image.Resampling.LANCZOS)
        else:
            canvas = Image.new('RGB', COVER, '#f7f3eb')
            image = ImageOps.contain(image, COVER, Image.Resampling.LANCZOS)
            canvas.paste(image, ((COVER[0]-image.width)//2, (COVER[1]-image.height)//2))
        canvas.save(target)


def data_path(relative):
    path = (DATA / relative).resolve()
    if not path.is_relative_to(DATA):
        raise ValueError('Caminho de arquivo inválido.')
    return path
