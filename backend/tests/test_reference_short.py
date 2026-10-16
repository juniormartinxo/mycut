"""Short livre ponta a ponta (MYC-8): the reference prompt "Da Ideia ao Filme com IA" from New to later editing.

The prompt goes in whole, as the author pastes it. Only what is outside the MyCut is simulated: the agents' CLIs answer
from reference_agents and ElevenLabs speaks at a natural pace. Everything else (jobs, Arte, lista de materiais, voice,
render, editor and the agent's proposals) is the real code."""
import base64
import copy
import io
import json
import subprocess
import unittest
from unittest.mock import patch
from PIL import Image
import test_studio  # Sets isolated DATA before the application modules are imported.
from mycut import bridge, elevenlabs, pipeline, scene_chat, store, worker
from mycut.block_render import validate_project
from mycut.config import DATA
from mycut.production import make_video
import reference_agents as reference
from reference_agents import BLOCKS, BROLLS, PROMPT
import test_art as art
from test_art import FakeCLI
from test_scene_shots import difference

PACE = 15  # Characters per second: about 2.7 words per second, ElevenLabs' natural pace in Portuguese.


def natural_voice(requests):
    """ElevenLabs HTTP: a tone as long as the text takes to say at PACE, with the character times over it."""
    def api(key, method, path, meta=None, **kwargs):
        text = kwargs['json']['text']
        requests.append(text)
        length = len(text) / PACE
        mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency=330:duration={length}',
                              '-f', 'mp3', 'pipe:1'], capture_output=True, check=True).stdout
        step = length / len(text)
        meta['credits'] = float(len(text))
        return {'audio_base64': base64.b64encode(mp3).decode(), 'normalized_alignment': {
            'characters': list(text), 'character_start_times_seconds': [i*step for i in range(len(text))],
            'character_end_times_seconds': [(i+1)*step for i in range(len(text))]}}
    return api


def clip(color):
    path = DATA / f'broll-{color}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=180x320:d=6:r=30',
                    '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path.read_bytes()


def planos(scene):
    return [scene, *scene.get('shots', [])]


class ReferenceShortTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    online = art.ArtTests.online
    image_of = art.ArtTests.image_of

    def run_job(self, cli=None, voice=None):
        job = store.claim()
        with patch.object(bridge, 'invoke', side_effect=cli or FakeCLI([])), \
                patch.object(elevenlabs, 'api', side_effect=voice or AssertionError('Nenhuma voz neste passo.')):
            pipeline.produce(job)
        message = worker.final_message(store.get_job(job['id']), None)
        store.finish(job['id'], 'succeeded', message)
        return store.get_job(job['id']), message

    def planned(self):
        """New › Livre with the whole prompt and a reference image, script and scenes first, bases reviewed first;
        then the remaining images. Returns the project, the CLI of each job and the stop message."""
        self.online()
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {**json.loads((bridge.BRIDGE/'heartbeat.json').read_text()),
                                                            'protocol': bridge.IMAGES_PROTOCOL})
        body = {'brief': PROMPT, 'automation': 'plan', 'art': 'bases'}
        response = self.client.post('/api/projects/free', data={'project': json.dumps(body)},
                                    files=[('files', ('ira-referencia.png', art.png('#335566'), 'image/png'))])
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()
        first = FakeCLI([reference.script(), reference.direction(), reference.APPROVED])
        self.production, stopped = self.run_job(first)
        response = self.client.post(f'/api/projects/{project["id"]}/art',
                                    json={'revision': store.get_project(project['id'])['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        rest = FakeCLI([])
        self.run_job(rest)
        return store.get_project(project['id']), first, rest, stopped

    def test_the_reference_prompt_is_followed_without_sources_with_planos_bases_first_and_its_lista_de_materiais(self):
        project, first, rest, stopped = self.planned()
        # Script, direction and conference only: an authorial prompt is never refused for lack of sources.
        self.assertEqual(len(first.texts), 3)
        self.assertIn(json.dumps(PROMPT, ensure_ascii=False), first.texts[0])
        self.assertIn(json.dumps(PROMPT, ensure_ascii=False), first.texts[2])
        steps = {s['name']: s['state'] for s in self.production['steps']}
        self.assertEqual(steps['research'], 'skipped')
        self.assertEqual(project['warnings'], [])
        # The seven blocks in order, with the narration and the text on screen of the prompt.
        scenes = project['scenes']
        self.assertEqual([s['narration'] for s in scenes], [narration for _, narration, _, _ in BLOCKS])
        titles = [next(b['object']['text'] for p in planos(s) for b in p['blocks'] if b['object'] and b['object']['type'] == 'title')
                  for s in scenes]
        self.assertEqual(titles, [screen for _, _, screen, _ in BLOCKS])
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
        self.assertEqual([call['attachments'] for call in first.images], [[], []])
        self.assertEqual(stopped, 'Imagens-base prontas: confira e oriente na aba Arte · faltam 6 clipes de B-roll '
                                  '(B-roll 1, B-roll 2, B-roll 3, B-roll 4, B-roll 5, B-roll 6): veja a aba Materiais')
        paths = {key: str(DATA/self.image_of(project, key)['path']) for key in ('ira', 'corredor')}
        self.assertEqual([call['attachments'] for call in rest.images],
                         [[], [paths['ira'], paths['corredor']], [paths['ira']], [paths['ira'], paths['corredor']]])
        self.assertTrue(all('cicatriz diagonal de 3 cm' in call['prompt'] for call in first.images + rest.images))
        self.assertEqual({item['state'] for item in project['art']['requests']}, {'generated'})
        self.assertIn('ira-referencia.png', [item['name'] for item in project['images']])
        # The six B-rolls with prompt, tool, references and duration, each waiting in its planos.
        listed = self.client.get(f'/api/projects/{project["id"]}').json()['brolls']
        self.assertEqual([{k: item[k] for k in ('key', 'prompt', 'tool', 'references', 'seconds')} for item in listed],
                         [{k: item[k] for k in ('key', 'prompt', 'tool', 'references', 'seconds')} for item in BROLLS])
        self.assertEqual({item['key']: [(p['scene'], p['shot']) for p in item['places']] for item in listed},
                         {'rostos': [(1, 1), (1, 2)], 'retrato': [(4, 4)], 'corredor-vivo': [(3, 1), (3, 2), (5, 1), (5, 2)],
                          'ira-avanca': [(6, 4)], 'flor': [(7, 1)], 'porta': [(7, 2)]})
        self.assertTrue(all(place['waiting'] for item in listed for place in item['places']))
        # The publication package the prompt asks for.
        self.assertEqual(project['publication'], {'titles': reference.TITLES, 'description': reference.script()['description'],
                                                  'hashtags': reference.HASHTAGS, 'pinned_comment': reference.PINNED})
        validate_project(project)

    def test_the_author_edits_the_speech_before_the_voice_and_the_short_lasts_what_is_said(self):
        project, _, _, _ = self.planned()
        # The author has the last word on the speech: edited in the script before any credit is spent.
        scenes = copy.deepcopy(project['scenes'])
        scenes[1]['narration'] = 'É que você pula a pré-produção. Olha: tudo começa com uma frase bem simples.'
        response = self.client.put(f'/api/projects/{project["id"]}', json={
            'title': project['title'], 'scenes': scenes, 'visual_style': project['visual_style'],
            'accent': project['accent'], 'revision': project['revision']})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(f'/api/projects/{project["id"]}/run', json={'kind': 'voice', 'revision': response.json()['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        spoken = []
        self.run_job(voice=natural_voice(spoken))
        self.assertIn('uma frase bem simples.', spoken[0])
        project = self.client.get(f'/api/projects/{project["id"]}').json()
        self.assertTrue(project['audio_matches_script'])
        # The clips made outside arrive: a video for Ira in the corridor, an image for the three faces.
        response = self.client.post(f'/api/projects/{project["id"]}/brolls/ira-avanca/clip', params={'revision': project['revision']},
                                    files={'file': ('ira-avanca.mp4', clip('red'), 'video/mp4')})
        self.assertEqual(response.status_code, 200, response.text)
        project = response.json()
        self.project = project
        store.enqueue(project['id'], 'preview', project['revision'])
        job = store.claim()
        folder = DATA / make_video(job)['directory']
        store.finish(job['id'], 'succeeded', 'Pronto')
        timing = json.loads((folder/'timing.json').read_text())
        # The Short lasts what the voice says, plus the pause: no silence is added to reach the prompt's times.
        said = sum(len(text) for text in spoken) / PACE + reference.PAUSE['seconds']
        self.assertAlmostEqual(timing['duration_seconds'], said, delta=.3)
        self.assertEqual(len(timing['scenes']), 7)
        # Cuts every 1,5 to 3 s of speech; only the Short's last plano holds the loop's closing frame too.
        lengths = []
        for index, scene in enumerate(project['scenes']):
            for window in self.inspect(scene)['shots']:
                lengths.append(round(window['end'] - window['start'], 2))
        self.assertEqual(len(lengths), 19)
        self.assertTrue(all(1.5 <= length <= 3 for length in lengths[:-1]), lengths)
        # Captions of 2 to 4 words, all of the speech, keywords in the accent.
        captions = timing['captions']
        self.assertTrue(all(2 <= len(c['text'].split()) <= 4 for c in captions), captions)
        self.assertEqual(' '.join(c['text'] for c in captions), ' '.join(s['narration'] for s in project['scenes']))
        # Preview and MP4 match at the same instants: the revealed sheet, the imported clip and a caption over a B-roll.
        sheet = project['scenes'][3]['shots'][0]['id']
        moving = project['scenes'][5]['shots'][2]['id']
        for scene_index, shot_id in ((3, sheet), (5, moving), (2, project['scenes'][2]['id'])):
            bounds = timing['scenes'][scene_index]
            window = next(w for w in self.inspect(project['scenes'][scene_index])['shots'] if w['id'] == shot_id)
            t = round((bounds['start'] + (window['start'] + window['end'] * 2) / 3) * 24) / 24
            frame = self.mp4_frame(folder, t)
            preview = self.preview_frame(project['scenes'][scene_index], t - bounds['start'])
            self.assertLess(difference(frame, preview), 2, (scene_index, t))
            if shot_id == moving:
                red = sum(1 for p in frame.crop((40, 100, 500, 300)).get_flattened_data() if p[0] > 200 and p[1] < 60)
                self.assertGreater(red, 30000, 'The imported clip fills the plano of its B-roll.')

    def test_the_short_opens_in_the_editor_and_takes_manual_changes_and_the_agents_proposals(self):
        project, _, _, _ = self.planned()
        self.project = project
        scene = project['scenes'][3]
        target = scene['shots'][0]['blocks'][1]['object']
        body = scene_chat.MessageRequest(scene_id=scene['id'], scope='object', target_id=target['id'],
                                         text='Destaque os números da ficha.', revision=project['revision'])
        with patch.object(scene_chat.bridge, 'require'), patch.object(scene_chat.agent_models, 'validate'):
            job_id = scene_chat.enqueue(project['id'], body)['id']
        proposed = copy.deepcopy(scene['shots'][0]['blocks'])
        proposed[1]['object']['text'] = 'Idade: 38\nAltura: 172 cm\nPeso: 64 kg\nCicatriz: 3 cm'
        proposed[1]['object']['color'] = reference.ACCENT
        with patch('mycut.pipeline.agent', return_value=scene_chat.Proposal(reply='Números em âmbar.', blocks=proposed)):
            scene_chat.run(store.get_job(job_id, private=True))
        store.finish(job_id, 'succeeded', 'Proposta pronta', {'reply': 'Números em âmbar.', 'blocks': proposed})
        accepted = self.client.post(f'/api/projects/{project["id"]}/scene-proposals/{job_id}',
                                    json={'decision': 'accepted', 'revision': project['revision']})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        saved = accepted.json()['scenes'][3]
        self.assertEqual(saved['shots'][0]['blocks'][1]['object']['text'].split('\n')[0], 'Idade: 38')
        self.assertEqual(saved['shots'][0]['blocks'][1]['object']['reveal'], 'lines')
        self.assertEqual([saved['blocks'], saved['shots'][1:]], [scene['blocks'], scene['shots'][1:]])
        # A manual change in the editor: the author shortens the hook's title and moves its plano.
        edited = copy.deepcopy(accepted.json())
        hook = edited['scenes'][0]
        hook['blocks'][0]['object']['text'] = 'NÃO É A IA'
        hook['shots'][0], hook['shots'][1] = hook['shots'][1], hook['shots'][0]
        response = self.client.put(f'/api/projects/{project["id"]}', json={
            'title': edited['title'], 'scenes': edited['scenes'], 'visual_style': edited['visual_style'],
            'accent': edited['accent'], 'revision': edited['revision']})
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved['scenes'][0]['blocks'][0]['object']['text'], 'NÃO É A IA')
        validate_project(store.get_project(project['id']))

    def inspect(self, scene):
        response = self.client.post('/api/scene-layout/inspect', json={
            'scene': scene, 'project_id': self.project['id'], 'accent': self.project['accent'],
            'visual_style': self.project['visual_style']})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def mp4_frame(self, folder, t, fps=24):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(folder/'short.mp4'), '-vf', f'select=eq(n\\,{round(t*fps)})',
                                       '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', 'pipe:1'])
        with Image.open(io.BytesIO(raw)) as image:
            return image.convert('RGB')

    def preview_frame(self, scene, t):
        response = self.client.post('/api/scene-preview', json={'scene': scene, 'project_id': self.project['id'],
                                    'accent': self.project['accent'], 'visual_style': self.project['visual_style'],
                                    'elapsed': t, 'width': 'full'})
        self.assertEqual(response.status_code, 200, response.text)
        with Image.open(io.BytesIO(response.content)) as image:
            return image.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS)


if __name__ == '__main__':
    unittest.main()
