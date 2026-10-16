"""Authoritative layout, text overflow and video compositing for scene blocks and their planos."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from . import visuals, google_fonts, flow, captions, typeset
from .scene_layout import geometry, validate_assets, shots
from .scene_media import VideoFrames
from .scene_images import AnimatedImage
from .media import data_path, digest
from .alignment import normalized

# A plano never lasts less than this, unless the scene itself is too short for its planos (ADR 0004).
MIN_SHOT = 1.0
FADE = .4
# Lines enter over the first part of the plano; typing ends before the plano does.
REVEAL_SPAN, LINE_IN, LINE_RISE = .7, .25, 16
TYPING_CPS, TYPING_SPAN = 18, .8
# Camera motion travels over this extra framing.
MOTION_ZOOM = 1.15
# A looping Short livre fades into its first frame and holds it, so the restart has no visible seam.
LOOP_FADE, LOOP_HOLD = .4, .1


def wrapped_lines(obj, box, face):
    """Lines as drawn in the box, each with the index of the text line it came from."""
    width = max(1, box[2]-16)
    lines = []
    for number, paragraph in enumerate(obj.get('text', '').split('\n')):
        line = ''
        for word in paragraph.split():
            # Preserve long tokens by wrapping characters, never clipping silently.
            pieces = ['']
            for char in typeset.clusters(word):
                if pieces[-1] and typeset.length(pieces[-1]+char, face) > width:
                    pieces.append('')
                pieces[-1] += char
            for piece in pieces:
                candidate = (line+' '+piece).strip()
                if line and typeset.length(candidate, face) > width:
                    lines.append((line, number))
                    line = piece
                else:
                    line = candidate
        lines.append((line, number))
    return lines


def text_layout(obj, box, style, size=None):
    pixels = size or obj['font_size']
    face = google_fonts.face(obj.get('font') or style.get('google_font') or 'Roboto', round(pixels))
    width, height = max(1, box[2]-16), max(1, box[3]-16)
    lines = [line for line, _ in wrapped_lines(obj, box, face)]
    ascent, descent = face.getmetrics()
    leading = max(pixels * 1.3, ascent + descent)
    overflow = len(lines)*leading > height or any(typeset.length(line, face) > width for line in lines)
    return face, lines, leading, overflow


def shot_windows(scene, clock):
    """Start and end of every plano in scene time: its narration anchor, or an even spread between known starts."""
    planos = shots(scene)
    duration = max(.1, clock['duration'])
    count = len(planos)
    if count == 1:
        return [(0.0, duration)]
    narration = scene.get('narration', '')
    anchors = flow.resolve_anchors({'steps': [{'anchor': s.get('anchor')} for s in planos[1:]]}, narration)
    known = {0: 0.0, count: duration}
    known.update({i+1: clock['words'][a] for i, a in enumerate(anchors) if a is not None and a < len(clock['words'])})
    starts = []
    for i in range(count):
        if i in known:
            starts.append(known[i])
            continue
        left = max(k for k in known if k < i)
        right = min(k for k in known if k > i)
        starts.append(known[left] + (known[right]-known[left])*(i-left)/(right-left))
    gap = min(MIN_SHOT, duration/count)
    for i in range(1, count):
        starts[i] = max(starts[i], starts[i-1]+gap)
    # A late anchor is pulled back so every later plano still gets its minimum time.
    for i in range(count-1, 0, -1):
        starts[i] = min(starts[i], duration-(count-i)*gap)
    return [(start, starts[i+1] if i+1 < count else duration) for i, start in enumerate(starts)]


def shot_clock(clock, window):
    start, end = window
    return {**clock, 'duration': end-start, 'words': [w-start for w in clock['words']],
            'ends': [w-start for w in clock.get('ends', [])]}


def inspect(scene, project, clock=None):
    validate_assets(scene, project)
    style = visuals.resolve(project)
    issues, warnings = [], []
    planos = shots(scene)
    windows = shot_windows(scene, clock) if clock else None
    narration = scene.get('narration', '')
    anchors = flow.resolve_anchors({'steps': [{'anchor': s.get('anchor')} for s in planos[1:]]}, narration)
    for index, shot in enumerate(planos):
        background = shot.get('background') or {}
        if background.get('kind') in ('image', 'video') and not background.get('asset_id'):
            issues.append({'shot_id': shot['id'], 'object_id': None, 'kind': 'missing_media',
                           'message': f'Plano {index+1}: selecione o arquivo do fundo ou troque o tipo de fundo.'})
        if index and shot.get('anchor') and anchors[index-1] is None:
            # Anchors are searched in order, so a passage may exist but come before the previous plano's.
            spoken = ' '.join(n for n in (normalized(w) for w in narration.split()) if n)
            needle = ' '.join(n for n in (normalized(w) for w in shot['anchor'].split()) if n)
            where = ('aparece antes do início do plano anterior' if needle and f' {needle} ' in f' {spoken} '
                     else 'não está na narração')
            warnings.append({'shot_id': shot['id'], 'object_id': None, 'kind': 'shot_anchor',
                             'message': f'Plano {index+1}: o trecho “{shot["anchor"]}” {where}; o plano entra no tempo automático.'})
        if windows and windows[index][1]-windows[index][0] < MIN_SHOT-1e-6:
            warnings.append({'shot_id': shot['id'], 'object_id': None, 'kind': 'shot_short',
                             'message': f'Plano {index+1}: a cena é curta demais para {len(planos)} planos de pelo menos 1 s.'})
        for block, info in zip(shot['blocks'], geometry(shot['blocks'])):
            obj = block.get('object')
            if not obj:
                continue
            if obj['type'] in ('image', 'video') and not obj.get('asset_id'):
                issues.append({'shot_id': shot['id'], 'object_id': obj['id'], 'kind': 'missing_media', 'message': 'Selecione um arquivo ou remova o objeto.'})
            if obj['type'] == 'flow':
                blocking, notes = flow.problems(obj, info['object'], style, narration)
                issues += [{'shot_id': shot['id'], **item} for item in blocking]
                warnings += [{'shot_id': shot['id'], **item} for item in notes]
            if obj['type'] in ('title', 'paragraph'):
                if text_layout(obj, info['object'], style)[3]:
                    fitted = None
                    for size in range(int(obj['font_size'])-1, 7, -1):
                        if not text_layout(obj, info['object'], style, size)[3]:
                            fitted = size
                            break
                    issues.append({'shot_id': shot['id'], 'object_id': obj['id'], 'kind': 'overflow', 'font_size': fitted,
                                   'message': 'O texto não cabe. Aumente a área, reduza o texto ou ajuste a fonte.'})
    report = {'issues': issues, 'warnings': warnings, 'geometry': geometry(scene['blocks'])}
    if windows:
        report['shots'] = [{'id': shot['id'], 'start': start, 'end': end} for shot, (start, end) in zip(planos, windows)]
    return report


def validate_project(project):
    for index, scene in enumerate(project['scenes']):
        if scene.get('blocks') is not None:
            issues = inspect(scene, project)['issues']
            if issues:
                raise ValueError(f'Cena {index+1}: {issues[0]["message"]}')


def gradient(size, first, second, angle):
    """Linear gradient with the CSS angle convention, so 180 runs from top to bottom."""
    width, height = size
    radians = math.radians(angle)
    dx, dy = math.sin(radians), -math.cos(radians)
    length = abs(width*dx) + abs(height*dy)
    xs = np.arange(width) - (width-1)/2
    ys = np.arange(height) - (height-1)/2
    t = np.clip((xs[None, :]*dx + ys[:, None]*dy)/length + .5, 0, 1)[..., None]
    a, b = np.array(visuals.rgb(first), dtype=np.float32), np.array(visuals.rgb(second), dtype=np.float32)
    return Image.fromarray(np.round(a + (b-a)*t).astype(np.uint8), 'RGB')


def motion_box(size, motion, progress):
    """Source rectangle of a layer at this point of its camera motion."""
    width, height = size
    progress = min(1.0, max(0.0, progress))
    zoom = {'zoom_in': 1 + (MOTION_ZOOM-1)*progress, 'zoom_out': MOTION_ZOOM - (MOTION_ZOOM-1)*progress}.get(motion, MOTION_ZOOM)
    fx = {'pan_left': 1-progress, 'pan_right': progress}.get(motion, .5)
    fy = {'pan_up': 1-progress, 'pan_down': progress}.get(motion, .5)
    w, h = width/zoom, height/zoom
    x, y = (width-w)*fx, (height-h)*fy
    return (x, y, x+w, y+h)


def moved(layer, motion, progress):
    return layer.resize(layer.size, Image.Resampling.BICUBIC, box=motion_box(layer.size, motion, progress))


def fit(layer, source, mode, zoom=1, crop_x=50, crop_y=50):
    if mode == 'cover':
        ratio = max(layer.width/source.width, layer.height/source.height) * zoom
        width, height = layer.width/ratio, layer.height/ratio
        x, y = (source.width-width)*crop_x/100, (source.height-height)*crop_y/100
        fitted = source.resize(layer.size, Image.Resampling.LANCZOS, box=(x, y, x+width, y+height))
    else:
        fitted = ImageOps.contain(source, layer.size, Image.Resampling.LANCZOS)
    layer.paste(fitted, ((layer.width-fitted.width)//2, (layer.height-fitted.height)//2))


class TextReveal:
    """A title or paragraph that enters line by line or is typed over its plano."""
    def __init__(self, obj, box, style, size, duration):
        self.obj, self.size, self.duration = obj, size, max(.1, duration)
        self.face = google_fonts.face(obj.get('font') or style.get('google_font') or 'Roboto', round(obj['font_size']))
        self.lines = wrapped_lines(obj, box, self.face)
        ascent, descent = self.face.getmetrics()
        self.leading = max(obj['font_size'] * 1.3, ascent + descent)
        text_height = max((n*self.leading+typeset.bbox(line, self.face, 'lt')[3]
                           for n, (line, _) in enumerate(self.lines)), default=0)
        self.dy = max(0, size[1]-16-text_height) * {'top': 0, 'center': .5, 'bottom': 1}[obj.get('text_vertical', 'top')]
        self.color = obj.get('color') or style['text_color']
        self.accent = style['accent']
        self.offsets = [(size[0]-16-typeset.length(line, self.face)) * {'left': 0, 'center': .5, 'right': 1}[obj['align']]
                        for line, _ in self.lines]
        sources = sorted({number for line, number in self.lines if line})
        span = self.duration*REVEAL_SPAN
        self.entries = {number: span*k/max(1, len(sources)) for k, number in enumerate(sources)}
        # Typing advances by whole characters as seen: an emoji sequence appears at once.
        self.units = [typeset.clusters(line) for line, _ in self.lines]
        self.characters = sum(len(units) for units in self.units)
        self.speed = max(TYPING_CPS, self.characters/(self.duration*TYPING_SPAN))

    def layer(self, elapsed):
        image = Image.new('RGBA', self.size)
        pen = ImageDraw.Draw(image)
        if self.obj.get('reveal') == 'typing' and elapsed is not None:
            remaining = int(elapsed*self.speed + 1e-6)
            typing = remaining < self.characters
            caret = None
            for n, units in enumerate(self.units):
                shown = ''.join(units[:max(0, remaining)])
                remaining -= len(units)
                x, y = 8+self.offsets[n], 8+self.dy+n*self.leading
                if shown:
                    typeset.text(pen, (x, y), shown, self.face, self.color, 'lt')
                if caret is None and remaining <= 0:
                    caret = (x+typeset.length(shown, self.face), y)
            if typing and caret:
                pen.rectangle((caret[0]+3, caret[1], caret[0]+3+max(3, self.obj['font_size']*.08), caret[1]+self.obj['font_size']), fill=self.accent)
            return image
        for n, (line, number) in enumerate(self.lines):
            amount = 1.0
            if self.obj.get('reveal') == 'lines' and elapsed is not None:
                amount = min(1.0, max(0.0, (elapsed-self.entries.get(number, 0))/LINE_IN))
            if amount <= 0 or not line:
                continue
            position = (8+self.offsets[n], 8+self.dy+n*self.leading+LINE_RISE*(1-amount))
            if amount >= 1:
                typeset.text(pen, position, line, self.face, self.color, 'lt')
                continue
            piece = Image.new('RGBA', self.size)
            typeset.text(ImageDraw.Draw(piece), position, line, self.face, self.color, 'lt')
            piece.putalpha(piece.getchannel('A').point(lambda value: round(value*amount)))
            image.alpha_composite(piece)
        return image


class ShotComposition:
    """One plano: its background, brand and blocks, drawn at a time measured from the plano's start."""
    def __init__(self, shot, scene, project, style, fps, clock, duration):
        self.style, self.fps, self.duration = style, fps, max(.1, duration)
        self.background = shot.get('background') or None
        self.videos, self.readers, self.flows, self.moving, self.reveals = [], {}, [], [], []
        # Animated GIFs: drawn per frame, with the fitted frame kept until the GIF advances.
        self.animations, self.fitted = [], {}
        self.backdrop_video = self.backdrop_animation = None
        self.backdrop = self.paint_background(project)
        overlay = Image.new('RGBA', (1080, 1920))
        if shot.get('brand', True):
            draw = ImageDraw.Draw(overlay)
            visuals.text_box(draw, style['channel_name'], (80, 95, 920, 70), style, 28)
            draw.line((70, 190, 1010, 190), fill=style['accent'], width=3)
        for block, info in zip(shot['blocks'], geometry(shot['blocks'])):
            obj = block.get('object')
            if not obj:
                continue
            x, y, w, h = info['object']
            size = (max(1, round(w)), max(1, round(h)))
            position = (round(x), round(y))
            layer = Image.new('RGBA', size)
            if obj['type'] == 'flow':
                # Drawn per frame: its states change with the narration (ADR 0003).
                if obj.get('flow'):
                    self.flows.append((flow.FlowRenderer(obj, info['object'], style, scene.get('narration', ''), clock), position))
                continue
            if obj['type'] in ('title', 'paragraph'):
                reveal = TextReveal(obj, info['object'], style, size, self.duration)
                if obj.get('reveal', 'none') != 'none':
                    self.reveals.append((reveal, position))
                    continue
                layer = reveal.layer(None)
            elif obj.get('asset_id'):
                records = project.get('images' if obj['type'] == 'image' else 'videos', [])
                record = next(r for r in records if r['id'] == obj['asset_id'])
                if obj['type'] == 'image' and record.get('animation'):
                    self.animations.append((obj, record, position, size))
                    continue
                path = data_path(record['path'] if obj['type'] == 'image' else record['poster_path'])
                if obj['type'] == 'image' and digest(path) != record['sha256']:
                    raise ValueError('A imagem mudou no disco. Importe-a novamente.')
                with Image.open(path) as source:
                    fit(layer, source.convert('RGBA'), obj['fit'], obj.get('zoom', 1), obj.get('crop_x', 50), obj.get('crop_y', 50))
                if obj['type'] == 'video':
                    self.videos.append((obj, record, (*position, *size)))
                if obj.get('motion', 'none') != 'none':
                    self.moving.append((layer, obj['motion'], position))
                    continue
            overlay.alpha_composite(layer, position)
        self.overlay = overlay
        # Without anything moving behind the blocks, the still part is composed once.
        self.still = None
        if not self.backdrop_video and not self.backdrop_animation and \
                not (self.background and self.background.get('motion', 'none') != 'none'):
            # Dimming applies to the background only, never to the blocks over it.
            self.still = self.darken(self.backdrop)
            self.still.paste(overlay, (0, 0), overlay)

    def paint_background(self, project):
        background, style = self.background, self.style
        if not background:
            return Image.new('RGB', (1080, 1920), style['background'])
        if background['kind'] == 'color':
            image = Image.new('RGB', (1080, 1920), background['color'])
        elif background['kind'] == 'gradient':
            image = gradient((1080, 1920), background['color'], background['color_to'], background.get('angle', 180))
        else:
            image = Image.new('RGB', (1080, 1920), style['background'])
            if background.get('asset_id'):
                kind = background['kind']
                record = next(r for r in project.get('images' if kind == 'image' else 'videos', []) if r['id'] == background['asset_id'])
                path = data_path(record['path'] if kind == 'image' else record['poster_path'])
                if kind == 'image' and digest(path) != record['sha256']:
                    raise ValueError('A imagem do fundo mudou no disco. Importe-a novamente.')
                with Image.open(path) as source:
                    layer = Image.new('RGBA', (1080, 1920))
                    fit(layer, source.convert('RGBA'), 'cover', background.get('zoom', 1), background.get('crop_x', 50), background.get('crop_y', 50))
                image.paste(layer, (0, 0), layer)
                if kind == 'video':
                    self.backdrop_video = record
                elif record.get('animation'):
                    self.backdrop_animation = record
        return image

    def darken(self, image):
        if self.background and self.background.get('dim'):
            return Image.blend(image, Image.new('RGB', image.size, '#000000'), self.background['dim']/100)
        return image.copy()

    def frame(self, elapsed=None, videos=True):
        progress = 0.0 if elapsed is None else elapsed/self.duration
        if self.still is not None:
            image = self.still.copy()
        else:
            if self.backdrop_video and elapsed is not None and videos:
                if 'background' not in self.readers:
                    record = self.backdrop_video
                    self.readers['background'] = VideoFrames(record, (1080, 1920), self.fps, 'cover', self.background.get('zoom', 1),
                                                             self.background.get('crop_x', 50), self.background.get('crop_y', 50))
                image = self.readers['background'].frame(elapsed).copy()
            elif self.backdrop_animation:
                background = self.background
                layer = self.animated('background', self.backdrop_animation, (1080, 1920), 'cover', background.get('zoom', 1),
                                      background.get('crop_x', 50), background.get('crop_y', 50), elapsed)
                image = Image.new('RGB', (1080, 1920), self.style['background'])
                image.paste(layer, (0, 0), layer)
                if background.get('motion', 'none') != 'none':
                    image = moved(image, background['motion'], progress)
            elif self.background.get('motion', 'none') != 'none':
                image = moved(self.backdrop, self.background['motion'], progress)
            else:
                image = self.backdrop.copy()
            image = self.darken(image)
            image.paste(self.overlay, (0, 0), self.overlay)
        for layer, motion, position in self.moving:
            current = moved(layer, motion, progress)
            image.paste(current, position, current)
        for obj, record, position, size in self.animations:
            layer = self.animated(obj['id'], record, size, obj['fit'], obj.get('zoom', 1), obj.get('crop_x', 50), obj.get('crop_y', 50), elapsed)
            if obj.get('motion', 'none') != 'none':
                layer = moved(layer, obj['motion'], progress)
            image.paste(layer, position, layer)
        for obj, record, (x, y, w, h) in self.videos if elapsed is not None and videos else []:
            if obj['id'] not in self.readers:
                ratio = min(w/record['width'], h/record['height'])
                size = (w, h) if obj['fit'] == 'cover' else (max(1, round(record['width']*ratio)), max(1, round(record['height']*ratio)))
                self.readers[obj['id']] = VideoFrames(record, size, self.fps, obj['fit'], obj.get('zoom', 1), obj.get('crop_x', 50), obj.get('crop_y', 50))
            source = self.readers[obj['id']].frame(elapsed)
            layer = Image.new('RGB', (w, h), self.style['background'])
            fit(layer, source, obj['fit'])
            image.paste(layer, (x, y))
        for reveal, position in self.reveals:
            layer = reveal.layer(elapsed)
            image.paste(layer, position, layer)
        for renderer, position in self.flows:
            layer = renderer.layer(elapsed)
            image.paste(layer, position, layer)
        return image

    def animated(self, key, record, size, mode, zoom, crop_x, crop_y, elapsed):
        """The GIF frame shown at this time, fitted to its box; refitted only when the GIF advances."""
        if key not in self.readers:
            self.readers[key] = AnimatedImage(record)
        index, source = self.readers[key].frame(elapsed)
        if self.fitted.get(key, (None,))[0] != index:
            layer = Image.new('RGBA', size)
            fit(layer, source, mode, zoom, crop_x, crop_y)
            self.fitted[key] = (index, layer)
        return self.fitted[key][1]

    def close(self):
        # A closed plano can still be drawn again: its decoders reopen on demand.
        for reader in self.readers.values():
            reader.close()
        self.readers.clear()
        self.fitted.clear()


