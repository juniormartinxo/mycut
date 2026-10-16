"""A production snapshot becomes a versioned video, using the existing drawing/alignment tools."""
import json
import math
import os
import shutil
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw
from . import store
from . import visuals, endings, block_render, graphics, alignment, flow
from .config import DATA, MODEL, MODEL_DIR
from .media import data_path, digest


def wrapped(draw, value, y, size=68, color='#29231f', width=890, gap=1.22, centered=False):
    """Wrap and shrink bounded copy rather than cropping text at the video edge."""
    while True:
        face = graphics.font(size, True)
        lines, line = [], ''
        for word in value.split():
            if draw.textlength(word, font=face) > width and size > 20:
                lines = [''] * 10
                break
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=face) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if len(lines) <= 3 or size <= 20:
            break
        size -= 2
    if centered:
        y -= len(lines) * size * gap / 2
    for index, line in enumerate(lines):
        draw.text((540, y + index * size * gap), line, font=face, fill=color, anchor='mt')
    return y + len(lines) * size * gap


def flow_centers(count):
    if count == 1:
        return [1080]
    start, end = (740, 1370) if count == 4 else (810, 1350)
    return [start + i * (end-start)/(count-1) for i in range(count)]


def scene_image(scene, accent):
    image = Image.new('RGB', (1080, 1920), '#f7f3eb')
    draw = ImageDraw.Draw(image)
    draw.line((88, 170, 992, 170), fill='#d6cbbb', width=2)
    graphics.text(draw, (88, 115), 'MYCUT', 29, '#29231f', True, anchor='lm')
    wrapped(draw, scene['title'].upper(), 275, color=accent)
    items = [i.strip() for i in scene['items'] if i.strip()]
    if scene['layout'] == 'flow':
        items = items or [scene['title']]
        total = len(items)
        for i, label in enumerate(items):
            centers = flow_centers(total)
            cy = centers[i]
            draw.rounded_rectangle((138, cy-82, 942, cy+82), radius=24, fill='#eee4d6', outline='#ccbaa5', width=2)
            wrapped(draw, label, cy, 40, '#29231f', width=730, gap=1.1, centered=True)
            if i < total-1:
                graphics.arrow(draw, (540, cy+92), (540, centers[i+1]-92), accent, 5)
    elif scene['layout'] == 'comparison':
        items = (items + ['Primeira opção', 'Segunda opção'])[:2]
        for i, label in enumerate(items):
            y = 745 + i*330
            draw.rounded_rectangle((96, y, 984, y+270), radius=28, fill='#eee4d6')
            wrapped(draw, label, y+75, 47, accent if i else '#29231f', width=790)
    else:
        draw.ellipse((414, 710, 666, 962), fill=accent)
        draw.line((470, 833, 518, 879, 616, 778), fill='#fffaf2', width=16, joint='curve')
        wrapped(draw, ' '.join(items) if items else scene['title'], 1090, 51, width=850)
    return image


def estimated_timing(project):
    scenes, captions, spoken, current = [], [], [], 0.0
    for i, scene in enumerate(project['scenes']):
        words = scene['narration'].split()
        duration = max(2.0, len(words)/2.7 + .3)
        scenes.append({'index': i, 'start': current, 'end': current+duration})
        spoken += [{'scene': i, 'start': current+duration*k/len(words), 'end': current+duration*(k+1)/len(words)}
                   for k in range(len(words))]
        chunks, chunk = [], []
        for word in words:
            if chunk and (len(chunk) >= 6 or len(' '.join(chunk+[word])) > 42):
                chunks.append(chunk)
                chunk = []
            chunk.append(word)
        if chunk:
            chunks.append(chunk)
        offset = 0
        for chunk in chunks:
            start = current + duration*offset/len(words)
            offset += len(chunk)
            captions.append({'start': start, 'end': current+duration*offset/len(words), 'text': ' '.join(chunk)})
        current += duration
    return {'duration_seconds': current, 'scenes': scenes, 'captions': captions, 'words': spoken,
            'timing_source': 'estimated_preview_only'}


