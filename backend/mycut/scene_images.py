"""Project-owned images; decode to bounded PNGs and keep source provenance."""
import io
import uuid
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin
from PIL import Image, ImageOps, UnidentifiedImageError
from .config import DATA
from .media import digest


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


def import_image(content, project_id, name, source_url='', page_url=''):
    if len(content) > 15 * 1024 * 1024:
        raise ValueError('Use uma imagem de até 15 MB.')
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Use uma imagem PNG, JPG ou WebP.')
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            width, height = image.size
            image_id = uuid.uuid4().hex
            target = DATA / 'projects' / project_id / 'images' / f'{image_id}.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format='PNG')
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError('Não foi possível ler a imagem. Use PNG, JPG ou WebP válido.') from exc
    return {'id': image_id, 'name': name[:200], 'path': str(target.relative_to(DATA)),
            'sha256': digest(target), 'width': width, 'height': height,
            'source_url': source_url, 'page_url': page_url}
