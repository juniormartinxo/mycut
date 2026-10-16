"""One composition engine for preset thumbnails, editor previews, covers and video."""
import io
import json
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin
from .media import data_path, digest

FORMATS = json.loads(Path(__file__).with_name('short_formats.json').read_text())
FONT_FILES = {
    'sans': 'DejaVuSans-Bold.ttf', 'serif': 'DejaVuSerif-Bold.ttf',
    'mono': 'DejaVuSansMono-Bold.ttf', 'condensed': 'DejaVuSansCondensed-Bold.ttf',
}
FONT_NAMES = {'sans': 'Sans', 'serif': 'Serifada', 'mono': 'Monoespaçada', 'condensed': 'Condensada'}


# Base of a Short livre (ADR 0005): never offered as a format; the director replaces its colors and font.
FREE = {'id': 'free', 'name': 'Livre', 'font': 'sans', 'background': '#101418', 'text_color': '#F2F4F5', 'accent': '#F2B544',
        'direction': ''}


def preset(format_id='editorial'):
    return FREE if format_id == 'free' else next(item for item in FORMATS if item['id'] == format_id)


def resolve(project):
    custom = project.get('visual_style') or {}
    base = preset(custom.get('format_id', 'editorial'))
    # A project without visual_style keeps the original sans-serif composition.
    return {**base, 'channel_name': 'MYCUT', **{key: value for key, value in custom.items() if value is not None},
            'font': custom.get('font') or (base['font'] if custom else 'sans'),
            'accent': project.get('accent') or base['accent']}


@lru_cache(maxsize=256)
def font(family, size):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/' + FONT_FILES[family], max(8, size))


def rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def blend(first, second, amount):
    return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(rgb(first), rgb(second)))


def text_box(draw, text, box, style, size=56, color=None, align='left', max_lines=4):
    x, y, width, height = box
    color = color or style['text_color']
    for pixels in range(max(8, round(size)), 7, -1):
        face = font(style['font'], pixels)
        lines, line = [], ''
        # Break long tokens too: URLs/model IDs must never escape the canvas.
        for word in str(text).split():
            pieces = ['']
            for char in word:
                if pieces[-1] and draw.textlength(pieces[-1] + char, font=face) > width:
                    pieces.append('')
                pieces[-1] += char
            for piece in pieces:
                candidate = (line + ' ' + piece).strip()
                if line and draw.textlength(candidate, font=face) > width:
                    lines.append(line)
                    line = piece
                else:
                    line = candidate
        if line:
            lines.append(line)
        leading = pixels * 1.3
        if len(lines) <= max_lines and len(lines) * leading <= height:
            break
    for index, line in enumerate(lines):
        dx = (width - draw.textlength(line, font=face)) / 2 if align == 'center' else 0
        draw.text((round(x + dx), round(y + index * leading)), line, fill=color, font=face, anchor='lt')


