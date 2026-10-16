"""Animated flow: an agent-authored motion graphic whose states change inside its own block object.

Everything is a pure function of (flow, object box, style, narration clock, elapsed). The same SVG,
rasterized by resvg with the project's Google Font, feeds the editor preview and the exported MP4.
"""
import base64
import io
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from xml.sax.saxutils import escape
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from . import google_fonts, typeset
from .alignment import normalized

ICONS = json.loads((Path(__file__).with_name('flow_icons') / 'icons.json').read_text())
Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9_-]{0,23}$')]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=28)]
Value = Annotated[float, Field(ge=0, le=1_000_000_000, allow_inf_nan=False)]
ChartLabel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=12)]

# Seconds. Tuned so each beat reads at 30 fps without looking hurried.
ENTER, DRAW, TRAVEL, HIGHLIGHT, WORK, BURST, BUILD, GAP = .4, .35, .6, .3, .7, .45, 1.0, .3


class FlowChart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['bars', 'line', 'gauge']
    values: list[Value] = Field(min_length=1, max_length=6)
    labels: list[ChartLabel] = Field(default_factory=list, max_length=6)
    maximum: float | None = Field(default=None, gt=0, le=1_000_000_000, allow_inf_nan=False)
    unit: str = Field(default='', max_length=6)

    @model_validator(mode='after')
    def consistent(self):
        if self.kind == 'gauge' and (len(self.values) != 1 or len(self.labels) > 1):
            raise ValueError('Um indicador tem exatamente um valor.')
        if self.kind == 'line' and len(self.values) < 2:
            raise ValueError('Um gráfico de linha precisa de ao menos dois valores.')
        if self.kind != 'gauge' and self.labels and len(self.labels) != len(self.values):
            raise ValueError('Informe um rótulo para cada valor do gráfico, ou nenhum.')
        if self.maximum is not None and max(self.values) > self.maximum:
            raise ValueError('O máximo do gráfico deve ser maior ou igual aos valores.')
        if self.kind == 'gauge' and self.maximum is None and self.values[0] > 100:
            raise ValueError('Informe o máximo do indicador quando o valor passar de 100.')
        return self


class FlowNode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Slug
    label: Label
    icon: str | None = None
    shape: Literal['circle', 'rounded', 'diamond'] = 'circle'
    x: float = Field(ge=0, le=100, allow_inf_nan=False)
    y: float = Field(ge=0, le=100, allow_inf_nan=False)
    size: float = Field(default=18, ge=6, le=90, allow_inf_nan=False)
    chart: FlowChart | None = None

    @field_validator('icon')
    @classmethod
    def known_icon(cls, value):
        if value is not None and value not in ICONS:
            raise ValueError('Use um ícone da lista disponível.')
        return value


class FlowLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Slug
    target: Slug

    @model_validator(mode='after')
    def distinct(self):
        if self.source == self.target:
            raise ValueError('Uma conexão liga dois nós diferentes.')
        return self


class FlowStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Slug | None = None
    target: Slug
    kind: Literal['request', 'result'] = 'request'
    anchor: str | None = Field(default=None, min_length=1, max_length=60)


class FlowSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nodes: list[FlowNode] = Field(min_length=1, max_length=8)
    links: list[FlowLink] = Field(default_factory=list, max_length=10)
    steps: list[FlowStep] = Field(min_length=1, max_length=14)

    @model_validator(mode='after')
    def connected(self):
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError('Cada nó do fluxo precisa de uma identificação única.')
        pairs = set()
        for link in self.links:
            if link.source not in ids or link.target not in ids:
                raise ValueError('Uma conexão referencia um nó inexistente.')
            pair = frozenset((link.source, link.target))
            if pair in pairs:
                raise ValueError('Há duas conexões entre os mesmos nós.')
            pairs.add(pair)
        for step in self.steps:
            if step.target not in ids or (step.source is not None and step.source not in ids):
                raise ValueError('Uma etapa referencia um nó inexistente.')
            if step.source is not None and frozenset((step.source, step.target)) not in pairs:
                raise ValueError('Uma etapa com pulso precisa de uma conexão entre a origem e o destino.')
        return self


# ---------------------------------------------------------------- narration clock

