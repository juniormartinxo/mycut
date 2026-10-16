"""One line of text in a font face, with emoji drawn from the color emoji font.

Pillow draws a string with a single face, and no text face carries emoji: a title like
"é só um apelido 😳" came out with a missing-glyph box. Text runs keep the project's face;
each emoji cluster is drawn from Noto Color Emoji, scaled to the face size and sharing its
baseline. A line without emoji goes straight to Pillow, so its pixels do not change.
"""
import os
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

EMOJI_FONT = Path(os.environ.get('MYCUT_EMOJI_FONT', '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'))
# Noto Color Emoji only carries bitmaps at this size; other sizes are scaled from it.
STRIKE = 109
# Joiners, presentation selectors, keycap, skin tones and tag characters extend the previous emoji.
EXTENDERS = {0x200D, 0xFE0E, 0xFE0F, 0x20E3}
MISSING = '\U0010FFFD'


def extends(code):
    return code in EXTENDERS or 0x1F3FB <= code <= 0x1F3FF or 0xE0020 <= code <= 0xE007F


def regional(code):
    return 0x1F1E6 <= code <= 0x1F1FF


def clusters(text):
    """Characters grouped so an emoji sequence (ZWJ family, flag, skin tone, keycap) stays whole."""
    units, i = [], 0
    while i < len(text):
        j = i+1
        if regional(ord(text[i])) and j < len(text) and regional(ord(text[j])):
            j += 1
        while j < len(text) and extends(ord(text[j])):
            # A joiner carries the next character into the same sequence.
            j += 2 if ord(text[j]) == 0x200D and j+1 < len(text) else 1
        units.append(text[i:j])
        i = j
    return units


def candidate(text):
    """Cheap test: plain Latin text never needs the emoji font."""
    return any(ord(char) >= 0x2000 or char in '©®' for char in text)


@lru_cache(maxsize=1)
def emoji_face():
    return ImageFont.truetype(str(EMOJI_FONT), STRIKE) if EMOJI_FONT.is_file() else None


@lru_cache(maxsize=4096)
def emoji_glyph(cluster):
    box = emoji_face().getbbox(cluster, anchor='ls')
    return box[3] > box[1]


def drawn(face, char):
    image = Image.new('L', (face.size*3, face.size*2))
    ImageDraw.Draw(image).text((0, 0), char, font=face, fill=255)
    return image.tobytes()


@lru_cache(maxsize=4096)
def lacks(face, char):
    """The face draws its missing-glyph box for this character."""
    return drawn(face, char) == drawn(face, MISSING)


def is_emoji(cluster, face):
    if emoji_face() is None or '\uFE0E' in cluster:
        return False
    codes = [ord(char) for char in cluster]
    marked = codes[0] >= 0x1F000 or any(extends(code) for code in codes[1:])
    if not marked and (codes[0] < 0x2000 and cluster not in '©®' or not lacks(face, cluster[0])):
        return False
    return emoji_glyph(cluster)


def runs(text, face):
    """(piece, is_emoji) in reading order; consecutive clusters of one kind share a run."""
    if not candidate(text):
        return [(text, False)]
    pieces = []
    for cluster in clusters(text):
        kind = is_emoji(cluster, face)
        if pieces and pieces[-1][1] == kind:
            pieces[-1] = (pieces[-1][0]+cluster, kind)
        else:
            pieces.append((cluster, kind))
    return pieces


def has_emoji(text, face):
    return any(emoji for _, emoji in runs(text, face))


def scale(face):
    return face.size/STRIKE


def emoji_length(piece, face):
    return emoji_face().getlength(piece)*scale(face)


def length(text, face):
    pieces = runs(text, face)
    if not any(emoji for _, emoji in pieces):
        return face.getlength(text)
    return sum(emoji_length(piece, face) if emoji else face.getlength(piece) for piece, emoji in pieces)


