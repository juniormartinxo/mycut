"""Export of a frozen revision of a horizontal project as MP4 H.264/AAC 48 kHz (Q34, Q47, ADR 0014, ADR 0019).

Asking for an export freezes the document as it is at that revision: editing goes on, and a change made during the
render never reaches the file, which carries the revision in its name. Exports stay until the author removes them.

The worker renders each export in its own process: a headless Chromium opens the engine's export page (the same
drawing and mixing code as the editor's preview), each frame is captured in order into FFmpeg, and the sound is the
preview's WebAudio graph rendered offline.
"""
import base64
import json
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from pydantic import Field
from . import editing, frames, resources, store
from .config import DATA, ROOT, configure

FOLDER = DATA / 'exports'
WEB = Path(os.environ.get('MYCUT_WEB_DIR', ROOT / 'web/dist'))
RATE = 48_000
# Pages drawing frames side by side; four already fill the 8 logical CPUs of the target machine (MYC-11).
TABS = int(os.environ.get('MYCUT_EXPORT_TABS', '3'))
AUDIO_CHUNK_S = 20
ENCODERS = {
    'h264_nvenc': ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '20', '-b:v', '0', '-profile:v', 'high'],
    'libx264': ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-profile:v', 'high'],
}
COLOR = ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709',
         '-color_primaries', 'bt709', '-color_trc', 'bt709']


class ExportRequest(editing.Strict):
    revision: int = Field(ge=1)
    author: editing.Author


class RemoveRequest(editing.Strict):
    author: editing.Author


def slug(title):
    plain = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', plain).strip('-')[:60].strip('-') or 'video'


def summary(row):
    document = json.loads(row['document'])
    return {'id': row['id'], 'project_id': row['project_id'], 'revision': row['revision'], 'state': row['state'],
            'progress': row['progress'], 'message': row['message'], 'name': row['name'], 'size': row['size'],
            'author': json.loads(row['author']), 'format': document['format'], 'duration_ms': document['duration_ms'],
            'created_at': row['created_at'], 'updated_at': row['updated_at']}


def create(project_id, body: ExportRequest):
    """Freeze the revision the author is looking at; a newer revision means the request was made on an old view."""
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM edit_projects WHERE id=?', (project_id,)).fetchone()
        document = editing.row_document(row)
        if document['revision'] != body.revision:
            raise store.Conflict('O projeto mudou depois que você o abriu. Atualize-o antes de exportar.')
        frozen = editing.present(document, row)
        export_id, now = store.uid(), time.time()
        name = f'{slug(document["title"])}-r{document["revision"]}.mp4'
        db.execute('INSERT INTO edit_exports VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (export_id, project_id, document['revision'], 'queued', 0, 'Aguardando o worker', name, None,
                    editing.dump(body.author.model_dump()), editing.dump(frozen), now, now))
        return summary(db.execute('SELECT * FROM edit_exports WHERE id=?', (export_id,)).fetchone())


def listing(project_id):
    with store.connect() as db:
        editing.load(db, project_id)
        rows = db.execute('SELECT * FROM edit_exports WHERE project_id=? ORDER BY created_at DESC', (project_id,)).fetchall()
    return {'exports': [summary(row) for row in rows]}


def find(db, project_id, export_id):
    row = db.execute('SELECT * FROM edit_exports WHERE id=? AND project_id=?', (export_id, project_id)).fetchone()
    if row is None:
        raise store.Missing('Exportação não encontrada.')
    return row


def output(row):
    return FOLDER / row['project_id'] / row['id'] / row['name']


def file(project_id, export_id):
    with store.connect() as db:
        row = find(db, project_id, export_id)
    if row['state'] != 'done' or not output(row).exists():
        raise store.Missing('A exportação ainda não tem arquivo.')
    return output(row), row['name']


def remove(project_id, export_id):
    """Only by the author's choice (Q47): a running export stops, its file goes with it, and so do the media that only
    this export still held after a cleanup of the history (ADR 0015)."""
    with resources.LOCK:
        with store.connect() as db:
            row = find(db, project_id, export_id)
            db.execute('DELETE FROM edit_exports WHERE id=?', (export_id,))
            held = {r['hash'] for r in json.loads(row['document'])['resources']} - set(editing.references(db))
            paths = resources.forget(db, sorted(held))[1]
        for path in paths:
            path.unlink(missing_ok=True)
    shutil.rmtree(output(row).parent, ignore_errors=True)
    return listing(project_id)