def estimate_clock(narration, pauses=None):
    """Same estimate as production.estimated_timing for a scene without generated narration; `pauses` are the
    seconds of silence after word indices (pause_points), which delay every later word."""
    words = narration.split()
    spoken = max(2.0, len(words)/2.7 + .3)
    pauses = {index: seconds for index, seconds in (pauses or {}).items() if index < len(words)}
    starts, ends, silence = [], [], 0
    for k in range(len(words)):
        starts.append(spoken*k/len(words) + silence)
        ends.append(spoken*(k+1)/len(words) + silence)
        silence += pauses.get(k, 0)
    return {'duration': spoken + sum(pauses.values()), 'words': starts, 'ends': ends, 'source': 'estimate'}


def clock_from_timing(timing, index):
    bounds = timing['scenes'][index]
    spoken = [w for w in timing.get('words', []) if w['scene'] == index]
    return {'duration': bounds['end']-bounds['start'], 'words': [w['start']-bounds['start'] for w in spoken],
            'ends': [w['end']-bounds['start'] for w in spoken],
            'source': 'estimate' if timing.get('timing_source') == 'estimated_preview_only' else 'narration'}


def scene_clock(project, scene):
    """Aligned narration times when the saved audio still matches; otherwise the export estimate."""
    from . import store, alignment
    from .media import data_path
    scenes = project.get('scenes') or []
    index = next((i for i, s in enumerate(scenes) if s.get('id') and s.get('id') == scene.get('id')), None)
    audio = project.get('audio')
    if (index is not None and audio and scenes[index]['narration'] == scene['narration']
            and audio.get('script_hash') == store.script_hash(project)):
        try:
            transcript = json.loads(data_path(audio['alignment']).read_text())
            timing = alignment.make_timing(store.script(project), transcript, audio['duration'], None)
            return clock_from_timing(timing, index)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            # Imported narration has no saved word alignment: the export aligns it with Whisper.
            return {**estimate_clock(scene['narration'], pause_points(scene)), 'source': 'export'}
    return estimate_clock(scene['narration'], pause_points(scene))


def anchor_spans(anchors, narration):
    """First and last narration word index of each anchor passage, searched in order; None when absent or not found.
    Words with nothing to say, like a spaced "—", are skipped on both sides but keep their place in the narration."""
    spoken = [(i, n) for i, n in enumerate(normalized(w) for w in narration.split()) if n]
    words = [n for _, n in spoken]
    cursor, found = 0, []
    for anchor in anchors:
        span = None
        needle = [n for n in (normalized(w) for w in (anchor or '').split()) if n]
        if needle:
            for i in range(cursor, len(words)-len(needle)+1):
                if words[i:i+len(needle)] == needle:
                    span = (spoken[i][0], spoken[i+len(needle)-1][0])
                    cursor = i+1
                    break
        found.append(span)
    return found


def resolve_anchors(flow, narration):
    """Word index of each step anchor, searched in order; None when absent or not found."""
    return [span and span[0] for span in anchor_spans([step.get('anchor') for step in flow['steps']], narration)]


def pause_points(scene):
    """Seconds of silence after each word index, for the pauses whose passage is found in the narration, in order."""
    pauses = scene.get('pauses') or []
    points = {}
    for pause, span in zip(pauses, anchor_spans([pause['after'] for pause in pauses], scene.get('narration', ''))):
        if span is not None:
            points[span[1]] = points.get(span[1], 0) + pause['seconds']
    return points


def anchor_warnings(flow, narration):
    return [i for i, (step, index) in enumerate(zip(flow['steps'], resolve_anchors(flow, narration)))
            if step.get('anchor') and index is None]


def schedule(flow, narration, clock):
    """Start time of every step: its narration anchor, or an even spread between known times."""
    duration = max(1.0, clock['duration'])
    count = len(flow['steps'])
    # The last step must still travel, react and build its chart before the scene ends.
    first = min(.8, duration*.15)
    last = max(first, duration-TRAVEL-BUILD-.2)
    anchors = resolve_anchors(flow, narration)
    known = {i: clock['words'][a] for i, a in enumerate(anchors) if a is not None and a < len(clock['words'])}
    times = []
    for i in range(count):
        if i in known:
            times.append(known[i])
            continue
        left = max((k for k in known if k < i), default=None)
        right = min((k for k in known if k > i), default=None)
        if left is None and right is None:
            times.append(first + (last-first)*i/max(1, count-1))
        elif left is None:
            times.append(first + (known[right]-first)*i/right)
        elif right is None:
            times.append(known[left] + (last-known[left])*(i-left)/max(1, count-1-left))
        else:
            times.append(known[left] + (known[right]-known[left])*(i-left)/(right-left))
    for i in range(1, count):
        times[i] = max(times[i], times[i-1]+GAP)
    # A late anchor is pulled back so the complete flow is visible before the next scene.
    for i in range(count-1, -1, -1):
        times[i] = max(0.0, min(times[i], last-(count-1-i)*GAP))
    return times