def bbox(text, face, anchor='la'):
    """Like ImageFont.getbbox for one line, emoji included."""
    if not has_emoji(text, face):
        return face.getbbox(text, anchor=anchor)
    spots, baseline = placed(text, face, (0, 0), anchor)
    boxes = []
    for piece, emoji, x in spots:
        if emoji:
            boxes.append((x, emoji_top(face, baseline), x+emoji_length(piece, face),
                          baseline+emoji_face().getmetrics()[1]*scale(face)))
        else:
            box = face.getbbox(piece, anchor='ls')
            boxes.append((x+box[0], baseline+box[1], x+box[2], baseline+box[3]))
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def origin(pieces, face, xy, anchor):
    """Left edge and baseline of the line for a Pillow anchor (horizontal: l m r; vertical: a t m s b d)."""
    total = sum(emoji_length(piece, face) if emoji else face.getlength(piece) for piece, emoji in pieces)
    ascent, descent = face.getmetrics()
    x = xy[0] - total*{'l': 0, 'm': .5, 'r': 1}[anchor[0]]
    vertical = anchor[1]
    if vertical == 'a':
        return x, xy[1]+ascent
    if vertical == 'm':
        return x, xy[1]+(ascent-descent)/2
    if vertical in 'tb':
        edges = []
        for piece, emoji in pieces:
            if emoji:
                edges.append(tuple(value*scale(face) for value in emoji_face().getmetrics()))
            else:
                box = face.getbbox(piece, anchor='ls')
                edges.append((-box[1], box[3]))
        if vertical == 't':
            return x, xy[1]+max(above for above, _ in edges)
        return x, xy[1]-max(below for _, below in edges)
    if vertical == 'd':
        return x, xy[1]-descent
    return x, xy[1]


@lru_cache(maxsize=1024)
def glyphs(piece, size):
    """The emoji run as an RGBA image scaled to a face of this size, its top at the emoji ascent."""
    face = emoji_face()
    ascent, descent = face.getmetrics()
    width = max(1, round(face.getlength(piece)))
    image = Image.new('RGBA', (width, ascent+descent))
    ImageDraw.Draw(image).text((0, ascent), piece, font=face, embedded_color=True, anchor='ls')
    factor = size/STRIKE
    return image.resize((max(1, round(width*factor)), max(1, round((ascent+descent)*factor))), Image.Resampling.LANCZOS)


def paste(image, layer, x, y):
    """Composite the layer at (x, y), clipped to the image; RGBA targets keep correct alpha."""
    x, y = round(x), round(y)
    if image.mode != 'RGBA':
        image.paste(layer, (x, y), layer)
        return
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(layer.width, image.width-x), min(layer.height, image.height-y)
    if right > left and bottom > top:
        image.alpha_composite(layer.crop((left, top, right, bottom)), (x+left, y+top))


def placed(value, face, xy, anchor='la'):
    """Each run of the line with the left edge it starts at, and the shared baseline."""
    pieces = runs(value, face)
    x, baseline = origin(pieces, face, xy, anchor)
    spots = []
    for piece, emoji in pieces:
        spots.append((piece, emoji, x))
        x += emoji_length(piece, face) if emoji else face.getlength(piece)
    return spots, baseline


def emoji_top(face, baseline):
    return baseline - emoji_face().getmetrics()[0]*scale(face)


def text(draw, xy, value, face, fill, anchor='la', **options):
    """ImageDraw.text for one line, with emoji in color. Options (stroke) apply to the text runs."""
    if not has_emoji(value, face):
        draw.text(xy, value, font=face, fill=fill, anchor=anchor, **options)
        return
    spots, baseline = placed(value, face, xy, anchor)
    for piece, emoji, x in spots:
        if emoji:
            paste(draw._image, glyphs(piece, face.size), x, emoji_top(face, baseline))
        else:
            draw.text((x, baseline), piece, font=face, fill=fill, anchor='ls', **options)
