"""Project-owned images; decode to bounded PNGs (animated GIFs and WebPs also keep their file) and keep source provenance."""
import bisect
import io
import itertools
import uuid
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin
from PIL import Image, ImageOps, UnidentifiedImageError
from .config import DATA
from .media import data_path, digest


def public_target(url):
    if len(url) > 2000 or any(ord(char) < 33 for char in url):
        raise ValueError('Endereço de imagem inválido.')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('A imagem deve usar HTTPS público, sem credenciais.')
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('O endereço da imagem não é público.')
    return parsed, addresses[0][4][0]


def fetch_image(url):
    """Pin the validated IP and verify TLS for the hostname on every redirect."""
    for _ in range(4):
        parsed, address = public_target(url)
        connection = http.client.HTTPSConnection(parsed.hostname, timeout=12)
        raw = socket.create_connection((address, 443), timeout=12)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
            connection.request('GET', parsed.path or '/' if not parsed.query else (parsed.path or '/')+'?'+parsed.query,
                               headers={'User-Agent': 'MyCut/1.0', 'Accept': 'image/png,image/jpeg,image/webp'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader('Location') or '')
                continue
            if response.status != 200:
                raise ValueError(f'A fonte da imagem respondeu HTTP {response.status}.')
            content = response.read(15 * 1024 * 1024 + 1)
            if len(content) > 15 * 1024 * 1024:
                raise ValueError('A imagem da fonte excede 15 MB.')
            return content
        finally:
            connection.close()
            raw.close()
    raise ValueError('A imagem redirecionou vezes demais.')


def eligible(project):
    """Restrict automatic selection without deleting stored or manually chosen assets."""
    style = project.get('visual_style') or {}
    if style.get('media_mode') != 'mixed':
        return []
    origin = style.get('image_source', 'sources')
    return [image for image in project.get('images', [])
            if origin == 'both' or bool(image.get('source_url')) == (origin == 'sources')]


def collect(research, project):
    style = project.get('visual_style') or {}
    images, notes = list(project.get('images', [])), []
    if style.get('media_mode') != 'mixed' or style.get('image_source') == 'library':
        return images, notes
    sources = {item['url'] for item in research['sources']}
    known = {item.get('source_url') for item in images}
    for candidate in research.get('images', [])[:3]:
        if len(images) >= 24:
            break
        if candidate['source_url'] not in sources:
            notes.append('Uma imagem foi ignorada porque sua página não consta das fontes verificadas.')
            continue
        if candidate['url'] in known:
            continue
        try:
            record = import_image(fetch_image(candidate['url']), project['id'], candidate['title'],
                                  candidate['url'], candidate['source_url'])
            images.append(record)
            known.add(candidate['url'])
        except (ValueError, OSError, http.client.HTTPException):
            notes.append(f'Imagem indisponível: {candidate["title"][:100]}. A cena pode usar animação.')
    if not eligible({**project, 'images': images}):
        notes.append('Nenhuma imagem disponível nas fontes. Os agentes usarão animações; você pode importar imagens nas cenas.')
    return images, notes


# Bounds for an animated GIF or WebP: it is decoded frame by frame at render time, never held whole.
ANIMATION_FRAMES, ANIMATION_SIDE = 1000, 1920
# Browsers play frame delays under 20 ms at 100 ms; the video follows what the person saw.
MIN_DELAY, DEFAULT_DELAY = 20, 100


def frame_delays(image):
    """Seconds each frame of an animated GIF or WebP stays on screen."""
    delays = []
    for index in range(image.n_frames):
        image.seek(index)
        if image.format == 'WEBP':
            # WebP reports a frame's duration only once the frame is decoded.
            image.load()
        delay = image.info.get('duration') or 0
        delays.append((delay if delay >= MIN_DELAY else DEFAULT_DELAY)/1000)
    image.seek(0)
    return delays


def import_image(content, project_id, name, source_url='', page_url=''):
    """A still image becomes a bounded PNG, transparent where the source is. An animated GIF or WebP
    keeps its file to play; its first frame is the PNG every still consumer (library, agents, covers) reads."""
    if len(content) > 15 * 1024 * 1024:
        raise ValueError('Use uma imagem de até 15 MB.')
    image_id = uuid.uuid4().hex
    folder = DATA / 'projects' / project_id / 'images'
    target = folder / f'{image_id}.png'
    animation = None
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
                raise ValueError('Use uma imagem PNG, JPG, WebP ou GIF.')
            if image.format in ('GIF', 'WEBP') and getattr(image, 'n_frames', 1) > 1:
                if image.n_frames > ANIMATION_FRAMES or max(image.size) > ANIMATION_SIDE:
                    raise ValueError(f'Use uma animação de até {ANIMATION_FRAMES} quadros e {ANIMATION_SIDE} px no maior lado.')
                delays = frame_delays(image)
                suffix = '.gif' if image.format == 'GIF' else '.webp'
                image = image.convert('RGBA')
                animation = {'path': folder / f'{image_id}{suffix}', 'frames': len(delays), 'duration': round(sum(delays), 3)}
            else:
                # A logo or sticker keeps its transparent areas instead of turning them black.
                image = ImageOps.exif_transpose(image).convert('RGBA' if image.has_transparency_data else 'RGB')
                image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            width, height = image.size
            folder.mkdir(parents=True, exist_ok=True)
            image.save(target, format='PNG')
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, EOFError) as exc:
        raise ValueError('Não foi possível ler a imagem. Use PNG, JPG, WebP ou GIF válido.') from exc
    record = {'id': image_id, 'name': name[:200], 'path': str(target.relative_to(DATA)),
              'sha256': digest(target), 'width': width, 'height': height,
              'source_url': source_url, 'page_url': page_url}
    if animation:
        animation['path'].write_bytes(content)
        record['animation'] = {**animation, 'path': str(animation['path'].relative_to(DATA)),
                               'sha256': digest(animation['path'])}
    return record


def files(record):
    """Every file an image record owns on disk."""
    return [data_path(record['path'])] + ([data_path(record['animation']['path'])] if record.get('animation') else [])


def public(record):
    """The record as the browser and the agents see it: no disk paths."""
    return {k: v for k, v in record.items() if k not in ('path', 'animation')} | {'animated': bool(record.get('animation'))}


class AnimatedImage:
    """An imported animated GIF or WebP on its own frame timing, decoded sequentially like a video."""
    def __init__(self, record):
        animation = record['animation']
        source = data_path(animation['path'])
        if digest(source) != animation['sha256']:
            raise ValueError('A imagem mudou no disco. Importe-a novamente.')
        self.image = Image.open(source)
        self.starts = list(itertools.accumulate(frame_delays(self.image), initial=0.0))
        self.duration = self.starts.pop()
        self.index, self.current = -1, None

    def frame(self, elapsed, loop=False):
        """(frame index, RGBA frame) shown at this time; no time is the first frame.
        Played once, the last frame stays after the animation ends."""
        moment = 0.0 if elapsed is None else elapsed % self.duration if loop else elapsed
        index = max(0, bisect.bisect_right(self.starts, moment)-1)
        if index != self.index:
            self.image.seek(index)
            self.index, self.current = index, self.image.convert('RGBA')
        return self.index, self.current

    def close(self):
        self.image.close()
