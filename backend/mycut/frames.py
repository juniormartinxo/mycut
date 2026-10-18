"""Frames of a video resource, prepared for the composition engine (ADR 0019).

A `<video>` does not show exact frames, so the engine draws a video from JPEG frames at the project's fps, fitted
to the project's size. They are derived from the content in the acervo (ADR 0015) and shared by every project with
the same format; the preview asks for them in the background, the export prepares them before the first frame.
"""
import json
import shutil
import subprocess
import threading
from .config import DATA
from . import resources

FOLDER = DATA / 'derived' / 'frames'
_running = set()
_lock = threading.Lock()


def folder(digest, fps, width, height):
    return FOLDER / f'{digest}-{fps}fps-{width}x{height}'


def info(digest, fps, width, height):
    target = folder(digest, fps, width, height)
    done = target / 'frames.json'
    if done.exists():
        return {'state': 'ready', **json.loads(done.read_text())}
    if (target / 'failed').exists():
        return {'state': 'failed'}
    return {'state': 'preparing'}


def prepare(digest, fps, width, height):
    """Decode the whole video once into numbered frames (0.jpg, 1.jpg…); repeated calls reuse them."""
    target = folder(digest, fps, width, height)
    if (target / 'frames.json').exists():
        return info(digest, fps, width, height)
    work = target.with_name(target.name + '.partial')
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    scale = (f'fps={fps},scale=w={width}:h={height}:force_original_aspect_ratio=decrease:'
             'in_color_matrix=auto:out_color_matrix=bt709,format=yuvj420p')
    result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(resources.path(digest)), '-an', '-vf', scale,
                             '-q:v', '3', '-start_number', '0', str(work / '%d.jpg')], capture_output=True, text=True)
    count = len(list(work.glob('*.jpg')))
    if result.returncode or not count:
        shutil.rmtree(work, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
        (target / 'failed').write_text(result.stderr[-2000:])
        return {'state': 'failed'}
    (work / 'frames.json').write_text(json.dumps({'fps': fps, 'count': count}))
    shutil.rmtree(target, ignore_errors=True)
    work.rename(target)
    return info(digest, fps, width, height)


def request(digest, fps, width, height):
    """For the preview: start preparing in the background and answer at once with the current state."""
    current = info(digest, fps, width, height)
    key = (digest, fps, width, height)
    with _lock:
        if current['state'] != 'preparing' or key in _running:
            return current
        _running.add(key)

    def run():
        try:
            prepare(*key)
        finally:
            with _lock:
                _running.discard(key)
    threading.Thread(target=run, daemon=True, name=f'frames-{digest[:8]}').start()
    return current


def frame(digest, fps, width, height, index):
    return folder(digest, fps, width, height) / f'{index}.jpg'
