"""Short livre ponta a ponta (MYC-8): the reference prompt "Da Ideia ao Filme com IA" from New to later editing.

The prompt goes in whole, as the author pastes it. Only what is outside the MyCut is simulated: the agents' CLIs answer
from reference_agents and ElevenLabs speaks at a natural pace. Each job runs as the worker runs it (its module, then
the finish with result.json), only in this process; jobs, Arte, lista de materiais, voice, render, editor and the
agent's proposals are the real code."""
import copy
import io
import json
import unittest
from unittest.mock import patch
from PIL import Image
import test_studio  # Sets isolated DATA before the application modules are imported.
from mycut import bridge, elevenlabs, integrations, pipeline, scene_chat, store, worker
from mycut.block_render import validate_project
from mycut.config import DATA
from mycut.production import make_video
import reference_agents as reference
from reference_agents import PASSAGES, BROLLS, PROMPT
import test_art as art
import test_free_short as free  # Imported as a module so its tests are not collected twice.
import test_materials as materials
from test_art import FakeCLI
from test_scene_shots import difference

PACE = 15  # Characters per second: about 2.7 words per second, a natural pace for ElevenLabs in Portuguese.
CAPTION_BAND = (0, 640, 465, 816)  # Captions at the bottom, in a 540×960 frame: above the bottom 15%, left of the buttons.


def planos(scene):
    return [scene, *scene.get('shots', [])]


def accent_pixels(image):
    return sum(1 for pixel in image.get_flattened_data()
               if all(abs(a-b) < 40 for a, b in zip(pixel, (0xf2, 0xb5, 0x44))))


class ReferenceShortTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    edit = test_studio.StudioTests.edit
    online = art.ArtTests.online
    image_of = art.ArtTests.image_of
    create_free = free.FreeShortTests.create_free
    mp4_frame = free.FreeShortTests.mp4_frame
    preview_frame = free.FreeShortTests.preview_frame
    clip = materials.MaterialsTests.clip

    def work(self, cli=None, voice=None, lane=False):
        """The next job of a worker lane (productions, or covers and scene proposals), with the CLIs answered by `cli`
        and ElevenLabs by `voice`."""
        job = store.claim(lane)
        run = scene_chat.run if job['kind'] == 'scene_edit' else pipeline.produce
        with patch.object(bridge, 'invoke', side_effect=cli or FakeCLI([])), \
                patch.object(elevenlabs, 'api', side_effect=voice or AssertionError('Nenhuma voz neste passo.')):
            run(job)
        output = json.loads((DATA/'projects'/job['project_id']/'renders'/job['id']/'result.json').read_text())
        store.finish(job['id'], 'succeeded', worker.final_message(store.get_job(job['id']), output), output)
        return store.get_job(job['id'])

    def planned(self):
        """New › Livre with the whole prompt and a reference image, script and scenes first, bases reviewed first;
        then the remaining images. Keeps each job's CLI and the production job."""
        self.online()
        # Settings outlive each test: the agents start as a new installation has them.
        integrations.save_section('agents', integrations.DEFAULTS['agents'])
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {**json.loads((bridge.BRIDGE/'heartbeat.json').read_text()),
                                                            'protocol': bridge.IMAGES_PROTOCOL})
        response = self.create_free([('ira-referencia.png', art.png('#335566'), 'image/png')], brief=PROMPT, art='bases')
        self.assertEqual(response.status_code, 201, response.text)
        self.project = response.json()
        self.production_cli = FakeCLI([reference.script(), reference.direction(), reference.APPROVED])
        self.production = self.work(self.production_cli)
        response = self.client.post(f'/api/projects/{self.project["id"]}/art',
                                    json={'revision': self.current()['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        self.arte_cli = FakeCLI([])
        self.work(self.arte_cli)
        return self.current()

    def first_pixel(self, project, key):
        response = self.client.get(self.image_of(project, key)['url'])
        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.content)) as image:
            return image.convert('RGB').getpixel((0, 0))

    def current(self):
        self.project = self.client.get(f'/api/projects/{self.project["id"]}').json()
        return self.project

    def test_the_reference_prompt_is_followed_without_sources_with_planos_bases_first_and_its_lista_de_materiais(self):
        project = self.planned()
        # Script, direction and conference only: an authorial prompt is never refused for lack of sources.
        steps = {s['name']: s['state'] for s in self.production['steps']}
        self.assertEqual(steps, {'writer': 'succeeded', 'research': 'skipped', 'director': 'succeeded',
                                 'reviewer': 'succeeded', 'art': 'succeeded'})
        self.assertIn(json.dumps(PROMPT, ensure_ascii=False), self.production_cli.texts[0])
        self.assertIn(json.dumps(PROMPT, ensure_ascii=False), self.production_cli.texts[-1], 'The conference reads the prompt.')
        self.assertEqual(project['warnings'], [])
        # The prompt's seven passages in order, with their narration and text on screen.
        scenes = project['scenes']
        self.assertEqual([s['narration'] for s in scenes], [narration for _, narration, _, _ in PASSAGES])
        titles = [next(b['object']['text'] for p in planos(s) for b in p['blocks'] if b['object'] and b['object']['type'] == 'title')
                  for s in scenes]
        self.assertEqual(titles, [screen for _, _, screen, _ in PASSAGES])
        self.assertEqual(scenes[-1]['pauses'], [reference.PAUSE])
        # Full screen B-rolls, the split screen and the character sheet revealed line by line.
        self.assertEqual(sum(len(planos(s)) for s in scenes), 19)
        hook = scenes[0]
        self.assertEqual((hook['background']['kind'], hook['background']['broll'], hook['brand']), ('image', 'rostos', False))
        split = scenes[5]['shots'][1]
        self.assertEqual([(b['height'], b['object']['type']) for b in split['blocks']], [(50, 'image'), (50, 'image')])
        self.assertEqual([b['object']['asset_id'] for b in split['blocks']],
                         [self.image_of(project, key)['id'] for key in ('ira', 'corredor')])
        sheet = scenes[3]['shots'][0]['blocks'][1]['object']
        self.assertEqual((sheet['reveal'], sheet['text'].split('\n')[0]), ('lines', 'Idade: 38 anos'))
        # Teal and amber from the prompt's tone, with no format.
        style = project['visual_style']
        self.assertEqual((style['format_id'], style['background'], project['accent'], style['loop']),
                         ('free', reference.BACKGROUND, reference.ACCENT, True))
        # The bases came first with nothing attached, then the stop to review them; the rest carry them.
        self.assertEqual([call['attachments'] for call in self.production_cli.images], [[], []])
        self.assertEqual(self.production['message'],
                         'Imagens-base prontas: confira e oriente na aba Arte · faltam 6 clipes de B-roll '
                         '(B-roll 1, B-roll 2, B-roll 3, B-roll 4, B-roll 5, B-roll 6): veja a aba Materiais')
        # Each attachment is the base itself, as the project serves it.
        ira, corridor = (self.first_pixel(project, key) for key in ('ira', 'corredor'))
        self.assertEqual([call['pixels'] for call in self.arte_cli.images], [[], [ira, corridor], [ira], [ira, corridor]])
        self.assertNotEqual(ira, corridor)
        self.assertTrue(all('cicatriz diagonal de 3 cm' in call['prompt']
                            for call in self.production_cli.images + self.arte_cli.images))
        self.assertEqual({item['state'] for item in project['art']['requests']}, {'generated'})
        self.assertIn('ira-referencia.png', [item['name'] for item in project['images']])
        # The six B-rolls with prompt, tool, references and duration, each waiting in its planos.
        fields = ('key', 'prompt', 'tool', 'references', 'seconds')
        self.assertEqual([{k: item[k] for k in fields} for item in project['brolls']], [{k: item[k] for k in fields} for item in BROLLS])
        self.assertEqual({item['key']: [(p['scene'], p['shot']) for p in item['places']] for item in project['brolls']},
                         {'rostos': [(1, 1), (1, 2)], 'retrato': [(4, 4)], 'corredor-vivo': [(3, 1), (3, 2), (5, 1), (5, 2)],
                          'ira-avanca': [(6, 4)], 'flor': [(7, 1)], 'porta': [(7, 2)]})
        self.assertTrue(all(place['waiting'] for item in project['brolls'] for place in item['places']))
        # The publication package the prompt asks for.
        self.assertEqual(project['publication'], {'titles': reference.TITLES, 'description': reference.script()['description'],
                                                  'hashtags': reference.HASHTAGS, 'pinned_comment': reference.PINNED})
        validate_project(project)

    def test_the_author_edits_the_speech_before_the_voice_and_the_short_lasts_what_is_said(self):
        project = self.planned()
        # The author has the last word on the speech: edited in the script before any credit is spent.
        edited = 'É que você pula a pré-produção. Olha: tudo começa com uma frase bem simples.'
        self.assertEqual(self.edit(scenes=[project['scenes'][0], {**project['scenes'][1], 'narration': edited},
                                           *project['scenes'][2:]]).status_code, 200)
        response = self.client.post(f'/api/projects/{project["id"]}/run', json={'kind': 'voice', 'revision': self.project['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        requests = []
        self.work(voice=free.fake_voice(requests, PACE))
        spoken = [request['text'] for request in requests]
        self.assertIn(edited, spoken[0])
        self.assertTrue(self.current()['audio_matches_script'])
        # The clip made outside arrives for Ira in the corridor.
        response = self.client.post(f'/api/projects/{project["id"]}/brolls/ira-avanca/clip', params={'revision': self.project['revision']},
                                    files={'file': ('ira-avanca.mp4', self.clip('red'), 'video/mp4')})
        self.assertEqual(response.status_code, 200, response.text)
        project = self.project = response.json()
        store.enqueue(project['id'], 'preview', project['revision'])
        job = store.claim()
        folder = DATA / make_video(job)['directory']
        store.finish(job['id'], 'succeeded', 'Pronto')
        timing = json.loads((folder/'timing.json').read_text())
        # The Short lasts what the voice says, plus the pause: no silence is added to reach the prompt's 58 s.
        said = sum(len(text) for text in spoken) / PACE + reference.PAUSE['seconds']
        self.assertAlmostEqual(timing['duration_seconds'], said, delta=.3)
        self.assertLess(timing['duration_seconds'], 50)
        self.assertEqual(len(timing['scenes']), 7)
        # Cuts every 1,5 to 3 s of speech.
        windows = [[(w['start'], w['end']) for w in self.inspect(scene)['shots']] for scene in project['scenes']]
        lengths = [round(end - start, 2) for scene in windows for start, end in scene]
        self.assertEqual(len(lengths), 19)
        self.assertTrue(all(1.5 <= length <= 3 for length in lengths), lengths)
        # Captions of 2 to 4 words, all of the speech.
        captions = timing['captions']
        self.assertTrue(all(2 <= len(c['text'].split()) <= 4 for c in captions), captions)
        self.assertEqual(' '.join(c['text'] for c in captions), ' '.join(s['narration'] for s in project['scenes']))
        # Preview and MP4 match at the same instants: mid-reveal of the sheet, just after a cut, on the imported clip.
        def instant(scene, shot, at):
            start, end = windows[scene][shot]
            return round((timing['scenes'][scene]['start'] + start + (end - start) * at) * 24) / 24
        for scene, shot, at in ((3, 1, 1/3), (5, 1, .05), (5, 3, 2/3)):
            t = instant(scene, shot, at)
            frame = self.mp4_frame(folder, t)
            preview = self.preview_frame(project['scenes'][scene], t - timing['scenes'][scene]['start'])
            self.assertLess(difference(frame, preview), 2, (scene, shot, t))
            self.assertLess(difference(frame.crop(CAPTION_BAND), preview.crop(CAPTION_BAND)), 3, (scene, shot, t))
        red = sum(1 for p in frame.crop((40, 100, 500, 300)).get_flattened_data() if p[0] > 200 and p[1] < 60)
        self.assertGreater(red, 30000, 'The imported clip fills the plano of its B-roll.')
        # A keyword's caption is drawn in the accent, inside the safe area, the same in preview and MP4.
        keyword = next(c for c in captions if 'cenário' in c['text'].split()[-1])
        scene = next(i for i, b in enumerate(timing['scenes']) if b['start'] <= keyword['start'] < b['end'])
        t = round((keyword['start'] + keyword['end']) / 2 * 24) / 24
        frame = self.mp4_frame(folder, t)
        preview = self.preview_frame(project['scenes'][scene], t - timing['scenes'][scene]['start'])
        self.assertGreater(accent_pixels(frame.crop(CAPTION_BAND)), 30, keyword)
        self.assertLess(difference(frame.crop(CAPTION_BAND), preview.crop(CAPTION_BAND)), 3, keyword)

    def test_the_short_opens_in_the_editor_and_takes_manual_changes_and_the_agents_proposals(self):
        project = self.planned()
        scene = project['scenes'][3]
        target = scene['shots'][0]['blocks'][1]['object']
        response = self.client.post(f'/api/projects/{project["id"]}/scene-conversations', json={
            'scene_id': scene['id'], 'scope': 'object', 'target_id': target['id'], 'text': 'Destaque os números da ficha.',
            'revision': project['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        proposed = copy.deepcopy(scene['shots'][0]['blocks'])
        proposed[1]['object'].update(text='Idade: 38\nAltura: 172 cm\nPeso: 64 kg\nCicatriz: 3 cm', color=reference.ACCENT)
        director = FakeCLI([{'reply': 'Números em âmbar.', 'blocks': proposed}])
        job = self.work(director, lane=True)
        self.assertIn('Destaque os números da ficha.', director.texts[0])
        # Nothing changes until the author accepts.
        self.assertEqual(self.current()['scenes'][3], scene)
        accepted = self.client.post(f'/api/projects/{project["id"]}/scene-proposals/{job["id"]}',
                                    json={'decision': 'accepted', 'revision': project['revision']})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        saved = accepted.json()['scenes'][3]
        self.assertEqual(saved['shots'][0]['blocks'][1]['object']['text'].split('\n')[0], 'Idade: 38')
        self.assertEqual(saved['shots'][0]['blocks'][1]['object']['reveal'], 'lines')
        self.assertEqual([saved['blocks'], saved['shots'][1:]], [scene['blocks'], scene['shots'][1:]])
        # A manual change in the editor: the author shortens the hook's title and swaps its second and third planos.
        self.project = accepted.json()
        hook = copy.deepcopy(self.project['scenes'][0])
        hook['blocks'][0]['object']['text'] = 'NÃO É A IA'
        order = [shot['id'] for shot in hook['shots']][::-1]
        hook['shots'] = hook['shots'][::-1]
        self.assertEqual(self.edit(scenes=[hook, *self.project['scenes'][1:]]).status_code, 200)
        saved = self.current()['scenes'][0]
        self.assertEqual((saved['blocks'][0]['object']['text'], [shot['id'] for shot in saved['shots']]), ('NÃO É A IA', order))
        validate_project(store.get_project(project['id']))

    def inspect(self, scene):
        response = self.client.post('/api/scene-layout/inspect', json={
            'scene': scene, 'project_id': self.project['id'], 'accent': self.project['accent'],
            'visual_style': self.project['visual_style']})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()


if __name__ == '__main__':
    unittest.main()
