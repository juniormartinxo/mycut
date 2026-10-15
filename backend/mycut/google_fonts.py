"""Google Fonts catalog snapshot and immutable, shared browser/render cache."""
import hashlib
import io
import json
import re
import tempfile
import threading
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from PIL import ImageFont
from .config import DATA

CATALOG_PATH = Path(__file__).with_name('google_fonts_catalog.json')
LOCK = threading.Lock()


@lru_cache(maxsize=1)
def catalog():
    return json.loads(CATALOG_PATH.read_text())


def entry(family):
    value = next((f for f in catalog()['families'] if f['family'] == family), None)
    if value is None:
        raise ValueError('Escolha uma família do catálogo Google Fonts.')
    return value


def cache_path(family):
    entry(family)
    return DATA / 'google-fonts' / hashlib.sha256(family.encode()).hexdigest()


def install(family):
    spec = entry(family)
    destination = cache_path(family)
    bundled = Path(__file__).with_name('fonts') / family / 'font.ttf'
    if family == 'Roboto' and bundled.is_file():
        return bundled
    with LOCK:
        if (destination / 'font.ttf').is_file():
            metadata = json.loads((destination / 'source.json').read_text())
            if hashlib.sha256((destination / 'font.ttf').read_bytes()).hexdigest() != metadata['sha256']:
                raise ValueError('A fonte foi alterada no disco. Restaure seu arquivo de cache.')
            return destination / 'font.ttf'
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.Client(timeout=30, follow_redirects=False, headers={'User-Agent': 'MyCut/1.0'}) as client:
                css = client.get('https://fonts.googleapis.com/css2', params={'family': f'{family}:wght@{spec["weight"]}'})
                css.raise_for_status()
                urls = re.findall(r'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)', css.text)
                if not urls:
                    raise ValueError('Google Fonts não retornou um arquivo TTF compatível para esta família.')
                url = urls[-1]
                if urlsplit(url).hostname != 'fonts.gstatic.com':
                    raise ValueError('Origem de fonte inválida.')
                chunks, size = [], 0
                with client.stream('GET', url) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 32*1024*1024:
                            raise ValueError('A fonte ultrapassa o limite de 32 MB.')
                        chunks.append(chunk)
                content = b''.join(chunks)
                ImageFont.truetype(io.BytesIO(content), 24)
        except (httpx.HTTPError, OSError) as exc:
            raise ValueError(f'Não foi possível baixar {family}. Confira a conexão e tente novamente.') from exc
        with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.font-') as staging:
            folder = Path(staging)
            (folder / 'font.ttf').write_bytes(content)
            (folder / 'source.json').write_text(json.dumps({'family': family, 'url': url,
                'weight': spec['weight'], 'sha256': hashlib.sha256(content).hexdigest()}, ensure_ascii=False))
            try:
                folder.rename(destination)
            except OSError:
                # Another worker can finish the same immutable download first.
                if not (destination / 'font.ttf').is_file():
                    raise
                metadata = json.loads((destination / 'source.json').read_text())
                if hashlib.sha256((destination / 'font.ttf').read_bytes()).hexdigest() != metadata['sha256']:
                    raise ValueError('A fonte em cache não passou na verificação de integridade.') from None
        return destination / 'font.ttf'


@lru_cache(maxsize=512)
def face(family, size):
    return ImageFont.truetype(str(install(family)), max(8, size))