def loops(project):
    """A Short livre asked to loop does, unless a video ending plays after its last frame."""
    return bool(visuals.resolve(project).get('loop')) and not project.get('ending_id')


def first_frame(project, clock=None):
    """The Short's first frame without its caption: where a loop ends."""
    first = BlockComposition(project['scenes'][0], project, clock=clock)
    try:
        return first.shots[0].frame(0.0)
    finally:
        first.close()


class BlockComposition:
    def __init__(self, scene, project, width=1080, fps=30, clock=None, loop_to=None):
        self.scene, self.project, self.fps = scene, project, fps
        self.scale = width / 1080
        self.size = (width, round(1920*self.scale))
        self.style = visuals.resolve(project)
        validate_assets(scene, project)
        clock = clock or flow.estimate_clock(scene.get('narration', ''), flow.pause_points(scene))
        planos = shots(scene)
        self.windows = shot_windows(scene, clock)
        self.transitions = [shot.get('transition', 'cut') for shot in planos]
        self.shots = [ShotComposition(shot, scene, project, self.style, fps, shot_clock(clock, window), window[1]-window[0])
                      for shot, window in zip(planos, self.windows)]
        # A Short livre times and draws its own captions; the others receive the caption text from the caller.
        self.captions = captions.timed(scene, clock, self.style['captions']) if self.style.get('captions') else None
        # Only the last scene of a looping Short carries the frame it ends on.
        self.loop_to = loop_to

    @property
    def flows(self):
        return [item for shot in self.shots for item in shot.flows]

    def active(self, elapsed):
        return max(i for i, (start, _) in enumerate(self.windows) if i == 0 or elapsed >= start - 1e-9)

    def frame(self, elapsed=None, phase=0, caption='', videos=True):
        looping = False
        if elapsed is None:
            image = self.shots[0].frame(None, videos)
        else:
            index = self.active(elapsed)
            start = self.windows[index][0]
            fading = index and self.transitions[index] == 'fade' and elapsed-start < FADE
            # Planos already over release their video decoders, the previous one after its fade.
            for shot in self.shots[:index-1 if fading else index]:
                if shot.readers:
                    shot.close()
            image = self.shots[index].frame(elapsed-start, videos)
            if fading:
                previous = self.shots[index-1].frame(elapsed-self.windows[index-1][0], videos)
                image = Image.blend(previous, image, max(0.0, elapsed-start)/FADE)
            closing = elapsed - (self.windows[-1][1]-LOOP_HOLD-LOOP_FADE)
            looping = self.loop_to is not None and closing > 0
            if looping:
                image = Image.blend(image.convert('RGB'), self.loop_to.convert('RGB'), min(1.0, closing/LOOP_FADE))
        if self.captions is not None:
            # The loop ends on the bare first frame: no caption over the fade.
            current = None if looping else captions.active(self.captions, elapsed)
            if current:
                captions.draw(image, current, self.style)
        elif caption:
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((70, 1620, 1010, 1810), radius=16,
                                   fill=visuals.blend(self.style['background'], self.style['text_color'], .08))
            visuals.text_box(draw, caption, (105, 1655, 870, 140), self.style, 50, align='center')
        return image.resize(self.size, Image.Resampling.LANCZOS) if self.scale != 1 else image

    def close(self):
        for shot in self.shots:
            shot.close()
