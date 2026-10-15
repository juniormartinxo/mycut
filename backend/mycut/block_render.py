"""Authoritative layout, text overflow and video compositing for scene blocks."""
import io
from PIL import Image, ImageDraw, ImageOps
from . import visuals, google_fonts, flow
from .scene_layout import geometry, validate_assets
from .scene_media import VideoFrames
from .media import data_path, digest


def text_layout(obj, box, style, size=None):
    pixels = size or obj['font_size']
    face = google_fonts.face(obj.get('font') or style.get('google_font') or 'Roboto', round(pixels))
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    width, height = max(1, box[2]-16), max(1, box[3]-16)
    lines = []
    for paragraph in obj.get('text', '').split('\n'):
        line = ''
        for word in paragraph.split():
            # Preserve long tokens by wrapping characters, never clipping silently.
            pieces = ['']
            for char in word:
                if pieces[-1] and draw.textlength(pieces[-1]+char, font=face) > width:
                    pieces.append('')
                pieces[-1] += char
            for piece in pieces:
                candidate = (line+' '+piece).strip()
                if line and draw.textlength(candidate, font=face) > width:
                    lines.append(line)
                    line = piece
                else:
                    line = candidate
        lines.append(line)
    ascent, descent = face.getmetrics()
    leading = max(pixels * 1.3, ascent + descent)
    overflow = len(lines)*leading > height or any(draw.textlength(line, font=face) > width for line in lines)
    return face, lines, leading, overflow


def inspect(scene, project):
    validate_assets(scene, project)
    style = visuals.resolve(project)
    issues, warnings, boxes = [], [], geometry(scene['blocks'])
    for block, info in zip(scene['blocks'], boxes):
        obj = block.get('object')
        if not obj:
            continue
        if obj['type'] in ('image', 'video') and not obj.get('asset_id'):
            issues.append({'object_id': obj['id'], 'kind': 'missing_media', 'message': 'Selecione um arquivo ou remova o objeto.'})
        if obj['type'] == 'flow':
            blocking, notes = flow.problems(obj, info['object'], style, scene.get('narration', ''))
            issues += blocking
            warnings += notes
        if obj['type'] in ('title', 'paragraph'):
            if text_layout(obj, info['object'], style)[3]:
                fitted = None
                for size in range(int(obj['font_size'])-1, 7, -1):
                    if not text_layout(obj, info['object'], style, size)[3]:
                        fitted = size
                        break
                issues.append({'object_id': obj['id'], 'kind': 'overflow', 'font_size': fitted,
                               'message': 'O texto não cabe. Aumente a área, reduza o texto ou ajuste a fonte.'})
    return {'issues': issues, 'warnings': warnings, 'geometry': boxes}


def validate_project(project):
    for index, scene in enumerate(project['scenes']):
        if scene.get('blocks') is not None:
            issues = inspect(scene, project)['issues']
            if issues:
                raise ValueError(f'Cena {index+1}: {issues[0]["message"]}')