class Composition:
    """Cache text/image layers once; animate only compositing at the output size."""
    def __init__(self, scene, project, width=1080, image=None):
        self.style = resolve(project)
        self.scale = width / 1080
        self.size = (width, round(1920 * self.scale))
        self.base = Image.new('RGB', self.size, self.style['background'])
        self.layers = []
        self.boxes = []
        self.scene = scene
        self.project = project
        self._caption_text = None
        self._caption_layer = None
        s, kind = self.scale, self.style['id']
        draw = ImageDraw.Draw(self.base)
        fg, accent = self.style['text_color'], self.style['accent']
        if kind == 'radar':
            draw.rectangle(self.coords((80, 100, 180, 114)), fill=accent)
            self.text(draw, self.style['channel_name'], (214, 80, 700, 60), 26)
            self.text(draw, scene['title'].upper(), (80, 245, 920, 360), 92)
        elif kind == 'tutorial':
            self.text(draw, self.style['channel_name'], (90, 100, 800, 60), 28)
            draw.line(self.coords((90, 194, 990, 194)), fill=accent, width=max(1, round(5 * s)))
            self.text(draw, scene['title'], (90, 255, 900, 340), 83)
        elif kind == 'impact':
            draw.rectangle(self.coords((0, 0, 1080, 42)), fill=accent)
            self.text(draw, self.style['channel_name'], (80, 115, 900, 60), 28)
            self.text(draw, scene['title'].upper(), (80, 245, 920, 370), 111)
        else:
            self.text(draw, self.style['channel_name'], (88, 100, 800, 60), 28)
            draw.line(self.coords((88, 180, 992, 180)), fill=blend(self.style['background'], fg, .3), width=max(1, round(2 * s)))
            self.text(draw, scene['title'].upper(), (88, 275, 904, 330), 76)
        if image is not None:
            self.image_layer(image, scene.get('image_fit', 'contain'))
            return
        labels = [i.strip() for i in scene.get('items', []) if i.strip()] or ['Aguardando conteúdo visual']
        layout = scene.get('layout', 'flow')
        if layout == 'comparison':
            labels = labels[:2]
        if layout == 'statement':
            labels = [' '.join(labels)]
        total = len(labels)
        for index, label in enumerate(labels):
            if layout == 'statement':
                box = (90, 800, 990, 1320)
            elif kind == 'radar':
                x = 80 if index % 2 == 0 else 270
                y = 680 + index * (720 / max(1, total - 1))
                box = (x, y, x + 730, y + 155)
            elif kind == 'tutorial':
                y = 685 + index * (690 / max(1, total - 1))
                box = (225, y, 990, y + 160)
            elif kind == 'impact':
                y = 700 + index * (700 / max(1, total - 1))
                box = (80 if index % 2 == 0 else 135, y, 945 if index % 2 == 0 else 1000, y + 170)
            else:
                y = 700 + index * (680 / max(1, total - 1))
                box = (138, y, 942, y + 164)
            if total == 1 and layout != 'statement':
                box = (box[0], 980, box[2], 1150)
            if index and layout == 'flow':
                previous = self.boxes[-1]
                x1, y1 = (previous[0] + previous[2]) / 2, previous[3]
                x2, y2 = (box[0] + box[2]) / 2, box[1]
                if kind == 'tutorial':
                    draw.line(self.coords((140, previous[1] + 80, 140, box[1] + 80)), fill=accent, width=max(2, round(4 * s)))
                elif kind == 'radar':
                    draw.line([self.point(x1, y1), self.point(x1, (y1+y2)/2), self.point(x2, (y1+y2)/2), self.point(x2, y2)], fill=accent, width=max(2, round(3 * s)))
                else:
                    draw.line(self.coords((x1, y1 + 10, x2, y2 - 10)), fill=accent, width=max(2, round(4 * s)))
                    draw.line([self.point(x2-13, y2-25), self.point(x2, y2-10), self.point(x2+13, y2-25)], fill=accent, width=max(2, round(4*s)))
            self.card_layer(label, box, index, layout)

    def point(self, x, y):
        return (round(x * self.scale), round(y * self.scale))

    def coords(self, box):
        return tuple(round(v * self.scale) for v in box)

    def text(self, draw, text, box, size, color=None, align='left'):
        text_box(draw, text, self.coords(box), self.style, size * self.scale, color, align)

    def card_layer(self, label, box, index, layout):
        layer = Image.new('RGBA', self.size)
        draw = ImageDraw.Draw(layer)
        kind, s = self.style['id'], self.scale
        foreground, background, accent = (self.style[k] for k in ('text_color', 'background', 'accent'))
        fill = blend(background, foreground, .07)
        radius = 24
        if kind == 'radar':
            radius = 8
            draw.rounded_rectangle(self.coords(box), radius=round(radius*s), fill=fill, outline=accent, width=max(1, round(2*s)))
        elif kind == 'impact':
            radius = 0
            fill, foreground = foreground, background
            draw.rectangle(self.coords(box), fill=fill)
        else:
            draw.rounded_rectangle(self.coords(box), radius=round(radius*s), fill=fill)
        if kind == 'tutorial' and layout != 'statement':
            cy = (box[1] + box[3]) / 2
            draw.ellipse(self.coords((124, cy-16, 156, cy+16)), fill=accent)
        inset = 38
        self.text(draw, label, (box[0]+inset, box[1]+30, box[2]-box[0]-2*inset, box[3]-box[1]-52),
                  76 if layout == 'statement' else 44, foreground, 'center' if kind in ('editorial','impact') else 'left')
        self.layers.append(layer)
        self.boxes.append(box)

    def image_layer(self, source, fit):
        box = self.coords((80, 670, 1000, 1360))
        size = (box[2]-box[0], box[3]-box[1])
        source = ImageOps.exif_transpose(source).convert('RGB')
        fitted = ImageOps.fit(source, size) if fit == 'cover' else ImageOps.contain(source, size)
        layer = Image.new('RGBA', self.size)
        layer.paste(fitted, (box[0]+(size[0]-fitted.width)//2, box[1]+(size[1]-fitted.height)//2))
        draw = ImageDraw.Draw(layer)
        labels = ' · '.join(self.scene.get('items', []))
        self.text(draw, labels, (90, 1410, 900, 160), 39, align='center')
        self.layers.append(layer)
        self.boxes.append((80, 670, 1000, 1360))

    def caption(self, value):
        if value == self._caption_text:
            return self._caption_layer
        layer = Image.new('RGBA', self.size)
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle(self.coords((70, 1620, 1010, 1810)), radius=round(16*self.scale),
                               fill=blend(self.style['background'], self.style['text_color'], .08))
        self.text(draw, value, (105, 1655, 870, 140), 50, self.style['text_color'], 'center')
        self._caption_text, self._caption_layer = value, layer
        return layer

    def frame(self, elapsed=None, phase=0, caption=''):
        image = self.base.copy().convert('RGBA')
        for index, layer in enumerate(self.layers):
            progress = 1 if elapsed is None else max(0, min(1, (elapsed-index*.16)/.45))
            if progress <= 0:
                continue
            ease = 1-(1-progress)**3
            moving = layer
            x = y = 0
            if self.style['id'] == 'radar':
                x = round((1-ease)*70*self.scale * (-1 if index%2 == 0 else 1))
            elif self.style['id'] == 'impact':
                factor = .92 + .08*ease
                moving = layer.resize((round(self.size[0]*factor), round(self.size[1]*factor)), Image.Resampling.BILINEAR)
                x, y = (self.size[0]-moving.width)//2, (self.size[1]-moving.height)//2
            else:
                y = round((1-ease)*35*self.scale)
            if progress < 1:
                moving = moving.copy()
                moving.putalpha(moving.getchannel('A').point(lambda a: round(a*ease)))
            image.alpha_composite(moving, (x, y))
        if elapsed is not None and elapsed > 1.2 and self.boxes:
            draw = ImageDraw.Draw(image)
            box = self.boxes[min(len(self.boxes)-1, int(phase*len(self.boxes)))]
            draw.rounded_rectangle(self.coords(box), radius=round((0 if self.style['id']=='impact' else 12)*self.scale),
                                   outline=self.style['accent'], width=max(2, round(5*self.scale)))
        if caption:
            image.alpha_composite(self.caption(caption))
        return image.convert('RGB')


def scene_asset(scene, project):
    if (project.get('visual_style') or {}).get('media_mode', 'animations') != 'mixed':
        return None
    image_id = scene.get('image_id')
    if not image_id:
        return None
    record = next((item for item in project.get('images', []) if item['id'] == image_id), None)
    if record is None:
        raise ValueError('Uma imagem da cena não está mais disponível. Escolha outra imagem ou remova-a da cena.')
    path = data_path(record['path'])
    if digest(path) != record['sha256']:
        raise ValueError('Uma imagem mudou no disco. Importe-a novamente antes de renderizar.')
    with Image.open(path) as source:
        return source.copy()


def save_png(image, target, project, **content):
    info = PngImagePlugin.PngInfo()
    info.add_text('mycut_provenance', json.dumps({
        'generator': 'MyCut format renderer', 'visual_style': resolve(project), **content,
    }, ensure_ascii=False))
    image.save(target, format='PNG', pnginfo=info)


def preview_png(scene, project, width=360, elapsed=None, clock=None, loop_to=None):
    """Static composition; with elapsed, the animated flow state at that scene time (videos keep their poster).
    loop_to is the first frame a looping Short's last scene fades into."""
    caption = scene.get('narration', '')[:115] + ('…' if len(scene.get('narration', '')) > 115 else '')
    if scene.get('blocks') is not None:
        from .block_render import BlockComposition
        composition = BlockComposition(scene, project, width, clock=clock, loop_to=loop_to)
        image = composition.frame(elapsed, caption=caption, videos=False)
    else:
        image = Composition(scene, project, width, scene_asset(scene, project)).frame(caption=caption)
    stream = io.BytesIO()
    save_png(image, stream, project, scene=scene)
    return stream.getvalue()


def cover_frame(project, concept):
    image = Composition({'title': concept['headline'], 'items': concept['labels'], 'layout': 'flow'}, project).frame()
    text_box(ImageDraw.Draw(image), concept['subtitle'], (90, 1640, 900, 170), resolve(project), 42, align='center')
    return image
