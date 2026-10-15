"""Drawing helpers and subtitle output shared by the video renderer."""
import math
from PIL import ImageDraw, ImageFont

BG = '#FBF8F1'
INK = '#29231F'
LINE = '#CAB8A8'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'


def font(size, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, size)


def text(draw, xy, value, size=40, color=INK, bold=False, anchor='mm', max_width=900):
    face = font(size, bold)
    while draw.textbbox((0, 0), value, font=face)[2] > max_width:
        size -= 1
        face = font(size, bold)
    draw.text(xy, value, font=face, fill=color, anchor=anchor)


def arrow(draw, start, end, color=LINE, width=6):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1]-start[1], end[0]-start[0])
    head = [(end[0]-22*math.cos(angle)+12*math.sin(angle), end[1]-22*math.sin(angle)-12*math.cos(angle)),
            end, (end[0]-22*math.cos(angle)-12*math.sin(angle), end[1]-22*math.sin(angle)+12*math.cos(angle))]
    draw.line(head, fill=color, width=width, joint='curve')


def add_caption(image, value, scale):
    draw = ImageDraw.Draw(image)
    face = font(round(53*scale), True)
    words, lines, line = value.split(), [], ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] > 845*scale and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > 2:
        raise ValueError(f'Legenda longa demais: {value}')
    height = (len(lines)*68+42)*scale
    top = 1610*scale - height/2
    draw.rounded_rectangle((72*scale, top, 1008*scale, top+height), radius=17*scale, fill='#29231F')
    for i, line in enumerate(lines):
        draw.text((540*scale, top+(25+i*68+30)*scale), line, font=face, fill=BG, anchor='mm')


def write_subtitles(timing, folder):
    def srt_time(value):
        ms = round(value*1000)
        return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    blocks = [f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}\n' for i,c in enumerate(timing['captions'])]
    (folder/'legendas.srt').write_text('\n'.join(blocks), encoding='utf-8')
