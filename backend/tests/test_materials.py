"""Lista de materiais (ADR 0005): the B-rolls in video a Short livre needs from tools the MyCut does not drive.
Each one waits in its plano on the Arte's image with camera motion until its clip is imported, and never blocks the
export. The external CLIs are fixtures, as in the Arte tests."""
import copy
import subprocess
import unittest
from unittest.mock import patch
import test_studio  # Sets isolated DATA before the application modules are imported.
from mycut import bridge, pipeline, store, worker
from mycut.config import DATA
from mycut.block_render import validate_project
import test_art as art
from test_art import FakeCLI, art_background, art_direction
from test_free_short import FREE_SCRIPT, APPROVED, free_direction

# The reference prompt's six B-rolls, in its table's order.
BROLLS = [
    {'key': 'rostos', 'title': 'Gancho: o mesmo personagem com 3 rostos', 'tool': 'Midjourney/Flux, 3 gerações',
     'references': [], 'seconds': 3,
     'prompt': 'Close-up portrait, 50mm lens, a female astronaut in a white spacesuit inside a spaceship --ar 9:16'},
    {'key': 'retrato', 'title': 'Etapa 2: retrato de estúdio da Ira', 'tool': 'Midjourney/Flux', 'references': [],
     'seconds': 4, 'prompt': 'Studio character reference sheet, 85mm lens, Commander Ira Vale --ar 3:2'},
    {'key': 'corredor-vivo', 'title': 'Corredor vivo', 'tool': 'Kling/Runway', 'references': ['corredor'], 'seconds': 5,
     'prompt': 'Wide shot, 24mm lens, slow dolly forward down an abandoned spaceship corridor, no people'},
    {'key': 'ira-avanca', 'title': 'Ira avança pelo corredor', 'tool': 'Kling/Runway', 'references': ['ira', 'corredor'],
     'seconds': 5, 'prompt': 'Medium shot, 50mm lens, tracking shot, Commander Ira Vale pulls herself forward'},
    {'key': 'flor', 'title': 'A flor nas luvas', 'tool': 'Kling/Luma', 'references': ['ira'], 'seconds': 4,
     'prompt': 'Macro close-up, 100mm lens, static camera, gloved hands cupping a glowing amber alien flower'},
    {'key': 'porta', 'title': 'A porta do módulo fecha', 'tool': 'Kling/Runway', 'references': ['ira', 'corredor'],
     'seconds': 4, 'prompt': 'Wide shot, 35mm lens, locked-off static camera, the pod hatch slides shut'},
]
# Images the Arte draws to hold the planos of the B-rolls that have no image among the bases yet.
STAND_INS = [
    {'key': 'rostos-still', 'base': False, 'title': 'Três rostos da astronauta', 'aspect': '9:16', 'references': [],
     'prompt': 'Close-up portrait of a female astronaut, helmet off, cinematic lighting'},
    {'key': 'flor-still', 'base': False, 'title': 'A flor nas luvas', 'aspect': '9:16', 'references': ['ira'],
     'prompt': 'Macro close-up of gloved hands cupping a glowing amber alien flower'},
    {'key': 'porta-still', 'base': False, 'title': 'A porta do módulo', 'aspect': '9:16', 'references': ['ira', 'corredor'],
     'prompt': 'Wide shot of a pod hatch closing at the end of a dark corridor'},
]


def broll_background(art_key, broll, motion='zoom_in', dim=20):
    return {**art_background(art_key, motion, dim), 'broll': broll}


def materials_direction():
    """The Arte's direction with the reference prompt's B-rolls in the planos the script gives them."""
    direction = art_direction()
    direction['images'] += copy.deepcopy(STAND_INS)
    direction['brolls'] = copy.deepcopy(BROLLS)
    scenes = direction['scenes']
    scenes[0]['shots'][0]['background'] = broll_background('rostos-still', 'rostos')
    scenes[2]['shots'][0]['background'] = broll_background('corredor', 'corredor-vivo')
    # Ira's character sheet holds the studio portrait.
    scenes[3]['shots'][0]['background'] = broll_background('ira', 'retrato')
    scenes[4]['shots'][0]['background'] = broll_background('corredor', 'corredor-vivo')
    scenes[5]['shots'][0]['background'] = broll_background('ira-corredor', 'ira-avanca', 'pan_left')
    scenes[6]['shots'][0]['background'] = broll_background('flor-still', 'flor')
    door = copy.deepcopy(scenes[6]['shots'][0])
    scenes[6]['shots'].append({**door, 'anchor': 'O prompt completo', 'background': broll_background('porta-still', 'porta')})
    return direction


class MaterialsTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    online = art.ArtTests.online
    create_free = art.ArtTests.create_free
    start = art.ArtTests.start
    image_of = art.ArtTests.image_of

    def produce(self, direction=None, mode='all'):
        project, job = self.start('plan', mode)
        cli = FakeCLI([FREE_SCRIPT, direction or materials_direction(), APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Roteiro e cenas prontos')
        return store.get_project(project['id']), cli

    def clip(self, color='red'):
        path = DATA / f'clip-{color}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=180x320:d=1:r=30',
                        '-pix_fmt', 'yuv420p', str(path)], check=True)
        return path.read_bytes()

    def import_clip(self, project, key, content, name='corredor.mp4', kind='video/mp4'):
        return self.client.post(f'/api/projects/{project["id"]}/brolls/{key}/clip',
                                params={'revision': project['revision']}, files={'file': (name, content, kind)})

    def test_the_list_has_each_b_roll_and_its_plano_waits_on_the_arte_image_without_blocking_the_export(self):
        saved, _ = self.produce()
        self.assertEqual([{k: item[k] for k in ('key', 'title', 'prompt', 'tool', 'references', 'seconds')}
                          for item in saved['brolls']], BROLLS)
        scenes = saved['scenes']
        still = self.image_of(saved, 'rostos-still')
        self.assertEqual({k: scenes[0]['background'][k] for k in ('kind', 'asset_id', 'motion', 'broll')},
                         {'kind': 'image', 'asset_id': still['id'], 'motion': 'zoom_in', 'broll': 'rostos'})
        # One B-roll in two planos; one held by a base image.
        corridor = self.image_of(saved, 'corredor')['id']
        self.assertEqual([(scenes[i]['background']['asset_id'], scenes[i]['background']['broll']) for i in (2, 4)],
                         [(corridor, 'corredor-vivo')] * 2)
        self.assertEqual({k: scenes[3]['background'][k] for k in ('kind', 'asset_id', 'broll')},
                         {'kind': 'image', 'asset_id': self.image_of(saved, 'ira')['id'], 'broll': 'retrato'})
        self.assertEqual(scenes[6]['shots'][0]['background']['broll'], 'porta')
        # Waiting for a clip is not a missing file: the Short still exports.
        validate_project(saved)

    def test_without_arte_images_a_b_roll_plano_waits_on_the_project_background_and_still_exports(self):
        direction = free_direction()
        direction['brolls'] = [copy.deepcopy(BROLLS[0])]
        direction['scenes'][0]['shots'][0]['background'] = broll_background(None, 'rostos', 'none', 0)
        saved, cli = self.produce(direction, 'none')
        self.assertEqual(len(cli.texts), 3, 'No correction: without the Arte there is no imagem provisória to ask for.')
        self.assertEqual({k: saved['scenes'][0]['background'][k] for k in ('kind', 'asset_id', 'broll')},
                         {'kind': 'image', 'asset_id': None, 'broll': 'rostos'})
        self.assertEqual(self.client.get(f'/api/projects/{saved["id"]}').json()['brolls'][0]['places'],
                         [{'scene': 1, 'shot': 1, 'waiting': True}])
        validate_project(saved)

    def test_with_the_arte_each_b_roll_plano_gets_an_imagem_provisoria_with_camera_motion(self):
        flawed = materials_direction()
        flawed['scenes'][3]['shots'][0]['background'] = broll_background(None, 'retrato')
        flawed['scenes'][6]['shots'][0]['background']['motion'] = 'none'
        project, job = self.start('plan', 'all')
        cli = FakeCLI([FREE_SCRIPT, flawed, copy.deepcopy(flawed), APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        correction = cli.texts[2]
        self.assertIn('scenes[3].shots[0].background: dê ao plano do B-roll “retrato” uma imagem provisória', correction)
        self.assertIn('scenes[6].shots[0].background: dê movimento de câmera (motion) à imagem provisória', correction)
        scenes = store.get_project(project['id'])['scenes']
        # What cannot be repaired waits on the project background; a still image gets a slow zoom.
        self.assertEqual(scenes[3]['background']['asset_id'], None)
        self.assertEqual(scenes[6]['background']['motion'], 'zoom_in')

    def test_invalid_b_rolls_get_one_correction_and_are_then_dropped(self):
        flawed = materials_direction()
        flawed['brolls'][2]['references'] = ['corredor', 'nave-inventada']
        # A B-roll no plano shows, and a plano citing a B-roll that is not in the list.
        flawed['brolls'].append({**BROLLS[0], 'key': 'sobra', 'title': 'Sobra'})
        flawed['scenes'][1]['shots'][0]['background'] = broll_background('corredor', 'inventado')
        project, job = self.start('plan', 'all')
        cli = FakeCLI([FREE_SCRIPT, flawed, copy.deepcopy(flawed), APPROVED])
        with patch.object(bridge, 'invoke', side_effect=cli):
            pipeline.produce(job)
        correction = cli.texts[2]
        for problem in ('“nave-inventada” não é uma imagem-base', 'o B-roll “sobra” não entra em nenhum plano',
                        'scenes[1].shots[0].background.broll'):
            self.assertIn(problem, correction)
        saved = store.get_project(project['id'])
        self.assertEqual([item['key'] for item in saved['brolls']], [item['key'] for item in BROLLS])
        self.assertEqual(saved['brolls'][2]['references'], ['corredor'])
        # The plano keeps the image the director gave it, as an ordinary background.
        background = saved['scenes'][1]['background']
        self.assertEqual((background['asset_id'], 'broll' in background), (self.image_of(saved, 'corredor')['id'], False))

    def test_an_imported_clip_fills_every_plano_of_its_b_roll_and_nothing_else(self):
        saved, _ = self.produce()
        before = copy.deepcopy(saved['scenes'])
        response = self.import_clip(saved, 'corredor-vivo', self.clip())
        self.assertEqual(response.status_code, 200, response.text)
        project = response.json()
        clip = project['videos'][-1]
        self.assertEqual(clip['name'], 'corredor.mp4')
        scenes = project['scenes']
        for index in (2, 4):
            background = scenes[index]['background']
            self.assertEqual({k: background[k] for k in ('kind', 'asset_id', 'broll', 'dim')},
                             {'kind': 'video', 'asset_id': clip['id'], 'broll': 'corredor-vivo', 'dim': 20})
            self.assertEqual(background['motion'], 'none', 'A video has its own movement.')
        for index in (0, 1, 3, 5, 6):
            self.assertEqual(scenes[index], before[index])
        validate_project(store.get_project(project['id']))
        # A new clip for the same B-roll replaces the previous one.
        again = self.import_clip(project, 'corredor-vivo', self.clip('blue'), 'corredor-v2.mp4').json()
        self.assertEqual(again['scenes'][4]['background']['asset_id'], again['videos'][-1]['id'])

    def test_a_b_roll_made_as_an_image_takes_the_imported_image_with_its_camera_motion(self):
        saved, _ = self.produce()
        response = self.import_clip(saved, 'rostos', art.png('#335577', (90, 160)), 'rostos.png', 'image/png')
        self.assertEqual(response.status_code, 200, response.text)
        project = response.json()
        image = project['images'][-1]
        self.assertEqual(image['name'], 'rostos.png')
        self.assertEqual({k: project['scenes'][0]['background'][k] for k in ('kind', 'asset_id', 'motion', 'broll')},
                         {'kind': 'image', 'asset_id': image['id'], 'motion': 'zoom_in', 'broll': 'rostos'})
        rostos = next(item for item in project['brolls'] if item['key'] == 'rostos')
        self.assertEqual(rostos['places'], [{'scene': 1, 'shot': 1, 'waiting': False}])
        validate_project(store.get_project(project['id']))

    def test_the_project_says_which_clips_are_missing_and_in_which_planos(self):
        saved, _ = self.produce()
        project = self.client.get(f'/api/projects/{saved["id"]}').json()
        places = {item['key']: item['places'] for item in project['brolls']}
        self.assertEqual(places['rostos'], [{'scene': 1, 'shot': 1, 'waiting': True}])
        self.assertEqual(places['corredor-vivo'], [{'scene': 3, 'shot': 1, 'waiting': True},
                                                   {'scene': 5, 'shot': 1, 'waiting': True}])
        self.assertEqual(places['porta'], [{'scene': 7, 'shot': 2, 'waiting': True}])
        project = self.import_clip(project, 'corredor-vivo', self.clip()).json()
        self.assertEqual([place['waiting'] for item in project['brolls'] for place in item['places']
                          if item['key'] == 'corredor-vivo'], [False, False])

    def test_a_clip_needs_a_b_roll_of_the_list_that_a_plano_still_shows(self):
        saved, _ = self.produce()
        self.assertEqual(self.import_clip(saved, 'inventado', self.clip()).status_code, 404)
        scenes = copy.deepcopy(saved['scenes'])
        scenes[0]['background'] = None
        edited = self.client.put(f'/api/projects/{saved["id"]}', json={
            'title': saved['title'], 'scenes': scenes, 'visual_style': saved['visual_style'], 'revision': saved['revision']})
        self.assertEqual(edited.status_code, 200, edited.text)
        refused = self.import_clip(edited.json(), 'rostos', self.clip())
        self.assertEqual(refused.status_code, 422)
        self.assertIn('Nenhum plano usa mais o B-roll', refused.text)
        self.assertEqual(store.get_project(saved['id']).get('videos', []), [])

    def test_the_finished_production_says_which_clips_are_missing_and_saves_the_list(self):
        project, job = self.start('plan', 'all')
        with patch.object(bridge, 'invoke', side_effect=FakeCLI([FREE_SCRIPT, materials_direction(), APPROVED])):
            pipeline.produce(job)
        self.assertEqual(worker.final_message(store.get_job(job['id']), None),
                         'Roteiro e cenas prontos · faltam 6 clipes de B-roll (B-roll 1, B-roll 2, B-roll 3, B-roll 4, B-roll 5, B-roll 6): '
                         'veja a aba Materiais')
        store.finish(job['id'], 'succeeded', 'Pronto')
        self.assertIn('materiais.txt', store.get_job(job['id'])['materials'])
        listing = self.client.get(f'/api/jobs/{job["id"]}/materials/materiais.txt')
        self.assertEqual(listing.status_code, 200)
        text = listing.text
        self.assertIn('B-ROLL 3 · Corredor vivo\nFerramenta: Kling/Runway · 5 s\nEntra em: cena 3, plano 1; cena 5, plano 1\n'
                      'Referências: Corredor vazio da Halcyon\n'
                      'Prompt: Wide shot, 24mm lens, slow dolly forward down an abandoned spaceship corridor, no people', text)
        self.assertIn('B-ROLL 1 · Gancho: o mesmo personagem com 3 rostos\nFerramenta: Midjourney/Flux, 3 gerações · 3 s\n'
                      'Entra em: cena 1, plano 1\nReferências: nenhuma', text)
        # One clip left after an import.
        saved = store.get_project(project['id'])
        for item in BROLLS[:-1]:
            saved = self.import_clip(saved, item['key'], self.clip()).json()
        self.assertEqual(worker.final_message(store.get_job(job['id']), None),
                         'Roteiro e cenas prontos · falta 1 clipe de B-roll (B-roll 6): veja a aba Materiais')

    def test_a_saved_plano_can_only_cite_a_b_roll_of_the_list(self):
        saved, _ = self.produce()
        scenes = copy.deepcopy(saved['scenes'])
        scenes[1]['background'] = {'kind': 'video', 'asset_id': None, 'broll': 'inventado'}
        body = {'title': saved['title'], 'scenes': scenes, 'visual_style': saved['visual_style'], 'revision': saved['revision']}
        refused = self.client.put(f'/api/projects/{saved["id"]}', json=body)
        self.assertEqual(refused.status_code, 422)
        self.assertIn('fora da lista de materiais', refused.text)
        # A Short with a format has no lista de materiais.
        blank = self.client.post('/api/projects', json={'title': 'Formato'}).json()
        scene = {**blank['scenes'][0], 'background': {'kind': 'image', 'asset_id': None, 'broll': 'rostos'}}
        refused = self.client.put(f'/api/projects/{blank["id"]}', json={'title': 'Formato', 'scenes': [scene],
                                                                         'revision': blank['revision']})
        self.assertEqual(refused.status_code, 422, refused.text)


if __name__ == '__main__':
    unittest.main()