# ---------------------------------------------------------------- geometry and text

def mix(first, second, amount):
    a = [int(first[i:i+2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i+2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x*(1-amount)+y*amount):02x}' for x, y in zip(a, b))


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ease(value):
    value = clamp(value)
    return 4*value**3 if value < .5 else 1-(-2*value+2)**3/2


def pop(value):
    value = clamp(value)
    return 1 + 2.2*(value-1)**3 + 1.2*(value-1)**2


def wrap(face, text, width):
    lines, line = [], ''
    for word in text.split():
        candidate = (line+' '+word).strip()
        if line and typeset.length(candidate, face) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + ([line] if line else [])


def number(value, unit=''):
    text = f'{value:,.0f}' if float(value).is_integer() or value >= 100 else f'{value:,.1f}'
    return text.replace(',', ' ').replace('.', ',').replace(' ', '.') + unit


class Layout:
    """Node boxes, label lines and connection lanes inside the object box (1080-frame pixels)."""
    def __init__(self, obj, width, height, style):
        self.flow, self.width, self.height = obj['flow'], width, height
        self.family = obj.get('font') or style.get('google_font') or 'Roboto'
        self.size = obj['font_size']
        self.face = google_fonts.face(self.family, round(self.size))
        self.small = google_fonts.face(self.family, max(8, round(self.size*.7)))
        self.font_path = str(google_fonts.install(self.family))
        self.font_name = self.face.getname()[0]
        self.nodes, self.problems = {}, []
        short = min(width, height)
        for node in self.flow['nodes']:
            if node.get('chart'):
                hw = min(width, width*node['size']/100)/2
                hh = min(height, hw*2*.62)/2
            else:
                hw = hh = min(short, short*node['size']/100)/2
            cx = clamp(width*node['x']/100, hw, width-hw)
            cy = clamp(height*node['y']/100, hh, height-hh)
            leading = self.size*1.2
            if node.get('chart'):
                label_width = hw*2*.88
                lines = wrap(self.face, node['label'], label_width)
                top, lx = cy-hh+hw*.08, cx
                if len(lines) > 1 or any(typeset.length(line, self.face) > label_width for line in lines):
                    self.problems.append(node['id'])
            else:
                label_width = min(width, max(hw*2.6, width*.3))
                lines = wrap(self.face, node['label'], label_width)
                block = len(lines)*leading
                top = cy+hh+self.size*.35
                if top+block > height:
                    top = cy-hh-self.size*.35-block
                lx = clamp(cx, label_width/2, width-label_width/2)
                if len(lines) > 2 or top < 0 or any(typeset.length(line, self.face) > label_width for line in lines):
                    self.problems.append(node['id'])
            self.nodes[node['id']] = {**node, 'cx': cx, 'cy': cy, 'hw': hw, 'hh': hh,
                                      'lines': lines, 'label_top': top, 'label_x': lx, 'leading': leading}
        kinds = {}
        for step in self.flow['steps']:
            if step.get('source'):
                kinds.setdefault(frozenset((step['source'], step['target'])), set()).add(step['kind'])
        self.lane_gap = short*.035
        self.kinds = kinds

    def edge(self, node, toward):
        dx, dy = toward[0]-node['cx'], toward[1]-node['cy']
        length = math.hypot(dx, dy) or 1
        if node.get('chart'):
            reach = min(node['hw']/abs(dx) if dx else math.inf, node['hh']/abs(dy) if dy else math.inf)*length
        else:
            reach = node['hw']*(1.12 if node['shape'] == 'diamond' else 1)
        reach += max(6, self.size*.25)
        return node['cx']+dx/length*reach, node['cy']+dy/length*reach

    def lane(self, source, target, kind):
        """Request and result lanes run side by side when a connection carries both."""
        a, b = self.nodes[source], self.nodes[target]
        both = len(self.kinds.get(frozenset((source, target)), ())) > 1
        offset = (self.lane_gap if kind == 'result' else -self.lane_gap) if both else 0
        # Perpendicular to the canonical (sorted) direction, so lanes never swap sides.
        first, second = sorted((source, target))
        u, v = self.nodes[first], self.nodes[second]
        dx, dy = v['cx']-u['cx'], v['cy']-u['cy']
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy/length*offset, dx/length*offset
        start = self.edge(a, (b['cx'], b['cy']))
        end = self.edge(b, (a['cx'], a['cy']))
        return (start[0]+nx, start[1]+ny), (end[0]+nx, end[1]+ny)


# ---------------------------------------------------------------- timeline

class Plan:
    def __init__(self, flow, narration, clock):
        steps = flow['steps']
        self.starts = schedule(flow, narration, clock)
        self.travel, self.arrivals = [], []
        for i, (step, start) in enumerate(zip(steps, self.starts)):
            if step.get('source') is None:
                travel = 0
            else:
                following = self.starts[i+1]-start if i+1 < len(steps) else TRAVEL/.8
                travel = min(TRAVEL, max(.25, following*.8))
            self.travel.append(travel)
            self.arrivals.append(start+travel)
        self.appear, order = {}, []

        def enter(node, at):
            if node not in self.appear:
                at = max(at, self.appear[order[-1]]+.15 if order else 0, 0)
                self.appear[node] = at
                order.append(node)
        for step, start in zip(steps, self.starts):
            if step.get('source'):
                enter(step['source'], start-DRAW-ENTER-.05)
            enter(step['target'], start-ENTER)
        for node in flow['nodes']:
            enter(node['id'], 0)
        self.lanes = {}
        for i, step in enumerate(steps):
            if step.get('source'):
                key = (frozenset((step['source'], step['target'])), step['kind'])
                if key not in self.lanes:
                    ready = max(self.appear[step['source']], self.appear[step['target']])
                    begin = max(ready, self.starts[i]-DRAW)
                    self.lanes[key] = {'source': step['source'], 'target': step['target'], 'kind': step['kind'],
                                       'begin': begin, 'end': max(begin+.1, self.starts[i])}
        for link in flow['links']:
            key = (frozenset((link['source'], link['target'])), 'request')
            if not any(k[0] == key[0] for k in self.lanes):
                begin = max(self.appear[link['source']], self.appear[link['target']])+ENTER
                self.lanes[key] = {'source': link['source'], 'target': link['target'], 'kind': 'request',
                                   'begin': begin, 'end': begin+DRAW}
        self.events = {node['id']: {'arrivals': [], 'departures': []} for node in flow['nodes']}
        for i, step in enumerate(steps):
            self.events[step['target']]['arrivals'].append(self.arrivals[i])
            if step.get('source'):
                self.events[step['source']]['departures'].append(self.starts[i])
        ends = [lane['end'] for lane in self.lanes.values()] + [t+ENTER for t in self.appear.values()]
        ends += [t+HIGHLIGHT+WORK+BURST+BUILD for t in self.arrivals] + [t+BURST for t in self.starts]
        self.end = max(ends) + .1

    def work(self, node, t):
        """(highlight 0..1, working, burst 0..1 or None, received) for a node at time t."""
        events = self.events[node]
        glow, working, burst = 0.0, False, None
        received = any(a <= t for a in events['arrivals'])
        for arrival in events['arrivals']:
            if arrival <= t:
                glow = max(glow, 1-(t-arrival)/(HIGHLIGHT*3))
                later = [d for d in events['departures'] if d > arrival+.05]
                finish = min(later) if later else arrival+HIGHLIGHT+WORK
                if arrival+HIGHLIGHT <= t < finish:
                    working = True
        for departure in events['departures']:
            if departure <= t < departure+BURST:
                burst = (t-departure)/BURST
        return clamp(glow), working, burst, received


# ---------------------------------------------------------------- drawing

def attributes(values):
    return ' '.join(f'{key}="{escape(str(value), {chr(34): "&quot;"})}"' for key, value in values.items())


def icon(name, cx, cy, size, color, opacity):
    scale = size/24
    parts = ''.join(f'<{tag} {attributes(attrs)}/>' for tag, attrs in ICONS[name])
    return (f'<g transform="translate({cx-size/2:.2f} {cy-size/2:.2f}) scale({scale:.4f})" fill="none" stroke="{color}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity:.3f}">{parts}</g>')


def shape(node, scale, fill, stroke, width, extra=''):
    cx, cy, r = node['cx'], node['cy'], node['hw']*scale
    if node['shape'] == 'rounded':
        return (f'<rect x="{cx-r:.2f}" y="{cy-r:.2f}" width="{2*r:.2f}" height="{2*r:.2f}" rx="{r*.3:.2f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{width:.2f}" {extra}/>')
    if node['shape'] == 'diamond':
        d = r*1.12
        return (f'<polygon points="{cx:.2f},{cy-d:.2f} {cx+d:.2f},{cy:.2f} {cx:.2f},{cy+d:.2f} {cx-d:.2f},{cy:.2f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{width:.2f}" stroke-linejoin="round" {extra}/>')
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{width:.2f}" {extra}/>'


def text(x, y, value, size, color, opacity=1.0, anchor='middle', weight=None, face=None):
    bold = f' font-weight="{weight}"' if weight else ''
    if face is not None and typeset.has_emoji(value, face):
        # resvg has no color emoji: text runs stay SVG text, each emoji run becomes an embedded image.
        spots, baseline = typeset.placed(value, face, (x, y), {'start': 'ls', 'middle': 'ms', 'end': 'rs'}[anchor])
        parts = []
        for piece, emoji, left in spots:
            if emoji:
                width, height, data = emoji_png(piece, face.size)
                parts.append(f'<image x="{left:.2f}" y="{typeset.emoji_top(face, baseline):.2f}" width="{width}" '
                             f'height="{height}" href="data:image/png;base64,{data}"/>')
            elif piece.strip():
                parts.append(f'<text x="{left:.2f}" y="{baseline:.2f}" font-size="{size:.2f}" fill="{color}" '
                             f'text-anchor="start" xml:space="preserve"{bold}>{escape(piece)}</text>')
        return f'<g opacity="{opacity:.3f}">' + ''.join(parts) + '</g>'
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" fill="{color}" text-anchor="{anchor}" '
            f'opacity="{opacity:.3f}"{bold}>{escape(value)}</text>')