def update(export_id, **values):
    with store.connect() as db:
        sets = ', '.join(f'{name}=?' for name in values)
        db.execute(f"UPDATE edit_exports SET {sets}, updated_at=? WHERE id=? AND state='running'",
                   (*values.values(), time.time(), export_id))


def still_running(export_id):
    with store.connect() as db:
        row = db.execute('SELECT state FROM edit_exports WHERE id=?', (export_id,)).fetchone()
    return row is not None and row['state'] == 'running'


# ---------- Worker: one export at a time, each in a process group that removal can stop ----------

def claim():
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM edit_exports WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
        if row is None:
            return None
        db.execute("UPDATE edit_exports SET state='running', message='Preparando a exportação', updated_at=? WHERE id=?",
                   (time.time(), row['id']))
        return row


def recover():
    with store.connect() as db:
        db.execute("UPDATE edit_exports SET state='failed', message='Worker reiniciado durante a exportação. Exporte de novo.', "
                   "updated_at=? WHERE state='running'", (time.time(),))


def stop(process):
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def run_once():
    row = claim()
    if row is None:
        return False
    folder = output(row).parent
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'export.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, '-m', 'mycut.exporting', row['id']], stdout=log, stderr=log,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                store.heartbeat()
                if not still_running(row['id']):
                    stop(process)
                    break
                time.sleep(.5)
        except BaseException:
            if process.poll() is None:
                stop(process)
            update(row['id'], state='failed', message='Exportação interrompida. Exporte de novo.')
            raise
    if still_running(row['id']):
        if process.returncode == 0 and output(row).exists():
            update(row['id'], state='done', progress=100, message='Pronta', size=output(row).stat().st_size)
        else:
            lines = (folder / 'export.log').read_text(errors='replace').strip().splitlines()
            update(row['id'], state='failed', message=(lines[-1] if lines else 'Falha na exportação.')[:600])
    return True


def lane():
    while True:
        store.heartbeat()
        if not run_once():
            time.sleep(1)


# ---------- The render itself, in the export's process ----------

@lru_cache(maxsize=1)
def encoder():
    """NVENC when the GPU really encodes here (MYC-11), otherwise x264; MYCUT_VIDEO_ENCODER forces one."""
    chosen = os.environ.get('MYCUT_VIDEO_ENCODER')
    if chosen:
        return chosen
    probe = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
                            *ENCODERS['h264_nvenc'], '-f', 'null', '-'], capture_output=True)
    return 'h264_nvenc' if probe.returncode == 0 else 'libx264'


def serve(snapshot):
    """A server of its own on the loopback: the export page, the frozen revision's media and the video frames."""
    if not (WEB / 'render.html').exists():
        raise RuntimeError('Compile a interface antes de exportar: cd web && npm run build')
    width, height, fps = (snapshot['format'][key] for key in ('width', 'height', 'fps'))
    media = {r['hash']: r['media_type'] for r in snapshot['resources']}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = self.path.split('?')[0]
            parts = path.strip('/').split('/')
            target, kind = None, None
            if parts[:2] == ['media', 'resources'] and len(parts) == 3 and parts[2] in media:
                target, kind = resources.path(parts[2]), media[parts[2]]
            elif parts[:2] == ['media', 'frames'] and len(parts) == 3 and parts[2] in media:
                body = json.dumps(frames.info(parts[2], fps, width, height)).encode()
                return self.answer(200, 'application/json', body)
            elif parts[:2] == ['media', 'frames'] and len(parts) == 4 and parts[2] in media and re.fullmatch(r'\d+\.jpg', parts[3]):
                target, kind = frames.frame(parts[2], fps, width, height, int(parts[3][:-4])), 'image/jpeg'
            elif parts[0] != 'media':
                candidate = (WEB / path.lstrip('/')).resolve()
                if candidate.is_relative_to(WEB.resolve()) and candidate.is_file():
                    target, kind = candidate, mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
            if target is None or not target.exists():
                return self.answer(404, 'text/plain', b'')
            self.answer(200, kind, target.read_bytes())

        def answer(self, status, kind, body):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name='export-server').start()
    return server


