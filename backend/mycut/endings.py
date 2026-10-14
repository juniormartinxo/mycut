"""Immutable local ending clips, shared by projects and appended after their scenes."""
import json
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .config import DATA, UPLOAD_LIMIT
from .media import digest


def video_info(path):
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-show_streams', '-show_format', '-of', 'json', str(path),
        ], capture_output=True, check=True, timeout=20)
        info = json.loads(result.stdout)
        video = next(s for s in info['streams'] if s['codec_type'] == 'video'
                     and not s.get('disposition', {}).get('attached_pic'))
        duration = float(info['format']['duration'])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        return {'duration': duration, 'width': int(video['width']), 'height': int(video['height']),
                'video_index': video['index'],
                'has_audio': any(s['codec_type'] == 'audio' for s in info['streams'])}
    except (subprocess.SubprocessError, ValueError, KeyError, StopIteration, TypeError):
        raise ValueError('Não foi possível ler o vídeo. Importe um MP4, MOV ou WebM válido.') from None


def get(ending_id):
    if not re.fullmatch(r'[a-f0-9]{32}', ending_id):
        raise ValueError('Selecione um vídeo de encerramento válido.')
    folder = DATA / 'endings' / ending_id
    if not (folder / 'record.json').is_file() or not (folder / 'clip.mp4').is_file():
        raise ValueError('O encerramento selecionado não está disponível. Importe o vídeo novamente.')
    return json.loads((folder / 'record.json').read_text())


def public(record):
    return {**record, 'url': f'/api/endings/{record["id"]}/video',
            'poster_url': f'/api/endings/{record["id"]}/poster'}


def catalog():
    records = [get(path.parent.name) for path in (DATA / 'endings').glob('*/record.json')
               if re.fullmatch(r'[a-f0-9]{32}', path.parent.name)]
    return [public(record) for record in sorted(records, key=lambda r: r['created_at'], reverse=True)]


def import_clip(stream, name):
    if Path(name).suffix.lower() not in ('.mp4', '.mov', '.webm'):
        raise ValueError('Use um vídeo MP4, MOV ou WebM de até 100 MB e 60 segundos.')
    root = DATA / 'endings'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.upload-', dir=root) as staging:
        folder = Path(staging)
        source = folder / 'source'
        size = 0
        with source.open('wb') as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > UPLOAD_LIMIT:
                    raise ValueError('O vídeo ultrapassa 100 MB. Exporte um arquivo menor.')
                output.write(chunk)
        source_hash = digest(source)
        ending_id = source_hash[:32]
        destination = root / ending_id
        if (destination / 'record.json').is_file():
            return public(get(ending_id))
        info = video_info(source)
        if not .2 <= info['duration'] <= 60:
            raise ValueError('O encerramento deve ter entre 0,2 e 60 segundos.')
        if not (0 < info['width'] <= 4096 and 0 < info['height'] <= 4096
                and info['width'] * info['height'] <= 3840 * 2160):
            raise ValueError('Use um vídeo com resolução de até 4K.')
        command = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe', '-i', str(source)]
        if not info['has_audio']:
            command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        command += [
            '-map', f'0:{info["video_index"]}', '-map', '0:a:0' if info['has_audio'] else '1:a:0',
            '-vf', f'scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                   f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={info["duration"]}',
            '-af', 'aresample=48000,apad', '-t', str(info['duration']),
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '4', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-movflags', '+faststart', str(folder / 'clip.mp4'),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True, timeout=180)
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(folder / 'clip.mp4'),
                            '-frames:v', '1', '-vf', 'scale=270:480', str(folder / 'poster.jpg')],
                           capture_output=True, check=True, timeout=30)
        except subprocess.SubprocessError:
            raise ValueError('Não foi possível preparar o encerramento. Exporte novamente como MP4 e tente importar.') from None
        record = {'id': ending_id, 'name': Path(name).name[:240], 'duration': video_info(folder / 'clip.mp4')['duration'],
                  'width': 1080, 'height': 1920, 'has_audio': info['has_audio'],
                  'sha256': digest(folder / 'clip.mp4'), 'source_sha256': source_hash, 'created_at': time.time()}
        (folder / 'record.json').write_text(json.dumps(record, ensure_ascii=False))
        source.unlink()
        # Publish the complete directory atomically; an identical concurrent upload is reusable.
        try:
            folder.rename(destination)
        except OSError:
            if not (destination / 'record.json').is_file():
                raise
        return public(get(ending_id))


def append_clip(target, record, width, height, fps, has_audio):
    source = DATA / 'endings' / record['id'] / 'clip.mp4'
    if not source.is_file() or digest(source) != record['sha256']:
        raise ValueError('O encerramento foi alterado no disco. Importe o vídeo novamente.')
    body_duration = video_info(target)['duration']
    duration = body_duration + record['duration']
    if duration > 180:
        raise ValueError('O Short com encerramento ultrapassa 3 minutos. Encurte as cenas ou desative o encerramento.')
    combined = target.with_name('with-ending.mp4')
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(target), '-i', str(source)]
    if not has_audio:
        command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    fit = f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},setpts=PTS-STARTPTS'
    audio = 'aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad'
    graph = (f'[0:v:0]{fit}[v0];[1:v:0]{fit}[v1];'
             f'[{"0:a:0" if has_audio else "2:a:0"}]{audio},atrim=duration={body_duration},asetpts=PTS-STARTPTS[a0];'
             f'[1:a:0]{audio},atrim=duration={record["duration"]},asetpts=PTS-STARTPTS[a1];'
             '[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]')
    command += ['-filter_complex', graph, '-map', '[v]', '-map', '[a]', '-t', str(duration),
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '4', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(combined)]
    try:
        subprocess.run(command, capture_output=True, check=True, timeout=300)
        actual_duration = video_info(combined)['duration']
        combined.replace(target)
    except subprocess.SubprocessError:
        combined.unlink(missing_ok=True)
        raise ValueError('Não foi possível juntar o encerramento ao Short. Tente renderizar novamente.') from None
    return {**record, 'start_seconds': body_duration, 'total_duration': actual_duration}