def transcribe(audio, folder, job):
    project = job['snapshot']
    record = project['audio']
    if record.get('alignment'):
        cached = json.loads(data_path(record['alignment']).read_text())
        if cached.get('audio_sha256') == digest(audio):
            return cached
    store.progress(job['id'], 12, 'Transcrevendo e alinhando a narração')
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    model_type = alignment.use_cached_whisper()
    try:
        model = model_type(MODEL_DIR or MODEL, device='cpu', compute_type='int8', cpu_threads=6,
                           local_files_only=True)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValueError('Modelo de alinhamento indisponível. Execute a preparação do Whisper descrita no README e tente novamente.') from exc
    signal = subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(audio), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], timeout=120)
    segments, info = model.transcribe(np.frombuffer(signal, dtype=np.float32).copy(), language='pt', beam_size=5,
                                      vad_filter=True, word_timestamps=True, condition_on_previous_text=False)
    result = {'audio_sha256': digest(audio), 'segments': []}
    for segment in segments:
        result['segments'].append({'start': segment.start, 'end': segment.end, 'text': segment.text,
                                  'words': [{'word': w.word.strip(), 'start': w.start, 'end': w.end} for w in segment.words or []]})
    return result


def make_video(job):
    project, job_id = job['snapshot'], job['id']
    block_render.validate_project(project)
    ending = endings.get(project['ending_id']) if project.get('ending_id') else None
    folder = DATA / 'projects' / project['id'] / 'renders' / job_id
    folder.mkdir(parents=True, exist_ok=True)
    script = store.script(project)
    (folder / 'roteiro.txt').write_text(script+'\n')
    audio = None
    if project.get('audio'):
        record = project['audio']
        source = data_path(record['path'])
        if digest(source) != record['sha256']:
            raise ValueError('A narração foi alterada no disco. Importe-a novamente.')
        audio = folder / 'narracao.wav'
        store.progress(job_id, 5, 'Preparando o áudio')
        if record.get('normalized'):
            shutil.copy2(source, audio)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe',
                            '-i', str(source), '-vn', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100',
                            '-c:a', 'pcm_s24le', str(audio)], check=True, timeout=180)
        transcript = transcribe(audio, folder, job)
        (folder / 'alignment.json').write_text(json.dumps(transcript, ensure_ascii=False))
        duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(audio)]))
        timing = alignment.make_timing(script, transcript, duration, folder)
    else:
        timing = estimated_timing(project)
    if not 1 <= timing['duration_seconds'] <= 180:
        raise ValueError('A duração deve ficar entre 1 e 180 segundos. Encurte o roteiro.')
    if ending and timing['duration_seconds'] + ending['duration'] > 180:
        raise ValueError('O Short com encerramento ultrapassa 3 minutos. Encurte as cenas ou desative o encerramento.')
    (folder / 'timing.json').write_text(json.dumps(timing, ensure_ascii=False, indent=2))
    graphics.write_subtitles(timing, folder)
    frames = [scene_image(scene, project['accent']) for scene in project['scenes']]
    compositions = None
    if project.get('visual_style') or any(s.get('blocks') is not None for s in project['scenes']):
        compositions = [block_render.BlockComposition(scene, project, 540 if job['mode'] == 'preview' else 1080,
                                                       24 if job['mode'] == 'preview' else 30,
                                                       flow.clock_from_timing(timing, index))
                        if scene.get('blocks') is not None else
                        visuals.Composition(scene, project, 540 if job['mode'] == 'preview' else 1080,
                                            visuals.scene_asset(scene, project)) if project.get('visual_style') else None
                        for index, scene in enumerate(project['scenes'])]
    if project.get('cover'):
        source_cover = data_path(project['cover']['path'])
        concept = None
        if project.get('visual_style'):
            with Image.open(source_cover) as cover:
                provenance = json.loads(cover.info.get('mycut_provenance', '{}'))
                if provenance.get('generator') in ('MyCut geometry renderer', 'MyCut format renderer'):
                    concept = provenance.get('agent_concept')
        if concept:
            visuals.save_png(visuals.cover_frame(project, concept), folder / 'capa.png', project, agent_concept=concept)
        else:
            shutil.copy2(source_cover, folder / 'capa.png')
    else:
        if compositions and compositions[0]:
            visuals.save_png(compositions[0].frame().resize((1080, 1920)), folder / 'capa.png', project,
                             scene=project['scenes'][0])
        else:
            frames[0].save(folder / 'capa.png')
    scale, fps = (0.5, 24) if job['mode'] == 'preview' else (1, 30)
    width, height = int(1080*scale), int(1920*scale)
    frames = [f.resize((width,height), Image.Resampling.LANCZOS) for f in frames]
    target = folder / 'short.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size',
           f'{width}x{height}', '-framerate', str(fps), '-i', 'pipe:0']
    if audio:
        cmd += ['-i', str(audio), '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest']
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-threads', '4', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
    duration = timing['duration_seconds']
    count = math.ceil(duration*fps)
    scene_index, caption_index = 0, 0
    with (folder / 'ffmpeg.log').open('wb') as log:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            for number in range(count):
                now = number/fps
                while scene_index+1 < len(timing['scenes']) and now >= timing['scenes'][scene_index+1]['start']:
                    # A finished scene releases its video decoders before the next one opens its own.
                    if compositions and isinstance(compositions[scene_index], block_render.BlockComposition):
                        compositions[scene_index].close()
                    scene_index += 1
                while caption_index+1 < len(timing['captions']) and now >= timing['captions'][caption_index]['end']:
                    caption_index += 1
                frame = frames[scene_index].copy()
                draw = ImageDraw.Draw(frame)
                # Emphasize each idea in order over the narrated scene's duration.
                scene = project['scenes'][scene_index]
                bounds = timing['scenes'][scene_index]
                phase = min(.999, max(0, (now-bounds['start']) / max(.1, bounds['end']-bounds['start'])))
                if compositions and compositions[scene_index]:
                    caption = timing['captions'][caption_index] if timing['captions'] else {'text': '', 'start': 0, 'end': 0}
                    text = caption['text'] if caption['start'] <= now < caption['end'] else ''
                    frame = compositions[scene_index].frame(now-bounds['start'], phase, text)
                    if not audio:
                        draw = ImageDraw.Draw(frame)
                        draw.text((width/2, 1840*scale), 'PRÉVIA SEM NARRAÇÃO',
                                  font=visuals.font('sans', round(24*scale)), fill=visuals.resolve(project)['text_color'], anchor='mm')
                    process.stdin.write(frame.tobytes())
                    if number % (fps*2) == 0:
                        store.progress(job_id, 25+int(70*number/count), f'Renderizando {now:.0f} de {duration:.0f} segundos')
                    continue
                labels = [item for item in scene['items'] if item.strip()]
                if scene['layout'] == 'flow':
                    centers = flow_centers(len(labels) or 1)
                    cy = centers[int(phase*len(centers))]
                    box = (138, cy-82, 942, cy+82)
                elif scene['layout'] == 'comparison':
                    y = 745 + int(phase*2)*330
                    box = (96, y, 984, y+270)
                else:
                    box = None
                if box:
                    draw.rounded_rectangle(tuple(v*scale for v in box), radius=round(24*scale),
                                           outline=project['accent'], width=max(2, round(4*scale)))
                caption = timing['captions'][caption_index]
                if caption['start'] <= now < caption['end']:
                    graphics.add_caption(frame, caption['text'], scale)
                if not audio:
                    draw.text((width/2,1840*scale), 'PRÉVIA SEM NARRAÇÃO', font=graphics.font(round(24*scale)), fill='#68584c', anchor='mm')
                process.stdin.write(frame.tobytes())
                if number % (fps*2) == 0:
                    store.progress(job_id, 25+int(70*number/count), f'Renderizando {now:.0f} de {duration:.0f} segundos')
            process.stdin.close()
            if process.wait():
                raise ValueError('O FFmpeg não concluiu a exportação. Consulte o log desta produção.')
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            for composition in compositions or []:
                if isinstance(composition, block_render.BlockComposition):
                    composition.close()
    if ending:
        store.progress(job_id, 96, 'Acrescentando o vídeo de encerramento')
        ending = endings.append_clip(target, ending, width, height, fps, bool(audio))
        duration = ending['total_duration']
    publication = f'TÍTULO\n{project["title"]}\n\nDESCRIÇÃO\n{project["description"]}\n\nFONTES\n{project["sources"]}\n\nTAGS\n{project["tags"]}\n'
    (folder / 'publicacao.txt').write_text(publication)
    manifest = {'project_id': project['id'], 'job_id': job_id, 'revision': project['revision'],
                'visual_style': project.get('visual_style'), 'accent': project['accent'],
                'audio_sha256': digest(audio) if audio else None, 'script_sha256': store.script_hash(project),
                'video_sha256': digest(target), 'duration_seconds': duration, 'width': width, 'height': height,
                'ending': ending,
                'timing_source': timing['timing_source'], 'status': 'pending_human_review'}
    (folder / 'render-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    result = {'directory': str(folder.relative_to(DATA)), 'duration': duration,
              'has_audio': bool(audio) or bool(ending and ending['has_audio']), 'has_narration': bool(audio),
              'ending': ending,
              'width': width, 'height': height, 'timing': 'aligned' if audio else 'estimated'}
    (folder / 'result.json').write_text(json.dumps(result))
    store.progress(job_id, 99, 'Finalizando os arquivos')
    return result


if __name__ == '__main__':
    try:
        make_video(store.get_job(sys.argv[1], private=True))
    except Exception as exc:
        print(str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
