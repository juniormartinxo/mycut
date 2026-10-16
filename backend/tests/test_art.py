"""Arte (ADR 0005): the director's visual bible becomes images, the bases first and attached to the others.
The external CLIs are fixtures, and the fake one saves its image where the runner would. Where a test only checks
that the production goes on to the voice and the video, ElevenLabs and the renderer are skipped too: the Short livre
tests render for real."""
import copy
import io
import json
import unittest
from unittest.mock import patch
from PIL import Image
import test_studio  # Sets isolated DATA before the application modules are imported.
from mycut import bridge, elevenlabs, integrations, pipeline, production, store, worker
from mycut.models import ProjectInput
from mycut.config import DATA
import test_free_short as free  # Imported as a module so its tests are not collected twice.
from test_free_short import FREE_SCRIPT, APPROVED, free_direction

BIBLE = {'tone': 'Ficção científica intimista: azul-petróleo frio contra o âmbar quente da flor.',
         'sheets': [{'kind': 'character', 'name': 'Comandante Ira Vale',
                     'description': '38 anos, 172 cm, olhos cinza-esverdeados, cicatriz de 3 cm na sobrancelha esquerda.'},
                    {'kind': 'setting', 'name': 'Nave Halcyon', 'description': 'Corredor cilíndrico de alumínio escovado.'}]}
REQUESTS = [
    {'key': 'ira', 'base': True, 'title': 'Ficha da Comandante Ira Vale', 'aspect': '3:2', 'references': [],
     'prompt': 'Studio character reference sheet, 85mm lens, Commander Ira Vale, 38-year-old woman --ar 3:2'},
    {'key': 'corredor', 'base': True, 'title': 'Corredor vazio da Halcyon', 'aspect': '9:16', 'references': [],
     'prompt': 'Wide establishing shot, 24mm lens, abandoned spaceship corridor, empty, no people'},
    {'key': 'ira-corredor', 'base': False, 'title': 'Ira avança pelo corredor', 'aspect': '9:16',
     'references': ['ira', 'corredor'], 'prompt': 'Medium shot, 50mm lens, Commander Ira Vale pulls herself along the rail'},
]


def art_background(key, motion='zoom_in', dim=30):
    return {'kind': 'image', 'color': None, 'color_to': None, 'angle': 0, 'image_id': None, 'art': key,
            'motion': motion, 'dim': dim}


def art_direction():
    """The reference prompt's bible: Ira's sheet in Etapa 2, the empty corridor in Etapa 3 and both in Etapa 4."""
    direction = free_direction()
    direction['bible'], direction['images'] = BIBLE, copy.deepcopy(REQUESTS)
    scenes = direction['scenes']
    scenes[3]['shots'][0]['blocks'][1]['object'] = {
        'type': 'image', 'text': '', 'font_size': 16, 'color': None, 'align': 'center', 'reveal': 'none',
        'image_id': None, 'art': 'ira', 'motion': 'zoom_in', 'flow': None}
    scenes[4]['shots'][0]['background'] = art_background('corredor')
    scenes[5]['shots'][0]['background'] = art_background('ira-corredor', 'pan_left', 20)
    return direction


def png(color, size=(96, 64)):
    out = io.BytesIO()
    Image.new('RGB', size, color).save(out, format='PNG')
    return out.getvalue()


class FakeCLI:
    """Text agents answer from `replies`; image requests save one PNG like the runner and are recorded."""
    def __init__(self, replies, fail=()):
        self.replies, self.fail, self.images, self.texts = list(replies), set(fail), [], []

    def __call__(self, config, prompt, schema, web=False, timeout=900, request_id=None, attachments=(), images=False):
        if not images:
            self.texts.append(prompt)
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        # The first pixel of each attachment, read while the call runs: examples are deleted after the job.
        self.images.append({'config': config, 'prompt': prompt, 'attachments': [str(path) for path in attachments],
                            'pixels': [Image.open(path).convert('RGB').getpixel((0, 0)) for path in attachments]})
        if len(self.images) in self.fail:
            raise ValueError('O CLI recusou a imagem.')
        folder = bridge.BRIDGE/'requests'/request_id/'outputs'
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'1.png').write_bytes(png((40 * len(self.images) % 255, 90, 120)))
        # The runner's answer: the CLI reported no token usage for the image call.
        bridge.atomic_json(bridge.BRIDGE/'requests'/request_id/'response.json', {'result': {}, 'usage': []})
        return {'message': 'Imagem criada.'}


class ArtTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    online = free.FreeShortTests.online
    create_free = free.FreeShortTests.create_free

    def start(self, kind='plan', art='all'):
        self.online()
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {**json.loads((bridge.BRIDGE/'heartbeat.json').read_text()),
                                                            'protocol': bridge.IMAGES_PROTOCOL})
        response = self.create_free(automation=kind, art=art)
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()
        store.claim()
        return project, store.get_job(project['jobs'][0]['id'], private=True)

    def image_of(self, project, key):
        request = next(item for item in project['art']['requests'] if item['key'] == key)
        return next(item for item in project['images'] if item['id'] == request['image_id'])

    def test_bases_are_generated_first_and_attached_to_the_images_that_reference_them(self):
        project, job = self.start()
        cli = FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual(saved['art']['bible'], BIBLE)
        self.assertEqual([item['state'] for item in saved['art']['requests']], ['generated'] * 3)
        ira, corridor, both = (self.image_of(saved, key) for key in ('ira', 'corredor', 'ira-corredor'))
        # The character sheet and the empty corridor come first, with no reference; the scene gets both attached.
        self.assertIn('Commander Ira Vale, 38-year-old woman', cli.images[0]['prompt'])
        self.assertIn('abandoned spaceship corridor', cli.images[1]['prompt'])
        self.assertEqual([call['attachments'] for call in cli.images[:2]], [[], []])
        self.assertEqual(cli.images[2]['attachments'], [str(DATA/ira['path']), str(DATA/corridor['path'])])
        self.assertIn('cicatriz de 3 cm', cli.images[2]['prompt'], 'Every image carries the visual bible.')
        self.assertEqual({call['config']['provider'] for call in cli.images}, {'codex'})
        # Each image takes the place the director gave it.
        scenes = saved['scenes']
        sheet = scenes[3]['blocks'][1]['object']
        self.assertEqual((sheet['type'], sheet['asset_id'], sheet['motion']), ('image', ira['id'], 'zoom_in'))
        self.assertEqual({k: scenes[4]['background'][k] for k in ('kind', 'asset_id', 'motion', 'dim')},
                         {'kind': 'image', 'asset_id': corridor['id'], 'motion': 'zoom_in', 'dim': 30})
        self.assertEqual(scenes[5]['background']['asset_id'], both['id'])
        self.assertEqual(next(s['state'] for s in store.get_job(job['id'])['steps'] if s['name'] == 'art'), 'succeeded')

    def test_by_default_only_the_bases_are_generated_and_the_production_waits_with_the_estimate(self):
        project, job = self.start('pipeline', 'bases')
        seen = []
        cli = FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])

        def invoke(*args, **kwargs):
            if kwargs.get('images'):
                seen.append(store.get_project(project['id'])['art'].get('estimate'))
            return cli(*args, **kwargs)
        with patch.object(bridge, 'invoke', side_effect=invoke), patch.object(elevenlabs, 'synthesize') as voice:
            pipeline.produce(job)
            voice.assert_not_called()
        # The estimate was saved before the first image was asked for: 2 bases at US$ 0,05.
        self.assertEqual(seen[0], {'images': 2, 'provider': 'codex', 'usd_per_image': .05, 'usd': .1})
        self.assertEqual(len(cli.images), 2)
        saved = store.get_project(project['id'])
        self.assertEqual([(item['key'], item['state']) for item in saved['art']['requests']],
                         [('ira', 'generated'), ('corredor', 'generated'), ('ira-corredor', 'pending')])
        self.assertEqual(saved['art']['then'], 'pipeline')
        self.assertIsNone(saved['scenes'][5].get('background'), 'A pending image leaves the project background.')
        ProjectInput.model_validate({key: saved[key] for key in ('title', 'scenes', 'visual_style')})
        art_step = next(s for s in store.get_job(job['id'])['steps'] if s['name'] == 'art')
        self.assertEqual(art_step['state'], 'succeeded')
        self.assertNotIn('voice', {s['name'] for s in store.get_job(job['id'])['steps']})

    def stopped_message(self, direction, fail=(), kind='pipeline'):
        """The message the worker finishes a production with when it stopped in the Arte tab."""
        project, job = self.start(kind, 'bases')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, direction, APPROVED], fail=fail)):
            pipeline.produce(job)
        return worker.final_message(store.get_job(job['id']), None)

    def test_the_stopped_production_says_what_happened_to_the_bases(self):
        for kind in ('pipeline', 'plan'):
            self.assertEqual(self.stopped_message(art_direction(), kind=kind),
                             'Imagens-base prontas: confira e oriente na aba Arte')
            self.assertEqual(self.stopped_message(art_direction(), fail={1, 2}, kind=kind),
                             'As imagens-base não puderam ser geradas: veja os avisos e refaça na aba Arte')
        self.assertEqual(self.stopped_message(art_direction(), fail={1}),
                         '1 de 2 imagens-base prontas: veja os avisos e refaça as demais na aba Arte')
        without_bases = art_direction()
        without_bases['images'] = [{**REQUESTS[2], 'references': []}]
        for scene in (3, 4):
            without_bases['scenes'][scene] = free_direction()['scenes'][scene]
        self.assertEqual(self.stopped_message(without_bases),
                         'Nenhuma imagem-base para conferir: gere as imagens das cenas na aba Arte')
        # A plan that did not stop keeps its usual message.
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        self.assertEqual(worker.final_message(store.get_job(job['id']), None), 'Roteiro e cenas prontos')

    def produce_bases(self, kind='pipeline'):
        project, job = self.start(kind, 'bases')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Imagens-base prontas')
        return store.get_project(project['id'])

    def test_the_remaining_images_get_the_bases_attached_and_the_short_goes_on_to_voice_and_video(self):
        project = self.produce_bases()
        response = self.client.post(f'/api/projects/{project["id"]}/art', json={'revision': project['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()['kind'], 'art')
        job = store.claim()
        cli = FakeCLI([])
        record = {'path': 'x.wav', 'script_hash': store.script_hash(project)}
        with patch.object(bridge, 'invoke', side_effect=cli), \
                patch.object(elevenlabs, 'synthesize', return_value=record) as voice, \
                patch.object(production, 'make_video', return_value={'duration': 58}) as video:
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual(len(cli.images), 1)
        self.assertEqual(cli.images[0]['attachments'],
                         [str(DATA/self.image_of(saved, key)['path']) for key in ('ira', 'corredor')])
        self.assertEqual(saved['scenes'][5]['background']['asset_id'], self.image_of(saved, 'ira-corredor')['id'])
        self.assertIsNone(saved['art']['then'])
        voice.assert_called_once()
        video.assert_called_once()

    def test_nothing_to_generate_or_a_format_project_is_refused(self):
        self.online()
        response = self.client.post(f'/api/projects/{self.project["id"]}/art', json={'revision': self.project['revision']})
        self.assertEqual(response.status_code, 422, response.text)

    def test_guidance_and_an_example_redo_one_image_and_the_new_version_takes_its_places(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        before = store.get_project(project['id'])
        old = self.image_of(before, 'ira')
        response = self.client.post(f'/api/projects/{project["id"]}/art/ira', data={
            'text': 'Cabelo mais curto e a cicatriz bem visível', 'revision': str(before['revision'])},
            files=[('files', ('exemplo.png', png('#ffcc00'), 'image/png'))])
        self.assertEqual(response.status_code, 202, response.text)
        cli = FakeCLI([])
        job = store.claim()
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        new = self.image_of(saved, 'ira')
        self.assertNotEqual(new['id'], old['id'])
        self.assertNotIn(old['id'], {item['id'] for item in saved['images']})
        self.assertIn('Cabelo mais curto e a cicatriz bem visível', cli.images[0]['prompt'])
        previous, example = cli.images[0]['attachments']
        self.assertEqual(previous, str(DATA/old['path']))
        self.assertEqual(cli.images[0]['pixels'][1], (255, 204, 0))
        self.assertFalse((DATA/'projects'/project['id']/'art-inputs').exists() and
                         any((DATA/'projects'/project['id']/'art-inputs').iterdir()), 'Examples do not outlive the job.')
        self.assertEqual(saved['scenes'][3]['blocks'][1]['object']['asset_id'], new['id'])
        requests = {item['key']: item for item in saved['art']['requests']}
        self.assertEqual(requests['ira']['messages'], [{'text': 'Cabelo mais curto e a cicatriz bem visível', 'attachments': 1}])
        # The scene image made with the previous sheet is flagged, not redone behind the author's back.
        self.assertEqual((requests['ira-corredor']['outdated'], requests['corredor']['outdated']), (True, False))
        self.assertEqual(len(saved['images']), 3)

    def test_guidance_needs_a_known_image_some_text_and_the_bases_it_references(self):
        project = self.produce_bases('plan')
        failed = {**project['art'], 'requests': [{**item, 'state': 'failed', 'image_id': None} if item['key'] == 'corredor'
                                                 else item for item in project['art']['requests']]}
        project = store.update_project(project['id'], {'art': failed}, project['revision'])
        for key, text in (('nao-existe', 'Mais luz'), ('ira', ' '), ('ira-corredor', 'Mais luz')):
            response = self.client.post(f'/api/projects/{project["id"]}/art/{key}',
                                        data={'text': text, 'revision': str(project['revision'])})
            self.assertEqual(response.status_code, 422, response.text)

    def test_each_generated_image_is_recorded_in_the_costs_at_the_price_per_image(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        calls = [call for version in self.client.get(f'/api/projects/{project["id"]}/usage').json()['versions']
                 for call in version['calls'] if call['step'] == 'art']
        self.assertEqual([(c['images'], c['usd'], c['cost_source'], c['state']) for c in calls],
                         [(1, .05, 'imagem', 'succeeded')] * 3)
        pricing = self.client.get('/api/integrations').json()['pricing']
        self.addCleanup(integrations.save_section, 'pricing', copy.deepcopy(integrations.DEFAULTS['pricing']))
        response = self.client.put('/api/integrations/pricing', json={
            **{k: pricing[k] for k in ('usd_brl', 'elevenlabs_usd_per_1k_credits', 'models')}, 'images': {'codex': .2, 'grok': None}})
        self.assertEqual(response.status_code, 200, response.text)
        usage = self.client.get(f'/api/projects/{project["id"]}/usage').json()
        self.assertEqual(usage['total']['images'], 3)
        self.assertAlmostEqual(sum(c['usd'] for v in usage['versions'] for c in v['calls'] if c['step'] == 'art'), .6)

    def test_a_failed_image_is_an_agent_warning_and_the_production_goes_on(self):
        project, job = self.start('pipeline', 'all')
        cli = FakeCLI([FREE_SCRIPT, art_direction(), APPROVED], fail={2})
        record = {'path': 'x.wav', 'script_hash': ''}
        with patch.object(bridge, 'invoke', side_effect=cli), \
                patch.object(elevenlabs, 'synthesize', return_value=record) as voice, \
                patch.object(production, 'make_video', return_value={'duration': 58}):
            pipeline.produce(job)
        voice.assert_called_once()
        saved = store.get_project(project['id'])
        states = {item['key']: item['state'] for item in saved['art']['requests']}
        # Without the corridor, Ira's scene would lose its setting: it waits for the base instead of being paid for.
        self.assertEqual(states, {'ira': 'generated', 'corredor': 'failed', 'ira-corredor': 'failed'})
        self.assertEqual(len(cli.images), 2)
        self.assertIn('Arte: a imagem “Corredor vazio da Halcyon” não pôde ser gerada (O CLI recusou a imagem.).',
                      saved['warnings'])
        self.assertIn('Arte: a imagem “Ira avança pelo corredor” não pôde ser gerada (gere antes a imagem-base '
                      '“Corredor vazio da Halcyon”.).', saved['warnings'])
        self.assertIsNone(saved['scenes'][4].get('background'))
        step = next(s for s in store.get_job(job['id'])['steps'] if s['name'] == 'art')
        self.assertEqual((step['state'], step['message']), ('succeeded', 'Arte · 1 de 3 imagens geradas · 2 com falha'))

    def test_the_arte_role_takes_only_clis_that_generate_images(self):
        agents = self.client.get('/api/integrations').json()['agents']
        self.addCleanup(integrations.save_section, 'agents', copy.deepcopy(integrations.DEFAULTS['agents']))
        self.assertEqual(agents['art'], {'provider': 'codex', 'model': ''})
        refused = self.client.put('/api/integrations/agents', json={**agents, 'art': {'provider': 'claude', 'model': ''}})
        self.assertEqual(refused.status_code, 422, refused.text)
        saved = self.client.put('/api/integrations/agents', json={**agents, 'art': {'provider': 'grok', 'model': ''}})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['agents']['art']['provider'], 'grok')

    def test_unknown_references_get_one_correction_and_are_then_dropped(self):
        project, job = self.start('plan', 'bases')
        flawed = art_direction()
        flawed['images'][2]['references'] = ['ira', 'nao-existe']
        flawed['scenes'][6]['shots'][0]['background'] = art_background('sumiu')
        cli = FakeCLI([FREE_SCRIPT, flawed, flawed, APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        self.assertIn('“nao-existe” não é uma imagem-base anterior', cli.texts[2])
        self.assertIn('scenes[6].shots[0].background: use em art a key', cli.texts[2])
        saved = store.get_project(project['id'])
        requests = {item['key']: item for item in saved['art']['requests']}
        self.assertEqual(requests['ira-corredor']['references'], ['ira'])
        self.assertIsNone(saved['scenes'][6].get('background'))

    def test_without_generated_images_the_director_gets_no_arte_and_nothing_is_generated(self):
        project, job = self.start('plan', 'none')
        cli = FakeCLI([FREE_SCRIPT, free_direction(), APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        self.assertIn('"art": null', cli.texts[1])
        self.assertEqual(cli.images, [])
        saved = store.get_project(project['id'])
        self.assertEqual((saved['art']['mode'], saved['art']['requests']), ('none', []))
        self.assertNotIn('art', {s['name'] for s in store.get_job(job['id'])['steps']})

    def test_the_production_resumes_from_the_voice_when_it_failed_after_the_images(self):
        project = self.produce_bases()
        self.client.post(f'/api/projects/{project["id"]}/art', json={'revision': project['revision']})
        job = store.claim()
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([])), \
                patch.object(elevenlabs, 'synthesize', side_effect=ValueError('ElevenLabs fora do ar')):
            with self.assertRaisesRegex(ValueError, 'fora do ar'):
                pipeline.produce(job)
        store.finish(job['id'], 'failed', 'ElevenLabs fora do ar')
        saved = store.get_project(project['id'])
        self.assertEqual(saved['art']['then'], 'pipeline', 'The production still has to go on.')
        response = self.client.post(f'/api/projects/{project["id"]}/art', json={'revision': saved['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        cli = FakeCLI([])
        record = {'path': 'x.wav', 'script_hash': ''}
        with patch.object(bridge, 'invoke', side_effect=cli), patch.object(elevenlabs, 'synthesize', return_value=record), \
                patch.object(production, 'make_video', return_value={'duration': 58}) as video:
            pipeline.produce(store.claim())
        self.assertEqual(cli.images, [])
        video.assert_called_once()
        self.assertIsNone(store.get_project(project['id'])['art']['then'])

    def test_requests_beyond_the_limit_are_corrected_and_then_dropped(self):
        project, job = self.start('plan', 'bases')
        crowded = art_direction()
        crowded['images'] += [{**REQUESTS[0], 'key': f'extra-{i}', 'base': False, 'references': ['ira']} for i in range(11)]
        for i in range(11):
            crowded['scenes'][i % 7]['shots'].append(free.plano([{'height': 100, 'object': {
                **art_direction()['scenes'][3]['shots'][0]['blocks'][1]['object'], 'art': f'extra-{i}'}}]))
        cli = FakeCLI([FREE_SCRIPT, crowded, crowded, APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        self.assertIn('images: peça até 12 imagens', cli.texts[2])
        saved = store.get_project(project['id'])
        self.assertEqual(len(saved['art']['requests']), 12)
        self.assertEqual(len(saved['scenes']), 7, 'The direction is kept, not replaced by the fallback.')

    def test_a_new_production_drops_the_previous_arte_images_the_new_scenes_do_not_use(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        before = store.get_project(project['id'])
        self.assertEqual(len(before['images']), 3)
        response = self.client.post(f'/api/projects/{project["id"]}/run',
                                    json={'kind': 'plan', 'mode': 'final', 'revision': before['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, free_direction(), APPROVED])):
            pipeline.produce(store.claim())
        saved = store.get_project(project['id'])
        self.assertEqual(saved['images'], [], 'Images nothing uses anymore leave the library.')

    def test_an_earlier_arte_image_cited_only_as_a_reference_stays_and_is_attached(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        before = store.get_project(project['id'])
        sheet = self.image_of(before, 'ira')
        again = free_direction()
        again['images'] = [{**REQUESTS[2], 'key': 'ira-de-novo', 'references': [sheet['id']]}]
        again['scenes'][5]['shots'][0]['background'] = art_background('ira-de-novo')
        self.client.post(f'/api/projects/{project["id"]}/run', json={'kind': 'plan', 'mode': 'final', 'revision': before['revision']})
        cli = FakeCLI([FREE_SCRIPT, again, APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(store.claim())
        saved = store.get_project(project['id'])
        self.assertEqual([image['id'] for image in saved['images'] if image.get('art') != 'ira-de-novo'], [sheet['id']])
        self.assertEqual(cli.images[0]['attachments'], [str(DATA/sheet['path'])])

    def test_a_redone_image_does_not_come_back_to_a_block_the_author_emptied(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, art_direction(), APPROVED])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        current = store.get_project(project['id'])
        scenes = copy.deepcopy(current['scenes'])
        scenes[3]['blocks'][1]['object'] = None
        current = store.update_project(project['id'], {'scenes': scenes}, current['revision'])
        self.client.post(f'/api/projects/{project["id"]}/art/ira', data={'text': 'Mais luz', 'revision': str(current['revision'])})
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([])):
            pipeline.produce(store.claim())
        self.assertIsNone(store.get_project(project['id'])['scenes'][3]['blocks'][1]['object'])


if __name__ == '__main__':
    unittest.main()
