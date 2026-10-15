"""Project-owned video objects, normalized without audio or aspect-ratio changes."""
import json
import subprocess
import tempfile
from pathlib import Path
from . import endings, store
from .config import DATA, UPLOAD_LIMIT
from .media import data_path, digest


def public(project_id, record):
    return {k: v for k, v in record.items() if k not in ('path', 'poster_path')} | {
        'url': f'/api/projects/{project_id}/scene-videos/{record["id"]}/video',
        'poster_url': f'/api/projects/{project_id}/scene-videos/{record["id"]}/poster'}


def import_video(stream, name, project_id):
    if Path(name).suffix.lower() not in ('.mp4', '.mov', '.webm'):
        raise ValueError('Use MP4, MOV ou WebM, até 100 MB e 180 segundos.')
    root = DATA / 'projects' / project_id / 'scene-videos'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.upload-', dir=root) as staging:
        folder = Path(staging)
        source = folder / 'source'
        size = 0
        with source.open('wb') as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > UPLOAD_LIMIT:
                    raise ValueError('O vídeo ultrapassa 100 MB.')
                output.write(chunk)
        info = endings.video_info(source)
        if not .1 <= info['duration'] <= 180 or max(info['width'], info['height']) > 4096:
            raise ValueError('Use um vídeo de até 180 segundos e resolução de até 4K.')
        try:
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe',
                            '-i', str(source), '-map', f'0:{info["video_index"]}', '-an',
                            '-vf', "scale='min(1920,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,fps=30",
                            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-threads', '2',
                            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(folder / 'video.mp4')],
                           capture_output=True, check=True, timeout=300)
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(folder / 'video.mp4'),
                            '-frames:v', '1', '-vf', 'scale=480:480:force_original_aspect_ratio=decrease', str(folder / 'poster.png')],
                           capture_output=True, check=True, timeout=30)
        except subprocess.SubprocessError:
            raise ValueError('Não foi possível preparar o vídeo. Exporte como MP4 e tente novamente.') from None
        identity = store.uid()
        destination = root / identity
        normalized = endings.video_info(folder / 'video.mp4')
        record = {'id': identity, 'name': Path(name).name[:240],
                  'width': normalized['width'], 'height': normalized['height'],
                  'duration': normalized['duration'], 'sha256': digest(folder / 'video.mp4'),
                  'path': str((destination / 'video.mp4').relative_to(DATA)),
                  'poster_path': str((destination / 'poster.png').relative_to(DATA))}
        source.unlink()
        folder.rename(destination)
        return record


class VideoFrames:
    """Bounded-memory sequential loop. One decoder per visible video object."""
    def __init__(self, record, size, fps, fit='contain', zoom=1, crop_x=50, crop_y=50):
        source = data_path(record['path'])
        if digest(source) != record['sha256']:
            raise ValueError('O vídeo mudou no disco. Importe-o novamente.')
        self.size, self.fps = size, fps
        self.index, self.image = -1, None
        # Crop before scaling: an extreme source aspect ratio must not create
        # a huge raw intermediate frame for a small cover object.
        crop = (f"crop='max(1,min(iw,ih*{size[0]}/{size[1]})/{zoom})':"
                f"'max(1,min(ih,iw*{size[1]}/{size[0]})/{zoom})':"
                f"'(iw-ow)*{crop_x}/100':'(ih-oh)*{crop_y}/100':exact=1,") if fit == 'cover' else ''
        self.process = subprocess.Popen([
            'ffmpeg', '-v', 'error', '-nostdin', '-threads', '1', '-stream_loop', '-1',
            '-protocol_whitelist', 'file,pipe', '-i', str(source), '-an',
            '-vf', f'{crop}scale={size[0]}:{size[1]},fps={fps}', '-threads', '1',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def frame(self, elapsed):
        from PIL import Image
        desired = max(0, int(elapsed * self.fps + 1e-5))
        while self.index < desired:
            raw = self.process.stdout.read(self.size[0] * self.size[1] * 3)
            if len(raw) != self.size[0] * self.size[1] * 3:
                raise ValueError('O decodificador de vídeo foi interrompido.')
            self.image = Image.frombytes('RGB', self.size, raw)
            self.index += 1
        return self.image

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()