class BlockComposition:
    def __init__(self, scene, project, width=1080, fps=30, clock=None):
        self.scene, self.project, self.fps = scene, project, fps
        self.scale = width / 1080
        self.size = (width, round(1920*self.scale))
        self.style = visuals.resolve(project)
        self.base = Image.new('RGB', (1080, 1920), self.style['background'])
        draw = ImageDraw.Draw(self.base)
        visuals.text_box(draw, self.style['channel_name'], (80, 95, 920, 70), self.style, 28)
        draw.line((70, 190, 1010, 190), fill=self.style['accent'], width=3)
        self.videos, self.readers, self.flows = [], {}, []
        validate_assets(scene, project)
        for block, info in zip(scene['blocks'], geometry(scene['blocks'])):
            obj = block.get('object')
            if not obj:
                continue
            x, y, w, h = info['object']
            size = (max(1, round(w)), max(1, round(h)))
            layer = Image.new('RGBA', size)
            if obj['type'] == 'flow':
                # Drawn per frame: its states change with the narration (ADR 0003).
                if obj.get('flow'):
                    narration = scene.get('narration', '')
                    self.flows.append((flow.FlowRenderer(obj, info['object'], self.style, narration,
                                                         clock or flow.estimate_clock(narration)), (round(x), round(y))))
                continue
            if obj['type'] in ('title', 'paragraph'):
                face, lines, leading, _ = text_layout(obj, info['object'], self.style)
                pen = ImageDraw.Draw(layer)
                text_height = max((n*leading+pen.textbbox((0, 0), line, font=face, anchor='lt')[3]
                                   for n, line in enumerate(lines)), default=0)
                dy = max(0, size[1]-16-text_height) * {'top': 0, 'center': .5, 'bottom': 1}[obj.get('text_vertical', 'top')]
                for n, line in enumerate(lines):
                    dx = (size[0]-16-pen.textlength(line, font=face)) * {'left': 0, 'center': .5, 'right': 1}[obj['align']]
                    pen.text((8+dx, 8+dy+n*leading), line, fill=obj.get('color') or self.style['text_color'], font=face, anchor='lt')
            elif obj.get('asset_id'):
                records = project.get('images' if obj['type'] == 'image' else 'videos', [])
                record = next(r for r in records if r['id'] == obj['asset_id'])
                path = data_path(record['path'] if obj['type'] == 'image' else record['poster_path'])
                if obj['type'] == 'image' and digest(path) != record['sha256']:
                    raise ValueError('A imagem mudou no disco. Importe-a novamente.')
                with Image.open(path) as source:
                    self.fit(layer, source.convert('RGBA'), obj['fit'], obj.get('zoom', 1), obj.get('crop_x', 50), obj.get('crop_y', 50))
                if obj['type'] == 'video':
                    self.videos.append((obj, record, (round(x), round(y), *size)))
            self.base.paste(layer, (round(x), round(y)), layer)

    @staticmethod
    def fit(layer, source, mode, zoom=1, crop_x=50, crop_y=50):
        if mode == 'cover':
            ratio = max(layer.width/source.width, layer.height/source.height) * zoom
            width, height = layer.width/ratio, layer.height/ratio
            x, y = (source.width-width)*crop_x/100, (source.height-height)*crop_y/100
            fitted = source.resize(layer.size, Image.Resampling.LANCZOS, box=(x, y, x+width, y+height))
        else:
            fitted = ImageOps.contain(source, layer.size, Image.Resampling.LANCZOS)
        layer.paste(fitted, ((layer.width-fitted.width)//2, (layer.height-fitted.height)//2))

    def frame(self, elapsed=None, phase=0, caption='', videos=True):
        image = self.base.copy()
        for obj, record, (x, y, w, h) in self.videos if elapsed is not None and videos else []:
            if obj['id'] not in self.readers:
                ratio = min(w/record['width'], h/record['height'])
                size = (w, h) if obj['fit'] == 'cover' else (max(1, round(record['width']*ratio)), max(1, round(record['height']*ratio)))
                self.readers[obj['id']] = VideoFrames(record, size, self.fps, obj['fit'], obj.get('zoom', 1), obj.get('crop_x', 50), obj.get('crop_y', 50))
            source = self.readers[obj['id']].frame(elapsed)
            layer = Image.new('RGB', (w, h), self.style['background'])
            self.fit(layer, source, obj['fit'])
            image.paste(layer, (x, y))
        for renderer, position in self.flows:
            layer = renderer.layer(elapsed)
            image.paste(layer, position, layer)
        if caption:
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((70, 1620, 1010, 1810), radius=16,
                                   fill=visuals.blend(self.style['background'], self.style['text_color'], .08))
            visuals.text_box(draw, caption, (105, 1655, 870, 140), self.style, 50, align='center')
        return image.resize(self.size, Image.Resampling.LANCZOS) if self.scale != 1 else image

    def close(self):
        for reader in self.readers.values():
            reader.close()
