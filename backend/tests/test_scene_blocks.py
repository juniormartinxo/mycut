import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

TEMP = tempfile.TemporaryDirectory(prefix='mycut-block-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut import store, scene_chat, scene_layout, block_render, google_fonts, scene_media
from mycut.api import app
from mycut.models import ProjectInput
from mycut.config import DATA
from mycut.production import make_video
from mycut.media import digest


class SceneBlockTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs')
            db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'Editor de blocos'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def edit(self, **changes):
        body = {key: self.project[key] for key in ProjectInput.model_fields}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        if response.status_code == 200:
            self.project = response.json()
        return response

    def with_text(self):
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['narration'] = 'Um vídeo com áreas editáveis.'
        scene['blocks'][0]['object'] = scene_layout.VisualObject(type='title', text='Edição de cena', font_size=64).model_dump()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        return self.project['scenes'][0]

    def enqueue(self, scene, scope='object', target_id=None):
        body = scene_chat.MessageRequest(scene_id=scene['id'], scope=scope,
            target_id=target_id or scene['blocks'][0]['object']['id'], text='Deixe o título mais direto.', revision=self.project['revision'])
        with patch.object(scene_chat.bridge, 'require'), patch.object(scene_chat.agent_models, 'validate'):
            return scene_chat.enqueue(self.project['id'], body)['id']

    def finish_proposal(self, job_id, blocks):
        store.finish(job_id, 'succeeded', 'Proposta pronta', {'reply': 'Sugestão de título.', 'blocks': blocks})

    def test_default_geometry_persistence_and_validation(self):
        scene = self.project['scenes'][0]
        self.assertEqual([b['height'] for b in scene['blocks']], [20, 60, 20])
        self.assertTrue(all(b['object'] is None for b in scene['blocks']))
        scene['blocks'][0]['width'] = 60
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        store.initialize()
        self.assertEqual(store.get_project(self.project['id'])['scenes'][0]['blocks'][0]['width'], 60)
        scene['blocks'][0]['height'] = 50
        self.assertEqual(self.edit(scenes=[scene]).status_code, 422)
        scene['blocks'][0]['height'] = 20
        scene['blocks'][1]['id'] = scene['blocks'][0]['id']
        self.assertEqual(self.edit(scenes=[scene]).status_code, 422)

    def test_overflow_and_missing_media_save_draft_but_block_export(self):
        scene = self.with_text()
        scene['blocks'][0]['object']['text'] = 'Muito texto ' * 150
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        response = self.client.post('/api/scene-layout/inspect', json={'scene': scene, 'accent': self.project['accent'], 'project_id': self.project['id']})
        self.assertEqual(response.status_code, 200, response.text)
        issue = response.json()['issues'][0]
        self.assertEqual(issue['kind'], 'overflow')
        self.assertIsNotNone(issue['font_size'])
        self.assertEqual(self.client.post(f'/api/projects/{self.project["id"]}/renders', json={'mode': 'preview', 'revision': self.project['revision']}).status_code, 422)
        scene['blocks'][0]['object']['font_size'] = issue['font_size']
        self.assertFalse(block_render.inspect(scene, self.project)['issues'])
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='video').model_dump()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        self.assertEqual(block_render.inspect(scene, self.project)['issues'][0]['kind'], 'missing_media')
        scene['blocks'][1]['object']['asset_id'] = 'f'*32
        self.assertEqual(self.edit(scenes=[scene]).status_code, 422)

    def test_text_vertical_alignment_pixels_and_persistence(self):
        scene = self.with_text()
        obj = scene['blocks'][0]['object']
        obj.update(text='Título\nSegunda linha', font_size=40, color='#ff0000')
        x, y, w, h = map(round, scene_layout.geometry(scene['blocks'])[0]['object'])
        for kind in ('title', 'paragraph'):
            obj['type'] = kind
            bounds = []
            for alignment in ('top', 'center', 'bottom'):
                obj['text_vertical'] = alignment
                response = self.edit(scenes=[scene])
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['scenes'][0]['blocks'][0]['object']['text_vertical'], alignment)
                composition = block_render.BlockComposition(scene, self.project)
                frame = composition.frame(elapsed=0).crop((x, y, x+w, y+h))
                mask = Image.new('L', frame.size)
                mask.putdata([255 if r > 200 and g < 60 and b < 60 else 0 for r, g, b in frame.getdata()])
                bounds.append(mask.getbbox())
                composition.close()
            top, center, bottom = bounds
            self.assertLessEqual(abs(top[1]-8), 1)
            self.assertLessEqual(abs((center[1]+center[3])/2-h/2), 1)
            self.assertLessEqual(abs(bottom[3]-(h-8)), 1)
            self.assertEqual(top[3]-top[1], bottom[3]-bottom[1])
        obj.pop('text_vertical')
        self.assertEqual(scene_layout.VisualObject.model_validate(obj).text_vertical, 'top')

    def test_text_vertical_alignment_matches_preview_and_mp4(self):
        scene = self.with_text()
        for block, alignment in zip(scene['blocks'], ('top', 'center', 'bottom')):
            block['object'] = scene_layout.VisualObject(type='title', text='Texto alinhado', font_size=40,
                                                       color='#ff0000', text_vertical=alignment).model_dump()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        preview = self.client.post('/api/scene-preview', json={'scene': scene, 'project_id': self.project['id'],
                                    'accent': self.project['accent'], 'visual_style': self.project['visual_style']})
        self.assertEqual(preview.status_code, 200)
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        result = make_video(store.claim())
        exported = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(DATA / result['directory'] / 'short.mp4'),
                                           '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', 'pipe:1'])
        centers = []
        for content in (preview.content, exported):
            with Image.open(io.BytesIO(content)) as image:
                positions = []
                scale = image.width/1080
                for info in scene_layout.geometry(scene['blocks']):
                    x, y, w, h = info['object']
                    crop = image.convert('RGB').crop(tuple(round(v*scale) for v in (x, y, x+w, y+h)))
                    pixels = crop.load()
                    rows = [row for row in range(crop.height) if any(
                        pixels[col, row][0] > 170 and pixels[col, row][1] < 90 and pixels[col, row][2] < 90
                        for col in range(crop.width))]
                    self.assertTrue(rows)
                    positions.append((min(rows)+max(rows))/2/crop.height)
                self.assertLess(positions[0], .15)
                self.assertAlmostEqual(positions[1], .5, delta=.015)
                self.assertGreater(positions[2], .85)
                centers.append(positions)
        for preview_y, exported_y in zip(*centers):
            self.assertAlmostEqual(preview_y, exported_y, delta=.015)

    def test_google_fonts_real_offline_font_and_unknown_family(self):
        with patch.object(google_fonts.httpx, 'Client', side_effect=AssertionError('offline')):
            response = self.client.get('/api/google-fonts')
            self.assertGreater(len(response.json()['families']), 1000)
            font = self.client.get('/api/google-fonts/file?family=Roboto')
            self.assertEqual(font.status_code, 200)
            self.assertGreater(len(font.content), 10000)
            scene = self.with_text()
            self.assertFalse(block_render.inspect(scene, self.project)['issues'])
        self.assertEqual(self.client.post('/api/google-fonts/install', json={'family': '../../private'}).status_code, 422)

    def test_proposal_persists_in_lane_and_requires_atomic_acceptance(self):
        scene = self.with_text()
        original = copy.deepcopy(scene)
        identity = self.enqueue(scene)
        self.assertIsNone(store.claim(False))
        job = store.claim(True)
        self.assertEqual(job['kind'], 'scene_edit')
        blocks = copy.deepcopy(scene['blocks'])
        blocks[0]['object']['text'] = 'Título proposto'
        self.finish_proposal(identity, blocks)
        self.assertEqual(store.get_project(self.project['id'])['scenes'][0], original)
        messages = scene_chat.messages(self.project['id'])['messages']
        self.assertFalse(messages[0]['stale'])
        result = self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{identity}', json={'decision': 'accepted', 'revision': self.project['revision']})
        self.assertEqual(result.status_code, 200, result.text)
        self.project = result.json()
        self.assertEqual(self.project['scenes'][0]['blocks'][0]['object']['text'], 'Título proposto')
        self.assertEqual(self.project['scenes'][0]['narration'], original['narration'])
        self.assertEqual(scene_chat.messages(self.project['id'])['messages'][0]['decision'], 'accepted')
        self.assertEqual(self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{identity}', json={'decision': 'accepted', 'revision': self.project['revision']}).status_code, 409)

    def test_human_edits_stale_proposal_and_deleted_object_archives_thread(self):
        scene = self.with_text()
        identity = self.enqueue(scene)
        proposed = copy.deepcopy(scene['blocks'])
        proposed[0]['object']['text'] = 'Proposta antiga'
        scene['blocks'][0]['object']['text'] = 'Minha edição'
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)  # Edits allowed while agent is queued.
        self.finish_proposal(identity, proposed)
        self.assertTrue(scene_chat.messages(self.project['id'])['messages'][0]['stale'])
        result = self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{identity}', json={'decision': 'accepted', 'revision': self.project['revision']})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(store.get_project(self.project['id'])['scenes'][0]['blocks'][0]['object']['text'], 'Minha edição')
        scene['blocks'][0]['object'] = None
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        threads = scene_chat.messages(self.project['id'])['threads']
        self.assertTrue(threads[0]['archived'])
        self.assertTrue(scene_chat.messages(self.project['id'])['messages'])

    def test_scope_escape_and_foreign_proposal_are_rejected(self):
        scene = self.with_text()
        identity = self.enqueue(scene)
        proposed = copy.deepcopy(scene['blocks'])
        proposed[1]['object'] = scene_layout.VisualObject(type='paragraph', text='Fora do alcance').model_dump()
        self.finish_proposal(identity, proposed)
        response = self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{identity}', json={'decision': 'accepted', 'revision': self.project['revision']})
        self.assertEqual(response.status_code, 422)
        other = self.client.post('/api/projects', json={'title': 'Outro projeto'}).json()
        self.assertEqual(self.client.post(f'/api/projects/{other["id"]}/scene-proposals/{identity}', json={'decision': 'accepted', 'revision': other['revision']}).status_code, 404)

    def test_conversion_preserves_old_scene_until_acceptance(self):
        original = {'title': 'Cena antiga', 'narration': 'Uma explicação.', 'layout': 'flow', 'items': ['Primeiro', 'Depois']}
        self.assertEqual(self.edit(scenes=[original]).status_code, 200)
        result = self.client.post(f'/api/projects/{self.project["id"]}/scene-layout/convert?revision={self.project["revision"]}', json={
            'scene': original, 'project_id': self.project['id'], 'accent': self.project['accent']})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIsNone(result.json()['project']['scenes'][0]['blocks'])
        converted = result.json()['scene']
        self.assertEqual(converted['blocks'][0]['object']['text'], original['title'])
        self.assertEqual(converted['blocks'][1]['object']['type'], 'image')
        self.assertEqual(converted['narration'], original['narration'])

    def test_conversion_uses_draft_style_without_saving_other_edits(self):
        original = {'title': 'Cena antiga', 'narration': 'Uma explicação.', 'layout': 'flow', 'items': ['Primeiro', 'Depois']}
        self.assertEqual(self.edit(scenes=[original], visual_style=None).status_code, 200)
        result = self.client.post(f'/api/projects/{self.project["id"]}/scene-layout/convert?revision={self.project["revision"]}', json={
            'scene': {**original, 'title': 'Título em rascunho'}, 'project_id': self.project['id'], 'accent': '#abcdef',
            'visual_style': {'format_id': 'editorial', 'background': '#123456'}})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['scene']['blocks'][0]['object']['text'], 'Título em rascunho')
        saved = store.get_project(self.project['id'])
        self.assertIsNone(saved['visual_style'])
        self.assertEqual(saved['scenes'][0]['title'], 'Cena antiga')
        self.assertIsNone(saved['scenes'][0]['blocks'])
        with Image.open(DATA / saved['images'][-1]['path']) as image:
            self.assertEqual(image.convert('RGB').getpixel((0, 0)), (18, 52, 86))

    def test_video_loops_inside_object_and_final_has_only_narration_audio(self):
        with tempfile.TemporaryDirectory() as staging:
            path = Path(staging) / 'sample.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=160x90:d=0.3:r=30',
                            '-f', 'lavfi', '-i', 'color=c=blue:s=160x90:d=0.3:r=30',
                            '-f', 'lavfi', '-i', 'sine=frequency=880:duration=0.6',
                            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]',
                            '-map', '2:a', '-c:a', 'aac', '-c:v', 'libx264', '-threads', '1', str(path)], check=True)
            scene = self.with_text()
            with path.open('rb') as stream:
                uploaded = self.client.post(f'/api/projects/{self.project["id"]}/scene-videos?revision={self.project["revision"]}',
                    files={'file': ('sample.mp4', stream, 'video/mp4')})
            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            self.project = uploaded.json()
            self.assertNotIn('path', self.project['videos'][0])
            self.assertEqual(self.client.get(self.project['videos'][0]['url']).status_code, 200)
            project = store.get_project(self.project['id'])
            record = project['videos'][0]
            normalized = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(DATA / record['path'])]))
            self.assertEqual([s['codec_type'] for s in normalized['streams']], ['video'])
            scene['blocks'][1]['object'] = scene_layout.VisualObject(type='video', asset_id=record['id']).model_dump()
            project = store.update_project(project['id'], {'scenes': [scene]}, project['revision'])
            composition = block_render.BlockComposition(scene, project, 360)
            try:
                red = composition.frame(0).getpixel((180, 300))
                blue = composition.frame(.4).getpixel((180, 300))
                repeat = composition.frame(.7).getpixel((180, 300))
            finally:
                composition.close()
            self.assertGreater(red[0], 200)
            self.assertGreater(blue[2], 200)
            self.assertGreater(repeat[0], 200)
            job = store.enqueue(project['id'], 'preview', project['revision'])
            claimed = store.claim()
            result = make_video(claimed)
            self.assertFalse(result['has_audio'])
            video = DATA / result['directory'] / 'short.mp4'
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(video)]))
            self.assertEqual([s['codec_type'] for s in info['streams']], ['video'])
            store.finish(job['id'], 'succeeded', 'Pronto', result)
            # Exercise cover decoding and a real final export with one narration track.
            scene['blocks'][1]['object']['fit'] = 'cover'
            folder = DATA / 'projects' / project['id']
            audio = folder / 'test.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
                            '-t', '1.5', str(audio)], check=True)
            alignment = folder / 'test-alignment.json'
            words = scene['narration'].split()
            alignment.write_text(json.dumps({'audio_sha256': digest(audio), 'segments': [{'start': 0, 'end': 1.5,
                'text': scene['narration'], 'words': [{'word': word, 'start': i*.25, 'end': (i+1)*.25} for i, word in enumerate(words)]}]}))
            project = store.update_project(project['id'], {'scenes': [scene], 'audio': {'path': str(audio.relative_to(DATA)),
                'sha256': digest(audio), 'duration': 1.5, 'normalized': True, 'script_hash': store.script_hash(project),
                'alignment': str(alignment.relative_to(DATA))}}, project['revision'])
            job = store.enqueue(project['id'], 'final', project['revision'])
            result = make_video(store.claim())
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                str(DATA / result['directory'] / 'short.mp4')]))
            self.assertEqual([s['codec_type'] for s in info['streams']], ['video', 'audio'])
            self.assertEqual((info['streams'][0]['width'], info['streams'][0]['height']), (1080, 1920))

    def test_mixed_legacy_keeps_original_renderer(self):
        scene = self.with_text()
        legacy = {'title': 'Original', 'narration': 'Ideia antiga.', 'layout': 'flow', 'items': ['Um', 'Dois']}
        self.assertEqual(self.edit(scenes=[legacy, scene], visual_style=None).status_code, 200)
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        with patch('mycut.production.visuals.Composition', side_effect=AssertionError('Legacy renderer changed')):
            result = make_video(store.claim())
        self.assertFalse(result['has_audio'])

    def test_proposal_accepts_unchanged_defaults_from_older_objects(self):
        scene = self.with_text()
        scene['blocks'][0]['object'].pop('zoom')
        proposed = copy.deepcopy(scene['blocks'])
        proposed[0]['object']['zoom'] = 1
        proposed[1]['width'] = 80
        self.assertEqual(scene_layout.scoped_blocks(scene, proposed, 'block', proposed[1]['id']), proposed)

    def test_zoom_persists_and_rejects_invalid_values(self):
        scene = self.with_text()
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='image', fit='cover', zoom=2.5).model_dump()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        self.assertEqual(store.get_project(self.project['id'])['scenes'][0]['blocks'][1]['object']['zoom'], 2.5)
        for value in (0, .9, 5.1):
            scene['blocks'][1]['object']['zoom'] = value
            self.assertEqual(self.edit(scenes=[scene]).status_code, 422)

    def test_scoped_resize_moves_only_one_shared_edge(self):
        scene = self.with_text()
        target_id = scene['blocks'][1]['id']
        for heights in ([10, 70, 20], [20, 70, 10]):
            proposed = copy.deepcopy(scene['blocks'])
            for block, height in zip(proposed, heights):
                block['height'] = height
            self.assertEqual(scene_layout.scoped_blocks(scene, proposed, 'block', target_id), proposed)
        proposed = copy.deepcopy(scene['blocks'])
        for block, height in zip(proposed, [15, 70, 15]):
            block['height'] = height
        with self.assertRaisesRegex(ValueError, 'uma borda'):
            scene_layout.scoped_blocks(scene, proposed, 'block', target_id)

    def test_image_and_video_zoom_match_static_preview_and_export(self):
        with tempfile.TemporaryDirectory() as staging:
            picture, clip = Path(staging) / 'target.png', Path(staging) / 'target.mp4'
            source = Image.new('RGB', (320, 180), 'red')
            source.paste('lime', (80, 45, 240, 135))
            source.save(picture)
            subprocess.run(['ffmpeg', '-v', 'error', '-loop', '1', '-i', str(picture), '-t', '0.3',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-threads', '1', str(clip)], check=True)
            scene = self.with_text()
            for kind, path, endpoint, mime in [('image', picture, 'images', 'image/png'), ('video', clip, 'scene-videos', 'video/mp4')]:
                with path.open('rb') as stream:
                    uploaded = self.client.post(f'/api/projects/{self.project["id"]}/{endpoint}?revision={self.project["revision"]}',
                                               files={'file': (path.name, stream, mime)})
                self.assertEqual(uploaded.status_code, 200, uploaded.text)
                self.project = uploaded.json()
                asset = self.project['images' if kind == 'image' else 'videos'][-1]
                obj = scene_layout.VisualObject(type=kind, asset_id=asset['id'], fit='cover').model_dump()
                scene['blocks'][1]['object'] = obj
                for zoom, crop_x, crop_y, point, channel in [
                    (1, 50, 50, (90, 900), 0), (2, 50, 50, (90, 900), 1),
                    (2, 100, 50, (990, 900), 0), (2, 50, 0, (540, 510), 0),
                    (2, 50, 100, (540, 1290), 0), (2, 0, 50, (90, 900), 0),
                ]:
                    obj['zoom'] = zoom
                    obj['crop_x'], obj['crop_y'] = crop_x, crop_y
                    composition = block_render.BlockComposition(scene, store.get_project(self.project['id']))
                    try:
                        for elapsed in (None, 0):
                            color = composition.frame(elapsed).getpixel(point)
                            self.assertGreater(color[channel], 220, (kind, zoom, elapsed, color))
                            self.assertLess(color[1-channel], 30)
                    finally:
                        composition.close()
            self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
            store.enqueue(self.project['id'], 'preview', self.project['revision'])
            result = make_video(store.claim())
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(DATA / result['directory'] / 'short.mp4'),
                                           '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', 'pipe:1'])
            with Image.open(io.BytesIO(raw)) as rendered:
                color = rendered.getpixel((round(90*rendered.width/1080), round(900*rendered.height/1920)))
                self.assertGreater(color[0], 220, color)
                self.assertLess(color[1], 30, color)

    def test_crop_position_validation_persistence_and_old_defaults(self):
        self.assertEqual(scene_layout.VisualObject(type='image').crop_x, 50)
        scene = self.with_text()
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='image', fit='cover', zoom=2, crop_x=10, crop_y=90).model_dump()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        saved = store.get_project(self.project['id'])['scenes'][0]['blocks'][1]['object']
        self.assertEqual((saved['crop_x'], saved['crop_y'], saved['zoom']), (10, 90, 2))
        for key in ('crop_x', 'crop_y'):
            for invalid in (-1, 101):
                with self.assertRaises(ValueError):
                    scene_layout.VisualObject.model_validate({**saved, key: invalid})

    def test_old_scene_agent_endpoint_cannot_bypass_block_proposals(self):
        self.with_text()
        response = self.client.post(f'/api/projects/{self.project["id"]}/run',
            json={'kind': 'scenes', 'revision': self.project['revision']})
        self.assertEqual(response.status_code, 409, response.text)


if __name__ == '__main__':
    unittest.main()
