"""Align a narration transcript to its script; local Whisper only, no audio upload."""
import difflib
import json
import sys
import unicodedata
from pathlib import Path


def use_cached_whisper():
    """Prefer installed packages; reuse compatible cached wheels if needed."""
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except ModuleNotFoundError:
        from email.parser import Parser
        from packaging.tags import parse_tag, sys_tags
        from packaging.version import Version
        archive = Path.home() / '.cache/uv/archive-v0'
        allowed, packages = set(sys_tags()), {}
        for metadata in archive.glob('*/*.dist-info/METADATA'):
            wheel = metadata.with_name('WHEEL')
            if not wheel.is_file():
                continue
            tags = set()
            for line in wheel.read_text().splitlines():
                if line.startswith('Tag: '):
                    tags |= parse_tag(line[5:])
            if not tags & allowed:
                continue
            info = Parser().parsestr(metadata.read_text())
            name = info['Name'].lower().replace('_', '-')
            version = Version(info['Version'])
            if name not in packages or version > packages[name][0]:
                packages[name] = (version, metadata.parent.parent)
        sys.path.extend(str(item[1]) for item in packages.values())
        from faster_whisper import WhisperModel
        return WhisperModel


def normalized(word):
    word = unicodedata.normalize('NFKD', word.lower())
    return ''.join(c for c in word if c.isalnum() and not unicodedata.combining(c))


def make_timing(script, transcript, duration, folder):
    paragraphs = script.strip().split('\n\n')
    original = []
    starts = []
    for index, paragraph in enumerate(paragraphs):
        starts.append(len(original))
        # Preserve the source script's pronunciation aid, but show the brand spelling in captions.
        original.extend({'text': word.replace('Cláude', 'Claude'), 'scene': index} for word in paragraph.split())
    actual = [word for segment in transcript['segments'] for word in segment['words'] if normalized(word['word'])]
    expected_words = [normalized(word['text']) for word in original]
    actual_words = [normalized(word['word']) for word in actual]
    matcher = difflib.SequenceMatcher(a=expected_words, b=actual_words, autojunk=False)
    anchors = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            word = actual[block.b+offset]
            anchors[block.a+offset] = (word['start'], word['end'])
    review = {'word_similarity': matcher.ratio(), 'exactly_aligned_words': len(anchors),
              'script_words': len(original), 'transcript_words': len(actual),
              'differences': [{'operation': op, 'script': ' '.join(expected_words[i:j]),
                               'transcript': ' '.join(actual_words[k:l])}
                              for op,i,j,k,l in matcher.get_opcodes() if op != 'equal'],
              'note': 'ASR differences may be pronunciation errors or recognition errors; human review is still required.'}
    if folder is not None:
        (folder/'alignment-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
    if matcher.ratio() < .90:
        raise ValueError('A transcrição diverge do roteiro. Consulte alignment-review.json antes de renderizar.')
    for i, word in enumerate(original):
        if i in anchors:
            word['start'], word['end'] = anchors[i]
        else:
            left = max((n for n in anchors if n < i), default=-1)
            right = min((n for n in anchors if n > i), default=len(original))
            begin = anchors[left][1] if left >= 0 else 0
            finish = anchors[right][0] if right < len(original) else duration
            portion = max(0, finish-begin)/(right-left-1)
            word['start'] = begin+(i-left-1)*portion
            word['end'] = begin+(i-left)*portion
            word['interpolated'] = True
    scenes = []
    for index, first in enumerate(starts):
        scene_start = 0 if index == 0 else original[first]['start']
        scene_end = original[starts[index+1]]['start'] if index+1<len(starts) else duration
        if scene_end <= scene_start:
            raise ValueError('Não foi possível alinhar os limites das cenas.')
        scenes.append({'index': index, 'start': scene_start, 'end': scene_end})
    captions = []
    for index in range(len(paragraphs)):
        scene_caption_start = len(captions)
        words = [w for w in original if w['scene'] == index]
        chunk = []
        for word in words:
            if chunk and (len(chunk) >= 6 or len(' '.join(w['text'] for w in chunk+[word])) > 49):
                captions.append({'start':chunk[0]['start'], 'end':chunk[-1]['end'], 'text':' '.join(w['text'] for w in chunk)})
                chunk = []
            chunk.append(word)
        if chunk:
            captions.append({'start':chunk[0]['start'], 'end':chunk[-1]['end'], 'text':' '.join(w['text'] for w in chunk)})
        # Keep a short sentence ending (e.g. "café?") with the preceding caption when it fits.
        if len(captions) - scene_caption_start >= 2:
            previous, last = captions[-2:]
            combined = previous['text'] + ' ' + last['text']
            if len(last['text'].split()) <= 2 and len(combined) <= 49:
                previous.update(text=combined, end=last['end'])
                captions.pop()
    for i, caption in enumerate(captions):
        following = captions[i+1]['start'] if i+1<len(captions) else duration
        caption['end'] = min(following, duration, caption['end']+.10)
        if caption['end'] <= caption['start']:
            raise ValueError('Legenda sem duração; reveja o alinhamento.')
    return {'duration_seconds':duration, 'scenes':scenes, 'captions':captions,
            'words':[{'scene':w['scene'], 'start':w['start'], 'end':w['end']} for w in original],
            'timing_source':'Whisper word timestamps; missing words interpolated', 'alignment':review}
