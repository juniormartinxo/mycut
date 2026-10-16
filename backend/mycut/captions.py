"""Captions of a Short livre (ADR 0005): a few words at a time, keywords in the accent color, in the safe area.

The preview and the MP4 time and draw them with the same code, from the scene's clock."""
import math
from PIL import ImageDraw
from . import google_fonts, flow
from .alignment import normalized

# YouTube draws its buttons over the right strip and its texts over the bottom 15% of a Short.
SAFE_RIGHT = 930
SAFE_BOTTOM = round(1920 * .85)
LEFT = 60
# Vertical center of the caption for each position the director can choose.
CENTERS = {'top': 430, 'middle': 960, 'bottom': 1450}
SENTENCE_END = ('.', '!', '?', '…')
TAIL = .1


def groups(words, size, breaks):
    """Index ranges of 2 to `size` words: a pause always cuts, a sentence end cuts when it leaves 2 words or more,
    and each phrase is spread evenly so no group is left with a single word when it can be avoided."""
    phrases, current = [], []
    for index, word in enumerate(words):
        current.append(index)
        if index in breaks or index == len(words)-1:
            phrases.append((current, True))
            current = []
        elif word.endswith(SENTENCE_END):
            phrases.append((current, False))
            current = []
    merged = []
    for phrase, hard in phrases:
        # A one-word sentence joins its neighbour in the same passage between pauses.
        if merged and not merged[-1][1] and (len(phrase) == 1 or len(merged[-1][0]) == 1):
            merged[-1] = (merged[-1][0] + phrase, hard)
        else:
            merged.append((phrase, hard))
    result = []
    for phrase, _ in merged:
        count = math.ceil(len(phrase) / size)
        base, extra = divmod(len(phrase), count)
        start = 0
        for number in range(count):
            length = base + (number < extra)
            result.append((phrase[start], phrase[start+length-1]))
            start += length
    return result


def timed(scene, clock, style):
    """The captions of one scene in scene time, from its narration and clock."""
    words = scene.get('narration', '').split()
    starts, ends = clock['words'], clock.get('ends') or []
    if not words or len(starts) < len(words):
        return []
    duration = clock['duration']
    result = []
    for first, last in groups(words, style['words'], set(flow.pause_points(scene))):
        end = ends[last] if last < len(ends) else (starts[last+1] if last+1 < len(starts) else duration)
        result.append({'start': starts[first], 'end': end + TAIL, 'words': words[first:last+1]})
    for current, following in zip(result, result[1:]):
        current['end'] = min(current['end'], following['start'])
    if result:
        result[-1]['end'] = min(result[-1]['end'], duration)
    return result


def active(captions, elapsed):
    """The caption shown at this scene time; without a time, the first one, as in the static composition."""
    if elapsed is None:
        return captions[0] if captions else None
    return next((c for c in captions if c['start'] <= elapsed < c['end']), None)


def draw(image, caption, style):
    """Large words centered in the safe area, keywords in the accent, outlined in the background color."""
    setting = style['captions']
    keywords = {normalized(part) for keyword in setting['keywords'] for part in keyword.split()} - {''}
    width = SAFE_RIGHT - LEFT
    pen = ImageDraw.Draw(image)
    for size in range(round(setting['font_size']), 23, -2):
        face = google_fonts.face(style.get('google_font') or 'Roboto', size)
        space = pen.textlength(' ', font=face)
        lines, line = [], []
        for word in caption['words']:
            if line and sum(pen.textlength(w, font=face) for w in line+[word]) + space*len(line) > width:
                lines.append(line)
                line = []
            line.append(word)
        lines.append(line)
        if len(lines) <= 2 and all(pen.textlength(w, font=face) <= width for w in caption['words']):
            break
    stroke = max(2, round(size * .09))
    ascent, descent = face.getmetrics()
    leading = max(size * 1.2, ascent + descent)
    top = min(CENTERS[setting['position']] - len(lines)*leading/2, SAFE_BOTTOM - stroke - len(lines)*leading)
    for number, line in enumerate(lines):
        x = LEFT + (width - sum(pen.textlength(w, font=face) for w in line) - space*(len(line)-1)) / 2
        for word in line:
            color = style['accent'] if normalized(word) in keywords else style['text_color']
            # Every word of a line shares its baseline.
            pen.text((x, top + number*leading + ascent), word, font=face, fill=color, anchor='ls',
                     stroke_width=stroke, stroke_fill=style['background'])
            x += pen.textlength(word, font=face) + space