@lru_cache(maxsize=256)
def emoji_png(piece, size):
    image = typeset.glyphs(piece, size)
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    return image.width, image.height, base64.b64encode(buffer.getvalue()).decode()


class FlowRenderer:
    def __init__(self, obj, box, style, narration, clock):
        self.size = (max(1, round(box[2])), max(1, round(box[3])))
        self.layout = Layout(obj, self.size[0], self.size[1], style)
        self.plan = Plan(obj['flow'], narration, clock)
        self.ink = obj.get('color') or style['text_color']
        self.background, self.accent = style['background'], style['accent']
        self.final, self.last = None, (None, None)

    def svg(self, t):
        lay, plan = self.layout, self.plan
        short = min(lay.width, lay.height)
        stroke = max(3, short*.008)
        line = mix(self.background, self.ink, .38)
        parts = []
        # Lanes: request solid, result dashed; both traced from sender to receiver.
        for lane in plan.lanes.values():
            progress = ease((t-lane['begin'])/max(.01, lane['end']-lane['begin']))
            if progress <= 0:
                continue
            (x1, y1), (x2, y2) = lay.lane(lane['source'], lane['target'], lane['kind'])
            x, y = x1+(x2-x1)*progress, y1+(y2-y1)*progress
            dash = f' stroke-dasharray="{stroke*3:.1f} {stroke*2.4:.1f}"' if lane['kind'] == 'result' else ''
            parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="{line}" '
                         f'stroke-width="{stroke:.2f}" stroke-linecap="round"{dash}/>')
            if progress >= 1:
                angle = math.atan2(y2-y1, x2-x1)
                head = max(10, short*.022)
                points = [(x2-head*math.cos(angle-.5), y2-head*math.sin(angle-.5)), (x2, y2),
                          (x2-head*math.cos(angle+.5), y2-head*math.sin(angle+.5))]
                parts.append(f'<polyline points="{" ".join(f"{px:.2f},{py:.2f}" for px, py in points)}" fill="none" '
                             f'stroke="{line}" stroke-width="{stroke:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
        for node in lay.flow['nodes']:
            parts.append(self.node(lay.nodes[node['id']], t))
        # Pulses ride on top: accent circles carry requests, ink diamonds carry results back.
        for i, step in enumerate(lay.flow['steps']):
            start, travel = plan.starts[i], plan.travel[i]
            if not step.get('source') or not start <= t < start+travel:
                continue
            (x1, y1), (x2, y2) = lay.lane(step['source'], step['target'], step['kind'])
            radius = max(8, short*.022)
            for k, alpha in ((3, .15), (2, .3), (1, .5), (0, 1)):
                p = ease((t-start)/travel) - k*.05
                if p < 0:
                    continue
                x, y, r = x1+(x2-x1)*p, y1+(y2-y1)*p, radius*(1-k*.15)
                if step['kind'] == 'result':
                    parts.append(f'<polygon points="{x:.2f},{y-r*1.3:.2f} {x+r*1.3:.2f},{y:.2f} {x:.2f},{y+r*1.3:.2f} '
                                 f'{x-r*1.3:.2f},{y:.2f}" fill="{self.ink}" opacity="{alpha:.2f}"/>')
                else:
                    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{self.accent}" opacity="{alpha:.2f}"/>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.size[0]}" height="{self.size[1]}" '
                f'viewBox="0 0 {self.size[0]} {self.size[1]}" font-family="{escape(lay.font_name)}">' + ''.join(parts) + '</svg>')

    def node(self, node, t):
        lay, plan = self.layout, self.plan
        entered = (t-plan.appear[node['id']])/ENTER
        if entered <= 0:
            return ''
        opacity, scale = clamp(entered*1.5), .6+.4*pop(entered)
        glow, working, burst, received = plan.work(node['id'], t)
        stroke = max(3, min(lay.width, lay.height)*.007)
        parts = []
        if node.get('chart'):
            parts.append(self.chart(node, t, scale))
        else:
            r = node['hw']
            if glow > 0:
                parts.append(shape(node, scale*(1.18+.22*(1-glow)), 'none', self.accent, r*.1, f'opacity="{glow*.55:.3f}"'))
            if burst is not None:
                parts.append(shape(node, scale*(1+.55*burst), 'none', self.accent, stroke, f'opacity="{(1-burst)*.8:.3f}"'))
            fill = mix(mix(self.background, self.ink, .06), self.accent, .28*glow)
            edge = self.accent if received else mix(self.background, self.ink, .38)
            parts.append(shape(node, scale, fill, edge, stroke))
            if node.get('icon'):
                parts.append(icon(node['icon'], node['cx'], node['cy'], r*1.05*scale,
                                  mix(self.ink, self.accent, glow), 1))
            if working:
                ring = r*scale*1.2
                circumference = 2*math.pi*ring
                angle = (t*320) % 360
                parts.append(f'<circle cx="{node["cx"]:.2f}" cy="{node["cy"]:.2f}" r="{ring:.2f}" fill="none" '
                             f'stroke="{self.accent}" stroke-width="{stroke*1.3:.2f}" stroke-linecap="round" '
                             f'stroke-dasharray="{circumference*.28:.2f} {circumference*.72:.2f}" '
                             f'transform="rotate({angle:.1f} {node["cx"]:.2f} {node["cy"]:.2f})"/>')
        ascent = lay.face.getmetrics()[0]
        for n, value in enumerate(node['lines']):
            baseline = node['label_top']+ascent+n*node['leading']
            if not node.get('chart'):
                # A backdrop keeps labels legible where a connection passes behind them.
                half = typeset.length(value, lay.face)/2+lay.size*.25
                parts.append(f'<rect x="{node["label_x"]-half:.2f}" y="{baseline-ascent-lay.size*.1:.2f}" width="{2*half:.2f}" '
                             f'height="{node["leading"]:.2f}" rx="{lay.size*.2:.2f}" fill="{self.background}" opacity=".88"/>')
            parts.append(text(node['label_x'], baseline, value, lay.size, self.ink, face=lay.face))
        return f'<g opacity="{opacity:.3f}">' + ''.join(parts) + '</g>'

    def chart(self, node, t, scale):
        lay, chart = self.layout, node['chart']
        arrivals = self.plan.events[node['id']]['arrivals']
        begin = min(arrivals) if arrivals else self.plan.appear[node['id']]+ENTER
        progress = clamp((t-begin)/BUILD)
        cx, cy, hw, hh = node['cx'], node['cy'], node['hw']*scale, node['hh']*scale
        stroke = max(2, min(lay.width, lay.height)*.005)
        glow = self.plan.work(node['id'], t)[0]
        parts = [f'<rect x="{cx-hw:.2f}" y="{cy-hh:.2f}" width="{2*hw:.2f}" height="{2*hh:.2f}" rx="{min(hw, hh)*.12:.2f}" '
                 f'fill="{mix(mix(self.background, self.ink, .04), self.accent, .15*glow)}" '
                 f'stroke="{self.accent if arrivals and t >= begin else mix(self.background, self.ink, .3)}" stroke-width="{stroke:.2f}"/>']
        small = lay.small.size
        pad = hw*.08
        title = node['label_top']-node['cy']+cy+node['leading']*scale
        left, right, top, bottom = cx-hw+pad, cx+hw-pad, title+small*1.4, cy+hh-pad-(small*1.3 if chart['labels'] else 0)
        values = chart['values']
        top_value = chart['maximum'] or (100 if chart['kind'] == 'gauge' else max(values) or 1)
        if chart['kind'] == 'bars':
            count = len(values)
            slot = (right-left)/count
            stagger = .5/count
            for i, value in enumerate(values):
                p = ease((progress-i*stagger)/(1-(count-1)*stagger))
                if p <= 0:
                    continue
                height = (bottom-top)*value/top_value*p
                x = left+slot*i+slot*.2
                parts.append(f'<rect x="{x:.2f}" y="{bottom-height:.2f}" width="{slot*.6:.2f}" height="{max(.1, height):.2f}" '
                             f'rx="{slot*.08:.2f}" fill="{self.accent}"/>')
                parts.append(text(x+slot*.3, bottom-height-small*.3, number(value*p, chart['unit']), small, self.ink, p, face=lay.small))
                if chart['labels']:
                    parts.append(text(x+slot*.3, bottom+small*1.05, chart['labels'][i], small, self.ink, p, face=lay.small))
        elif chart['kind'] == 'line':
            count = len(values)
            points = [(left+(right-left)*i/(count-1), bottom-(bottom-top)*v/top_value) for i, v in enumerate(values)]
            reach = progress*(count-1)
            drawn = [points[0]]
            for i in range(1, count):
                if reach >= i:
                    drawn.append(points[i])
                elif reach > i-1:
                    f = reach-(i-1)
                    drawn.append((points[i-1][0]+(points[i][0]-points[i-1][0])*f, points[i-1][1]+(points[i][1]-points[i-1][1])*f))
            if progress > 0:
                parts.append(f'<line x1="{left:.2f}" y1="{bottom:.2f}" x2="{right:.2f}" y2="{bottom:.2f}" '
                             f'stroke="{mix(self.background, self.ink, .3)}" stroke-width="{stroke*.6:.2f}"/>')
                parts.append(f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in drawn)}" fill="none" '
                             f'stroke="{self.accent}" stroke-width="{stroke*1.6:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
            for i, (x, y) in enumerate(points):
                p = clamp((reach-i+.3)/.3) if progress > 0 else 0
                if p <= 0:
                    continue
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{stroke*2.2:.2f}" fill="{self.accent}" opacity="{p:.3f}"/>')
                parts.append(text(x, y-small*.6, number(values[i], chart['unit']), small, self.ink, p, face=lay.small))
                if chart['labels']:
                    parts.append(text(x, bottom+small*1.05, chart['labels'][i], small, self.ink, p, face=lay.small))
        else:
            radius = min(hw-pad, (bottom-top)*.9)
            base_y = bottom-(bottom-top-radius)/2
            share = ease(progress)*values[0]/top_value
            def arc(fraction):
                angle = math.pi*(1-fraction)
                return base_y-radius*math.sin(angle), cx+radius*math.cos(angle)
            track = mix(self.background, self.ink, .15)
            parts.append(f'<path d="M {cx-radius:.2f} {base_y:.2f} A {radius:.2f} {radius:.2f} 0 0 1 {cx+radius:.2f} {base_y:.2f}" '
                         f'fill="none" stroke="{track}" stroke-width="{radius*.18:.2f}" stroke-linecap="round"/>')
            if share > 0:
                y, x = arc(share)
                parts.append(f'<path d="M {cx-radius:.2f} {base_y:.2f} A {radius:.2f} {radius:.2f} 0 0 1 {x:.2f} {y:.2f}" '
                             f'fill="none" stroke="{self.accent}" stroke-width="{radius*.18:.2f}" stroke-linecap="round"/>')
                parts.append(text(cx, base_y-radius*.15, number(values[0]*ease(progress), chart['unit']), lay.size, self.ink, ease(progress*2), face=lay.face))
                if chart['labels']:
                    parts.append(text(cx, base_y+small*1.3, chart['labels'][0], small, self.ink, ease(progress*2), face=lay.small))
        return ''.join(parts)

    def layer(self, t=None):
        """RGBA layer of the object box at scene time t; None (or after the last beat) is the final state."""
        final = t is None or t >= self.plan.end
        if final and self.final is not None:
            return self.final
        svg = self.svg(math.inf if final else max(0.0, t))
        # Between beats the drawing is identical; reuse it instead of rasterizing again.
        if svg != self.last[0]:
            self.last = (svg, rasterize(svg, self.layout.font_path, self.layout.font_name))
        if final:
            self.final = self.last[1]
        return self.last[1]