def videos(snapshot):
    kinds = {track['id']: track['kind'] for track in snapshot['tracks']}
    used = {item['resource'] for item in snapshot['items'] if kinds[item['track_id']] == 'visual'}
    return [r['hash'] for r in snapshot['resources'] if r['hash'] in used and r['media_type'].startswith('video/')]


def render(export_id):
    from .chromium import Browser
    with store.connect() as db:
        row = db.execute('SELECT * FROM edit_exports WHERE id=?', (export_id,)).fetchone()
    snapshot = json.loads(row['document'])
    width, height, fps = (snapshot['format'][key] for key in ('width', 'height', 'fps'))
    target = output(row)
    work = target.parent / '.work'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    for digest in videos(snapshot):
        update(export_id, message='Preparando os quadros dos vídeos')
        if frames.prepare(digest, fps, width, height)['state'] != 'ready':
            raise RuntimeError('Não foi possível ler um dos vídeos do projeto.')
    server = serve(snapshot)
    browser = Browser()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/render.html'
        pages = [browser.page(url, width, height) for _ in range(TABS)]
        loaded = [page.call('(montage, base) => motor.load(montage, base)', snapshot, '/media') for page in pages]
        total = loaded[0]['frames']
        video = work / 'video.mp4'
        name = encoder()
        ffmpeg = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg',
                                   '-framerate', str(fps), '-i', '-', *COLOR, *ENCODERS[name], '-r', str(fps), str(video)],
                                  stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        update(export_id, message=f'Desenhando {total} quadros')
        write_frames(export_id, pages, total, fps, ffmpeg)
        ffmpeg.stdin.close()
        if ffmpeg.wait():
            raise RuntimeError(f'O FFmpeg falhou ao codificar o vídeo: {ffmpeg.stderr.read().decode(errors="replace")[-400:]}')
        update(export_id, message='Mixando o som')
        mix = work / 'mix.f32'
        # The sound lasts exactly as long as the frames, counted in samples from the frame count.
        samples = round(total * RATE / fps)
        with mix.open('wb') as out:
            for start in range(0, samples, AUDIO_CHUNK_S * RATE):
                length = min(AUDIO_CHUNK_S * RATE, samples - start)
                out.write(base64.b64decode(pages[0].call('(from, length) => motor.mix(from, length)', start, length)))
    finally:
        browser.close()
        server.shutdown()
    update(export_id, message='Juntando imagem e som')
    title = f'{snapshot["title"]} · revisão {snapshot["revision"]}'
    partial = target.with_name(target.name + '.partial.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(video), '-f', 'f32le', '-ar', str(RATE), '-ac', '2',
                    '-i', str(mix), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-ar', str(RATE), '-metadata', f'title={title}', '-movflags', '+faststart', str(partial)], check=True)
    partial.rename(target)
    shutil.rmtree(work, ignore_errors=True)


def write_frames(export_id, pages, total, fps, ffmpeg):
    """Each page draws every TABS-th frame; the frames reach FFmpeg in order, never more than a few ahead."""
    ready, condition, failure = {}, threading.Condition(), []
    written = [0]

    def draw(offset, page):
        try:
            for index in range(offset, total, len(pages)):
                with condition:
                    condition.wait_for(lambda: index - written[0] < len(pages) * 4 or failure)
                    if failure:
                        return
                page.call('ms => motor.seek(ms)', index * 1000 / fps)
                picture = page.capture()
                with condition:
                    ready[index] = picture
                    condition.notify_all()
        except BaseException as error:
            with condition:
                failure.append(error)
                condition.notify_all()

    threads = [threading.Thread(target=draw, args=(k, page), daemon=True) for k, page in enumerate(pages)]
    for thread in threads:
        thread.start()
    for index in range(total):
        with condition:
            condition.wait_for(lambda: index in ready or failure)
            if failure:
                raise failure[0]
            picture = ready.pop(index)
        ffmpeg.stdin.write(picture)
        with condition:
            written[0] = index + 1
            condition.notify_all()
        if index % 30 == 0:
            update(export_id, progress=min(95, round(95 * index / total)))
    for thread in threads:
        thread.join()


def main():
    configure()
    store.initialize()
    render(sys.argv[1])


if __name__ == '__main__':
    main()
