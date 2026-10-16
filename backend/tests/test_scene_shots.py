import copy
import io
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops, ImageDraw, ImageStat

TEMP = tempfile.TemporaryDirectory(prefix='mycut-shot-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut import store, scene_chat, scene_layout, block_render, flow
from mycut.api import app
from mycut.models import ProjectInput
from mycut.config import DATA
from mycut.production import make_video

NARRATION = ('Primeiro o tom da história com a paleta e a luz. Depois a ficha da personagem com números exatos. '
             'Por último o cenário vazio que vira a referência do mundo inteiro.')
SHEET = 'Idade: 38 anos\nAltura: 172 cm\nPeso: 64 kg\nCicatriz: 3 cm'


def difference(first, second):
    return sum(ImageStat.Stat(ImageChops.difference(first.convert('RGB'), second.convert('RGB'))).mean)/3


def obj(kind, **values):
    return scene_layout.VisualObject(type=kind, **values).model_dump()


def plano(anchor, blocks, **values):
    return scene_layout.Shot(anchor=anchor, blocks=blocks, **values).model_dump()


def blocks(*objects):
    heights = {1: [100], 2: [30, 70], 3: [20, 60, 20]}[len(objects)]
    return [scene_layout.SceneBlock(height=h, object=o).model_dump() for h, o in zip(heights, objects)]


class SceneShotTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs')
            db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'Planos'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def edit(self, **changes):
        body = {key: self.project[key] for key in ProjectInput.model_fields}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        if response.status_code == 200:
            self.project = response.json()
        return response

    def upload_image(self, color='#c04020', size=(1200, 800), stripes=True):
        image = Image.new('RGB', size, color)
        if stripes:
            draw = ImageDraw.Draw(image)
            for x in range(0, size[0], 300):
                draw.rectangle((x, 0, x+120, size[1]), fill='#20a0c0')
        stream = io.BytesIO()
        image.save(stream, 'PNG')
        response = self.client.post(f'/api/projects/{self.project["id"]}/images?revision={self.project["revision"]}',
                                    files={'file': ('fundo.png', stream.getvalue(), 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()
        return self.project['images'][-1]['id']

    def three_shots(self, **first):
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['narration'] = NARRATION
        scene['blocks'] = blocks(obj('title', text='ETAPA 1: TOM', font_size=72), obj('paragraph', text='Paleta teal e âmbar', font_size=48))
        scene.update(first)
        scene['shots'] = [
            plano('ficha', blocks(obj('title', text='ETAPA 2: FICHA', font_size=72), obj('paragraph', text=SHEET, font_size=96, reveal='lines')),
                  background={'kind': 'gradient', 'color': '#0e3b43', 'color_to': '#d98a1c', 'angle': 180}),
            plano('cenário', blocks(obj('title', text='ETAPA 3: CENÁRIO', font_size=72)), transition='fade',
                  background={'kind': 'color', 'color': '#101820'}, brand=False),
        ]
        return scene

    def test_planos_persist_and_older_scenes_keep_their_shape(self):
        self.assertEqual(self.edit(scenes=self.project['scenes']).status_code, 200)
        original = copy.deepcopy(self.project['scenes'][0])
        self.assertEqual(self.edit(scenes=[original]).status_code, 200)
        self.assertEqual(self.project['scenes'][0], original)
        self.assertFalse({'shots', 'background', 'brand'} & set(original))
        self.assertNotIn('reveal', self.project['scenes'][0]['blocks'][0].get('object') or {})
        scene = self.three_shots()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        saved = self.project['scenes'][0]
        self.assertEqual(len(saved['shots']), 2)
        self.assertEqual(saved['shots'][0]['anchor'], 'ficha')
        self.assertEqual(saved['shots'][0]['blocks'][1]['object']['reveal'], 'lines')
        self.assertEqual(saved['shots'][1]['transition'], 'fade')
        self.assertFalse(saved['shots'][1]['brand'])
        self.assertEqual(store.get_project(self.project['id'])['scenes'][0]['shots'], saved['shots'])

    def test_invalid_planos_are_rejected(self):
        scene = self.three_shots()
        cases = []
        broken = copy.deepcopy(scene)
        broken['shots'][0]['background'] = {'kind': 'gradient', 'color': '#000000'}
        cases.append(broken)
        broken = copy.deepcopy(scene)
        broken['shots'][0]['blocks'][1]['object']['motion'] = 'zoom_in'
        cases.append(broken)
        broken = copy.deepcopy(scene)
        broken['blocks'][0]['object'] = obj('video', reveal='none')
        broken['blocks'][0]['object']['reveal'] = 'typing'
        cases.append(broken)
        broken = copy.deepcopy(scene)
        broken['shots'][1]['id'] = broken['shots'][0]['id']
        cases.append(broken)
        broken = copy.deepcopy(scene)
        broken['shots'] = [plano(None, blocks(None)) for _ in range(12)]
        cases.append(broken)
        legacy = copy.deepcopy(scene)
        legacy['blocks'] = None
        cases.append(legacy)
        for case in cases:
            self.assertEqual(self.edit(scenes=[case]).status_code, 422)
        many = []
        for _ in range(6):
            item = copy.deepcopy(self.project['scenes'][0])
            item['id'] = scene_layout.new_id()
            item['blocks'] = blocks(None)
            item['shots'] = [plano(None, blocks(None)) for _ in range(10)]
            many.append(item)
        response = self.edit(scenes=many)
        self.assertEqual(response.status_code, 422)
        self.assertIn('60 planos', response.text)
        missing = copy.deepcopy(scene)
        missing['shots'][0]['background'] = {'kind': 'image', 'asset_id': scene_layout.new_id()}
        response = self.edit(scenes=[missing])
        self.assertEqual(response.status_code, 422)
        self.assertIn('fundo', response.text)

    def test_planos_follow_their_anchors_and_unanchored_ones_spread(self):
        scene = self.three_shots()
        clock = flow.estimate_clock(NARRATION)
        words = NARRATION.split()
        windows = block_render.shot_windows(scene, clock)
        self.assertEqual(windows[0][0], 0)
        self.assertAlmostEqual(windows[1][0], clock['words'][words.index('ficha')])
        self.assertAlmostEqual(windows[2][0], clock['words'][words.index('cenário')])
        self.assertEqual(windows[-1][1], clock['duration'])
        scene['shots'][0]['anchor'] = None
        scene['shots'][1]['anchor'] = 'palavra ausente'
        windows = block_render.shot_windows(scene, clock)
        self.assertAlmostEqual(windows[1][0], clock['duration']/3)
        self.assertAlmostEqual(windows[2][0], clock['duration']*2/3)
        report = block_render.inspect(scene, self.project, clock)
        self.assertEqual([w['kind'] for w in report['warnings']], ['shot_anchor'])
        self.assertIn('não está na narração', report['warnings'][0]['message'])
        # A passage that exists but comes before the previous plano's start says so.
        out_of_order = copy.deepcopy(scene)
        out_of_order['shots'][0]['anchor'], out_of_order['shots'][1]['anchor'] = 'cenário', 'ficha'
        message = block_render.inspect(out_of_order, self.project, clock)['warnings'][0]['message']
        self.assertIn('Plano 3', message)
        self.assertIn('antes do início do plano anterior', message)
        self.assertEqual(len(report['shots']), 3)
        # Late anchors still leave every plano its minimum time.
        scene['shots'][0]['anchor'] = scene['shots'][1]['anchor'] = 'mundo inteiro'
        windows = block_render.shot_windows(scene, clock)
        self.assertTrue(all(end-start >= block_render.MIN_SHOT-1e-6 for start, end in windows), windows)
        short = {'duration': 1.5, 'words': clock['words'][:1], 'source': 'estimate'}
        windows = block_render.shot_windows(scene, short)
        self.assertAlmostEqual(sum(end-start for start, end in windows), 1.5)
        self.assertIn('shot_short', [w['kind'] for w in block_render.inspect(scene, self.project, short)['warnings']])

    def test_composition_changes_at_each_plano_with_gradient_brand_and_fade(self):
        scene = self.three_shots()
        clock = flow.estimate_clock(NARRATION)
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']), 1080, clock=clock)
        (_, first_end), (second, second_end), (third, _) = composition.windows
        a = composition.frame(first_end-.2)
        b = composition.frame(second+1.5)
        c = composition.frame(third+block_render.FADE+.2)
        self.assertGreater(difference(a, b), 5)
        self.assertGreater(difference(b, c), 5)
        # The gradient runs from teal at the top to amber at the bottom.
        self.assertLess(difference(b.crop((0, 0, 40, 40)), Image.new('RGB', (40, 40), '#0e3b43')), 4)
        self.assertLess(difference(b.crop((0, 1880, 40, 1920)), Image.new('RGB', (40, 40), '#d98a1c')), 4)
        # Brand on in the second plano, off in the third.
        self.assertGreater(ImageStat.Stat(b.crop((80, 95, 400, 165)).convert('L')).stddev[0], 2)
        self.assertLess(ImageStat.Stat(c.crop((70, 95, 1010, 200)).convert('L')).stddev[0], 1)
        # Fusão: halfway through, the frame lies between both planos.
        middle = composition.frame(third+block_render.FADE/2)
        before = composition.shots[1].frame(third+block_render.FADE/2-second)
        after = composition.shots[2].frame(block_render.FADE/2)
        self.assertLess(difference(middle, Image.blend(before, after, .5)), 1.5)
        self.assertGreater(difference(middle, after), 3)
        # A cut has no blend.
        self.assertLess(difference(composition.frame(second+.01), composition.shots[1].frame(.01)), .01)
        composition.close()

    def test_lines_reveal_typing_and_static_state(self):
        scene = self.three_shots()
        clock = flow.estimate_clock(NARRATION)
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']), 1080, clock=clock)
        start, end = composition.windows[1]
        reveal = composition.shots[1].reveals[0][0]
        entries = sorted(reveal.entries.values())
        self.assertEqual(len(entries), 4)
        self.assertLess(entries[-1], (end-start)*block_render.REVEAL_SPAN)
        ink = lambda layer: sum(1 for value in layer.getchannel('A').get_flattened_data() if value > 128)
        first, half, done = reveal.layer(entries[0]+block_render.LINE_IN), reveal.layer(entries[2]+block_render.LINE_IN), reveal.layer(None)
        self.assertLess(ink(first), ink(half))
        self.assertLess(ink(half), ink(done))
        self.assertEqual(ink(reveal.layer(end-start)), ink(done))
        typing = copy.deepcopy(scene)
        typing['shots'][0]['blocks'][1]['object']['reveal'] = 'typing'
        composition = block_render.BlockComposition(typing, store.get_project(self.project['id']), 1080, clock=clock)
        typed = composition.shots[1].reveals[0][0]
        early, later = ink(typed.layer(.4)), ink(typed.layer(1.2))
        self.assertLess(early, later)
        self.assertLess(later, ink(typed.layer(None)))
        finished = typed.characters/typed.speed
        self.assertLessEqual(finished, (end-start)*block_render.TYPING_SPAN+1e-6)
        static = composition.shots[1].frame(None)
        self.assertLess(difference(static, composition.shots[1].frame(end-start)), .01)

    def test_camera_motion_on_image_object_and_background(self):
        image_id = self.upload_image()
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['narration'] = NARRATION
        scene['blocks'] = blocks(obj('title', text='Corredor', font_size=64), obj('image', asset_id=image_id, fit='cover', motion='zoom_in'))
        scene['shots'] = [plano('ficha', blocks(obj('title', text='Plano cheio', font_size=64)),
                                background={'kind': 'image', 'asset_id': image_id, 'motion': 'pan_right', 'dim': 40}, brand=False)]
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200, self.project)
        clock = flow.estimate_clock(NARRATION)
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']), 1080, clock=clock)
        (start, end), (second, second_end) = composition.windows
        box = tuple(round(v) for v in scene_layout.geometry(scene['blocks'])[1]['object'])
        crop = (box[0], box[1], box[0]+box[2], box[1]+box[3])
        still = composition.frame(None).crop(crop)
        self.assertLess(difference(still, composition.frame(0).crop(crop)), .01)
        self.assertGreater(difference(still, composition.frame(end-.1).crop(crop)), 3)
        left, right = composition.frame(second+.05), composition.frame(second_end-.05)
        self.assertGreater(difference(left.crop((0, 300, 1080, 1500)), right.crop((0, 300, 1080, 1500))), 3)
        # Dimmed by 40%: the stripes' red is darker than the source color.
        red = max(pixel[0] for pixel in left.crop((0, 600, 1080, 640)).get_flattened_data())
        self.assertLess(red, 0xc0*.7)
        self.assertEqual(block_render.motion_box((100, 200), 'zoom_in', 0), (0, 0, 100, 200))
        x0, _, x1, _ = block_render.motion_box((100, 200), 'pan_right', 1)
        self.assertAlmostEqual(x1, 100)
        composition.close()

    def upload_video(self):
        with tempfile.TemporaryDirectory() as staging:
            path = os.path.join(staging, 'fundo.mp4')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=180x320:d=0.5:r=30',
                            '-f', 'lavfi', '-i', 'color=c=blue:s=180x320:d=0.5:r=30',
                            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]',
                            '-c:v', 'libx264', '-threads', '1', path], check=True)
            with open(path, 'rb') as stream:
                uploaded = self.client.post(f'/api/projects/{self.project["id"]}/scene-videos?revision={self.project["revision"]}',
                                            files={'file': ('fundo.mp4', stream, 'video/mp4')})
            self.assertEqual(uploaded.status_code, 200, uploaded.text)
            self.project = uploaded.json()
        return self.project['videos'][-1]['id']

    def test_background_video_plays_from_the_plano_start_behind_the_blocks(self):
        video_id = self.upload_video()
        scene = self.three_shots()
        scene['shots'][1]['background'] = {'kind': 'video', 'asset_id': video_id}
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200, self.project)
        clock = flow.estimate_clock(NARRATION)
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']), 1080, fps=30, clock=clock)
        third = composition.windows[2][0]
        pixel = lambda t: composition.frame(t).getpixel((40, 1000))
        # The clip restarts with the plano: red first, blue after half a second.
        early, late = pixel(third+block_render.FADE+.02), pixel(third+.75)
        self.assertGreater(early[0], 150)
        self.assertLess(early[2], 100)
        self.assertGreater(late[2], 150)
        self.assertLess(late[0], 100)
        # The static view shows the poster, never a decoded frame.
        self.assertGreater(composition.shots[2].frame(None, videos=False).getpixel((40, 1000))[0], 150)
        composition.close()

    def test_finished_planos_release_their_video_decoders(self):
        video_id = self.upload_video()
        scene = self.three_shots(background={'kind': 'video', 'asset_id': video_id})
        scene['shots'][0]['background'] = {'kind': 'video', 'asset_id': video_id}
        scene['shots'][1]['background'] = {'kind': 'video', 'asset_id': video_id}
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200, self.project)
        clock = flow.estimate_clock(NARRATION)
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']), 540, fps=24, clock=clock)
        (_, first_end), (second, _), (third, _) = composition.windows
        first = second_reader = None
        try:
            for step in range(0, int(third*24)+int(block_render.FADE*24)+6):
                now = step/24
                composition.frame(now)
                if now < second:
                    first = composition.shots[0].readers['background']
                elif now < third:
                    self.assertEqual(composition.shots[0].readers, {}, now)
                    self.assertIsNotNone(first.process.poll())
                    second_reader = composition.shots[1].readers['background']
                elif now < third+block_render.FADE:
                    # The previous plano still plays during the fade into the next one.
                    self.assertIsNone(second_reader.process.poll(), now)
                else:
                    self.assertEqual(composition.shots[1].readers, {}, now)
                    self.assertIsNotNone(second_reader.process.poll())
            self.assertIn('background', composition.shots[2].readers)
            # A plano drawn again after closing reopens its decoder at the right time.
            self.assertGreater(composition.frame(second+.75).getpixel((20, 500))[2], 150)
        finally:
            composition.close()

    def test_export_closes_each_scene_before_the_next_one_plays(self):
        first, second = self.three_shots(), copy.deepcopy(self.three_shots())
        second['id'] = scene_layout.new_id()
        for item in (second, *second['shots']):
            for block in item['blocks']:
                block['id'] = scene_layout.new_id()
                if block['object']:
                    block['object']['id'] = scene_layout.new_id()
        for shot in second['shots']:
            shot['id'] = scene_layout.new_id()
        self.assertEqual(self.edit(scenes=[first, second]).status_code, 200, self.project)
        events = []
        original_close, original_frame = block_render.BlockComposition.close, block_render.BlockComposition.frame

        def close(composition):
            events.append(('close', composition.scene['id']))
            return original_close(composition)

        def frame(composition, elapsed=None, *args, **kwargs):
            if elapsed is not None and (not events or events[-1] != ('frame', composition.scene['id'])):
                events.append(('frame', composition.scene['id']))
            return original_frame(composition, elapsed, *args, **kwargs)
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        with patch.object(block_render.BlockComposition, 'close', close), patch.object(block_render.BlockComposition, 'frame', frame):
            make_video(store.claim())
        ids = [s['id'] for s in self.project['scenes']]
        self.assertEqual(events[:3], [('frame', ids[0]), ('close', ids[0]), ('frame', ids[1])])

    def test_preview_matches_exported_mp4_in_planos_reveal_motion_and_fade(self):
        image_id = self.upload_image()
        scene = self.three_shots()
        scene['blocks'][1]['object'] = obj('image', asset_id=image_id, fit='cover', motion='zoom_in')
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200, self.project)
        scene = self.project['scenes'][0]
        fps = 24
        clock = flow.estimate_clock(NARRATION)
        windows = block_render.shot_windows(scene, clock)
        snap = lambda t: round(t*fps)/fps
        times = [snap(windows[0][1]*.6), snap(windows[1][0]+.3), snap(windows[1][1]-.15),
                 snap(windows[2][0]+block_render.FADE/2), snap(windows[2][0]+1)]
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        result = make_video(store.claim())
        video = DATA / result['directory'] / 'short.mp4'
        # Captions differ by design between the editor preview and the export; compare above them.
        area = (0, 0, 540, 800)
        exported, previews = [], []
        for t in times:
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf', f'select=eq(n\\,{round(t*fps)})',
                                           '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', 'pipe:1'])
            with Image.open(io.BytesIO(raw)) as image:
                exported.append(image.convert('RGB').crop(area))
            response = self.client.post('/api/scene-preview', json={'scene': scene, 'project_id': self.project['id'],
                                        'accent': self.project['accent'], 'elapsed': t, 'width': 'full'})
            self.assertEqual(response.status_code, 200, response.text)
            with Image.open(io.BytesIO(response.content)) as image:
                previews.append(image.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS).crop(area))
        for i, (preview, frame) in enumerate(zip(previews, exported)):
            same = difference(preview, frame)
            self.assertLess(same, 2.5, (times[i], same))
            for j, other in enumerate(exported):
                if j != i:
                    self.assertGreater(difference(preview, other), same+.3, (times[i], times[j]))

    def test_inspection_reports_planos_and_missing_background_media(self):
        scene = self.three_shots()
        scene['shots'][1]['background'] = {'kind': 'video'}
        response = self.client.post('/api/scene-layout/inspect', json={'scene': scene, 'project_id': self.project['id'],
                                    'accent': self.project['accent']})
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual([(i['kind'], i['shot_id']) for i in report['issues']], [('missing_media', scene['shots'][1]['id'])])
        self.assertEqual([s['id'] for s in report['shots']], [scene['id'], *(s['id'] for s in scene['shots'])])
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        with self.assertRaisesRegex(ValueError, 'Plano 3'):
            store.enqueue(self.project['id'], 'preview', self.project['revision'])

    def test_agent_proposal_changes_only_the_plano_of_its_target(self):
        self.assertEqual(self.edit(scenes=[self.three_shots()]).status_code, 200)
        scene = self.project['scenes'][0]
        second = scene['shots'][0]
        target = second['blocks'][0]['object']['id']
        body = scene_chat.MessageRequest(scene_id=scene['id'], scope='object', target_id=target,
                                         text='Título mais curto.', revision=self.project['revision'])
        with patch.object(scene_chat.bridge, 'require'), patch.object(scene_chat.agent_models, 'validate'):
            job_id = scene_chat.enqueue(self.project['id'], body)['id']
        job = store.get_job(job_id, private=True)
        proposed = copy.deepcopy(second['blocks'])
        proposed[0]['object']['text'] = 'FICHA'
        seen = {}

        def fake_agent(job, role, instructions, payload, model, attempt=1, **_):
            seen.update(payload)
            return scene_chat.Proposal(reply='Encurtei.', blocks=proposed)
        with patch('mycut.pipeline.agent', side_effect=fake_agent):
            scene_chat.run(job)
        self.assertEqual(seen['shot'], {'number': 2, 'count': 3, 'anchor': 'ficha'})
        self.assertEqual([b['id'] for b in seen['scene']['blocks']], [b['id'] for b in second['blocks']])
        self.assertNotIn('shots', seen['scene'])
        store.finish(job_id, 'succeeded', 'Proposta pronta', {'reply': 'Encurtei.', 'blocks': proposed})
        self.assertFalse(scene_chat.messages(self.project['id'])['messages'][0]['stale'])
        accepted = self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{job_id}',
                                    json={'decision': 'accepted', 'revision': self.project['revision']})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        saved = accepted.json()['scenes'][0]
        self.assertEqual(saved['shots'][0]['blocks'][0]['object']['text'], 'FICHA')
        self.assertEqual(saved['blocks'], scene['blocks'])
        self.assertEqual(saved['shots'][1], scene['shots'][1])
        # A proposal for the whole plano may change any of its blocks, and none elsewhere.
        whole = scene_layout.with_shot_blocks(saved, saved['shots'][1]['id'], blocks(obj('title', text='Novo plano')))
        self.assertEqual(whole['shots'][0], saved['shots'][0])
        with self.assertRaises(ValueError):
            scene_layout.scoped_blocks(saved, saved['shots'][0]['blocks'], 'block', saved['blocks'][0]['id'])


if __name__ == '__main__':
    unittest.main()