def rasterize(svg, font_path, font_name):
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg, font_files=[font_path], skip_system_fonts=True, font_family=font_name)
    with Image.open(io.BytesIO(bytes(png))) as image:
        return image.convert('RGBA')


# ---------------------------------------------------------------- inspection

def problems(obj, box, style, narration):
    """Blocking issues (label overflow) and non-blocking anchor warnings for one flow object."""
    issues, warnings = [], []
    if not obj.get('flow'):
        issues.append({'object_id': obj['id'], 'kind': 'missing_flow',
                       'message': 'Peça ao agente para montar o Fluxo animado ou remova o objeto.'})
        return issues, warnings
    width, height = max(1, round(box[2])), max(1, round(box[3]))
    if Layout(obj, width, height, style).problems:
        fitted = next((size for size in range(int(obj['font_size'])-1, 11, -1)
                       if not Layout({**obj, 'font_size': size}, width, height, style).problems), None)
        issues.append({'object_id': obj['id'], 'kind': 'overflow', 'font_size': fitted,
                       'message': 'Um rótulo do fluxo não cabe. Aumente a área, encurte o rótulo ou ajuste a fonte.'})
    for index in anchor_warnings(obj['flow'], narration):
        warnings.append({'object_id': obj['id'], 'kind': 'anchor', 'step': index,
                         'message': f'A âncora da etapa {index+1} não está na narração; ela segue a distribuição automática.'})
    return issues, warnings


@lru_cache(maxsize=1)
def icon_names():
    return sorted(ICONS)


GUIDE = (
    'Fluxo animado (objeto type="flow", campo flow) é o recurso visual principal do MyCut: use-o sempre que a fala '
    'descrever um processo, uma sequência, causa e efeito, troca de dados entre partes, números ou evolução. '
    'Não é um slide com transição: cada movimento mostra quem envia, quem recebe e o que acontece depois; nada decorativo. '
    'flow.nodes (até 8): id curto em minúsculas (a-z, 0-9, - ou _), label curto (1 a 3 palavras, até 28 caracteres), '
    'icon de flow_icons ou null, shape circle|rounded|diamond, x e y = centro do nó em % da área do objeto, '
    'size = diâmetro em % do lado menor da área (14 a 26 para nós com ícone). O vídeo é vertical 9:16: distribua os nós '
    'sem sobrepor nós nem rótulos e deixe espaço abaixo de cada nó para o rótulo. '
    'Um nó com chart vira um gráfico que se constrói ao receber um pulso: kind bars|line|gauge, values (até 6), labels curtos '
    '(um por valor, ou []), maximum ou null, unit como "%" ou ""; nesse caso size é a largura em % da área (40 a 90) e o label é o título. '
    'flow.links liga pares de nós (source, target). flow.steps (até 14) é a sequência narrada: source→target envia um pulso '
    'pela conexão; kind=request para pedidos e comandos (ida), kind=result para resultados que voltam; source=null apenas '
    'ativa o target (por exemplo, construir um gráfico isolado). O nó que recebe um pulso acende, processa e dispara a próxima '
    'etapa que sai dele: encadeie as etapas na ordem de causa e efeito. anchor é uma palavra ou trecho curto copiado '
    'literalmente da narração da cena, no instante em que a etapa acontece, em ordem de fala; use null quando não houver '
    'palavra adequada e a etapa será distribuída automaticamente. No objeto flow, font_size é o tamanho dos rótulos (26 a 36) '
    'e text fica vazio. Prefira o Fluxo animado em um bloco alto (60% ou mais da cena).'
)


def check_for_agent(obj, box, style, narration):
    """Messages an agent can act on: unknown anchors and labels that do not fit."""
    issues, warnings = problems(obj, box, style, narration)
    return [item['message'] for item in issues] + [item['message'] for item in warnings]
