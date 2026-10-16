"""Short livre (ADR 0005): the prompt is the specification. Only external CLIs are fixtures."""
import base64
import io
import json
import math
import subprocess
import time
import numpy as np
import unittest
from PIL import Image
import test_studio  # Sets isolated DATA before the application modules are imported.
from unittest.mock import patch
from mycut import bridge, elevenlabs, integrations, pipeline, store
from mycut.config import DATA
from mycut.production import make_video
from mycut.scene_layout import SceneBlock, new_id
from test_scene_shots import difference

BLOCKS = [
    ('0–3 s', 'Seus vídeos de IA mudam de rosto a cada cena? O problema não é a ferramenta.', 'O PROBLEMA NÃO É A IA'),
    ('3–8 s', 'É que você pula a pré-produção. Olha: tudo começa com uma frase simples.', '1 FRASE → 1 FILME'),
    ('8–16 s', 'Primeiro, o tom: gênero, paleta e luz. Isso vira a regra de todas as cenas.', 'ETAPA 1: TOM'),
    ('16–28 s', 'Depois, a ficha do personagem com números exatos: idade, altura, peso, cicatriz.', 'ETAPA 2: FICHA COM NÚMEROS'),
    ('28–38 s', 'Terceiro, o cenário sozinho, sem ninguém. Ele vira a referência fixa do mundo.', 'ETAPA 3: CENÁRIO VAZIO'),
    ('38–50 s', 'Por último, a decupagem: plano, movimento de câmera e física.', 'ETAPA 4: CENA = FICHA + CENÁRIO + PROMPT'),
    ('50–58 s', 'Resultado: isso. O prompt completo está no comentário fixado.', 'PROMPT NO COMENTÁRIO FIXADO'),
]
# A complete script in Markdown, with a table and code blocks, longer than the old 12 000-character brief.
PROMPT = ('# Short: Da Ideia ao Filme com IA\n\n## Roteiro segundo a segundo\n\n'
          '| Tempo | Narração (off) | Texto na tela |\n| --- | --- | --- |\n'
          + ''.join(f'| {t} | "{n}" | {s} |\n' for t, n, s in BLOCKS)
          + '\n## Material de demonstração\n\n'
          + ''.join(f'### Ficha {i}\n\n```\nStudio character reference sheet, 85mm lens, take {i}, photorealistic --ar 3:2\n```\n\n'
                    + 'Corredor cilíndrico de painéis de alumínio escovado, com cabos soltos flutuando. ' * 4 + '\n\n'
                    for i in range(30)))


FREE_SCRIPT = {'mode': 'script', 'titles': ['Da ideia ao filme com IA #Shorts', 'O segredo dos filmes de IA consistentes'],
               'description': 'Método em 4 etapas.', 'tags': 'IA, Shorts', 'hashtags': ['#Shorts', '#IA', '#FilmeComIA'],
               'pinned_comment': 'Prompt-mestre: você é um diretor de cinema. Junto de cada prompt em inglês, traga a tradução em português.',
               'claims': [],
               'scenes': [{'timing': t, 'narration': n, 'screen_text': [s], 'visual': f'Bloco {t}', 'pauses': []}
                          for t, n, s in BLOCKS]}
# "Resultado: isso." (pausa) "O prompt completo está no comentário fixado."
FREE_SCRIPT['scenes'][-1]['pauses'] = [{'after': 'Resultado: isso.', 'seconds': .8}]


def text(kind, value, **extra):
    return {'type': kind, 'text': value, 'font_size': 64, 'color': '#f2b544', 'align': 'center', 'reveal': 'none',
            'image_id': None, 'motion': 'none', 'flow': None, **extra}


def plano(blocks, anchor=None, background=None, brand=False, transition='cut'):
    return {'anchor': anchor, 'transition': transition, 'brand': brand, 'blocks': blocks,
            'background': background or {'kind': 'gradient', 'color': '#0b2a33', 'color_to': '#05080a', 'angle': 180,
                                         'image_id': None, 'motion': 'none', 'dim': 0}}


def free_direction():
    scenes = [{'title': s, 'shots': [plano([{'height': 30, 'object': text('title', s)}, {'height': 70, 'object': None}])]}
              for _, _, s in BLOCKS]
    # Etapa 2: the character sheet enters line by line in a second plano anchored on the narration.
    scenes[3]['shots'].append(plano([{'height': 100, 'object': text('paragraph', 'Idade: 38 anos\nAltura: 172 cm\nPeso: 64 kg',
                                                                    font_size=56, reveal='lines', align='left')}],
                                    anchor='idade, altura', transition='fade'))
    # Teal and amber from the prompt's tone ("azul-petróleo frio ... contra o âmbar quente da flor").
    return {'accent': '#f2b544', 'style': {'background': '#0b2a33', 'text_color': '#e6f1f2', 'font': 'Roboto'},
            'captions': CAPTIONS, 'loop': True, 'scenes': scenes}


CAPTIONS = {'words': 3, 'position': 'middle', 'font_size': 72, 'keywords': ['ficha', 'cenário', '38']}


APPROVED = {'approved': True, 'issues': []}


def png(color):
    out = io.BytesIO()
    Image.new('RGB', (64, 96), color).save(out, format='PNG')
    return out.getvalue()


FREE_STYLE = {'format_id': 'free', 'channel_name': 'MYCUT', 'font': 'sans', 'google_font': 'Roboto',
              'background': '#0b2a33', 'text_color': '#e6f1f2', 'media_mode': 'mixed', 'image_source': 'library',
              'captions': CAPTIONS}
ACCENT = (0xf2, 0xb5, 0x44)


def empty_scene(narration, **values):
    # Nothing but the project background and the caption: every other pixel is the caption's.
    return {'id': new_id(), 'title': 'Cena', 'narration': narration, 'layout': 'statement', 'items': [], 'brand': False,
            'blocks': [SceneBlock(height=100).model_dump()], **values}


def accent_pixels(image):
    return sum(1 for pixel in image.get_flattened_data() if all(abs(a-b) < 40 for a, b in zip(pixel, ACCENT)))


def ink(image, box):
    """Pixels in box that are not the project background."""
    return sum(1 for pixel in image.crop(box).get_flattened_data() if max(abs(a-b) for a, b in zip(pixel, (0x0b, 0x2a, 0x33))) > 60)


def fake_voice(requests):
    """ElevenLabs HTTP: one second of tone per 20 characters, with the provider's character times over it."""
    def api(key, method, path, meta=None, **kwargs):
        text = kwargs['json']['text']
        requests.append(kwargs['json'])
        length = len(text) / 20
        mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'sine=frequency=330:duration={length}',
                              '-f', 'mp3', 'pipe:1'], capture_output=True, check=True).stdout
        step = length / len(text)
        meta['credits'] = float(len(text))
        return {'audio_base64': base64.b64encode(mp3).decode(), 'normalized_alignment': {
            'characters': list(text), 'character_start_times_seconds': [i*step for i in range(len(text))],
            'character_end_times_seconds': [(i+1)*step for i in range(len(text))]}}
    return api


PAUSED = 'Resultado: isso. O prompt completo está no comentário fixado.'


class FreeShortTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    edit = test_studio.StudioTests.edit

    def online(self):
        integrations.save_section('elevenlabs', {**integrations.DEFAULTS['elevenlabs'], 'api_key': 'test-only-secret',
                                                 'voice_id': 'junior123', 'voice_name': 'Junior'})
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time': time.time(), 'providers': {'codex': True, 'claude': True, 'grok': True}})

    def create_free(self, files=(), **fields):
        body = {'brief': PROMPT, 'automation': 'plan', **fields}
        return self.client.post('/api/projects/free', data={'project': json.dumps(body)},
                                files=[('files', (name, content, kind)) for name, content, kind in files])

    def test_free_short_accepts_the_whole_markdown_prompt_and_reference_attachments(self):
        self.online()
        self.assertGreater(len(PROMPT), 12000)
        response = self.create_free([('ira.png', png('#225566'), 'image/png'), ('corredor.png', png('#aa7722'), 'image/png')])
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()
        self.assertTrue(project['free'])
        self.assertEqual(project['brief'], PROMPT)
        self.assertIsNone(project['visual_style'])
        self.assertEqual([image['name'] for image in project['images']], ['ira.png', 'corredor.png'])
        self.assertEqual([(job['kind'], job['state']) for job in project['jobs']], [('plan', 'queued')])
        self.assertTrue(store.job_input(project['jobs'][0]['id'])['free'])

    def start_free(self, kind='plan'):
        self.online()
        project = self.create_free(automation=kind).json()
        store.claim()
        return project, store.get_job(project['jobs'][0]['id'], private=True)

    def test_complete_script_is_followed_literally_without_research(self):
        project, job = self.start_free()
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        prompts = [call.args[1] for call in invoke.call_args_list]
        self.assertEqual(len(prompts), 3)  # Roteiro, direção e conferência; nenhuma pesquisa.
        sent = json.dumps(PROMPT, ensure_ascii=False)
        self.assertTrue(sent in prompts[0], 'O roteirista recebe o prompt inteiro.')
        self.assertIn('personagens fictícios realistas', prompts[0])
        self.assertNotIn('nunca apresentadores humanos realistas', prompts[0])
        self.assertTrue(sent in prompts[2], 'A conferência compara o resultado com o prompt.')
        saved = store.get_project(project['id'])
        self.assertEqual([scene['narration'] for scene in saved['scenes']], [n for _, n, _ in BLOCKS])
        self.assertEqual([scene['blocks'][0]['object']['text'] for scene in saved['scenes']], [s for _, _, s in BLOCKS])
        first = saved['scenes'][0]
        self.assertEqual((first['background']['kind'], first.get('brand', True)), ('gradient', False))
        self.assertEqual([b['height'] for b in first['blocks']], [30, 70])
        sheet = saved['scenes'][3]['shots'][0]
        self.assertEqual((sheet['anchor'], sheet['transition']), ('idade, altura', 'fade'))
        self.assertEqual(sheet['blocks'][0]['object']['reveal'], 'lines')
        self.assertEqual((saved['title'], saved['accent'], saved['warnings'], saved['sources']),
                         (FREE_SCRIPT['titles'][0], '#f2b544', [], ''))
        steps = {s['name']: s['state'] for s in store.get_job(job['id'])['steps']}
        self.assertEqual(steps, {'writer': 'succeeded', 'research': 'skipped', 'director': 'succeeded', 'reviewer': 'succeeded'})

    def test_palette_font_and_captions_come_from_the_prompt_tone_without_a_format(self):
        project, job = self.start_free()
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        self.assertNotIn('format_id', invoke.call_args_list[1].args[1])  # The director gets no format to start from.
        saved = store.get_project(project['id'])
        self.assertEqual(saved['visual_style'], {
            'format_id': 'free', 'channel_name': 'MYCUT', 'font': 'sans', 'google_font': 'Roboto',
            'background': '#0b2a33', 'text_color': '#e6f1f2', 'media_mode': 'mixed', 'image_source': 'library',
            'captions': CAPTIONS, 'loop': True})
        self.assertEqual(saved['accent'], '#f2b544')

    def test_publication_package_has_title_options_description_hashtags_and_pinned_comment(self):
        project, job = self.start_free()
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, free_direction(), APPROVED]):
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual(saved['publication'], {
            'titles': FREE_SCRIPT['titles'], 'description': 'Método em 4 etapas.',
            'hashtags': ['#Shorts', '#IA', '#FilmeComIA'], 'pinned_comment': FREE_SCRIPT['pinned_comment']})
        self.assertEqual((saved['title'], saved['description']), (FREE_SCRIPT['titles'][0], 'Método em 4 etapas.'))
        text = (DATA/'projects'/project['id']/'renders'/job['id']/'publicacao.txt').read_text()
        for part in ('O segredo dos filmes de IA consistentes', '#Shorts #IA #FilmeComIA', 'COMENTÁRIO FIXADO',
                     FREE_SCRIPT['pinned_comment']):
            self.assertIn(part, text)

    def test_an_explicit_pause_is_kept_in_its_scene_and_checked_by_the_conference(self):
        project, job = self.start_free()
        script = json.loads(json.dumps(FREE_SCRIPT))
        script['scenes'][2]['pauses'] = [{'after': 'uma frase que ninguém fala', 'seconds': 1}]
        with patch.object(bridge, 'invoke', side_effect=[script, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual(saved['scenes'][-1]['pauses'], [{'after': 'Resultado: isso.', 'seconds': .8}])
        self.assertNotIn('pauses', saved['scenes'][2])
        self.assertEqual(saved['warnings'], ['Cena 3: a pausa depois de “uma frase que ninguém fala” não está na narração '
                                             'e foi removida.'])
        self.assertIn('"pauses": [{"after": "Resultado: isso.", "seconds": 0.8}]', invoke.call_args_list[2].args[1])

    def test_a_pause_is_silence_between_synthesized_passages_and_shifts_the_word_times(self):
        pause = {'after': 'Resultado: isso.', 'seconds': .8}
        project = {'scenes': [{'narration': 'Primeiro, o tom.'},
                              {'narration': 'Resultado: isso. O prompt completo está no comentário fixado.', 'pauses': [pause]}]}
        requests = []
        api = fake_voice(requests)
        spent = []
        settings = {'api_key': 'k', 'voice_id': 'v', 'voice_name': 'Voz', 'model_id': 'm', 'stability': .5,
                    'similarity_boost': .75, 'speed': 1}
        with patch.object(elevenlabs, 'api', side_effect=api):
            record = elevenlabs.synthesize(project, settings, DATA/'pause-test', spent=lambda *args: spent.append(args))
        first, second = 'Primeiro, o tom.\n\nResultado: isso.', 'O prompt completo está no comentário fixado.'
        self.assertEqual([r['text'] for r in requests], [first, second])
        # Prosody continues across the cut: each passage knows its neighbour.
        self.assertEqual((requests[0].get('next_text'), requests[1].get('previous_text')), (second, first))
        self.assertEqual(spent, [(float(len(first) + len(second)), False)])
        before = len(first) / 20
        self.assertAlmostEqual(record['duration'], before + .8 + len(second) / 20, delta=.12)
        words = json.loads((DATA/record['alignment']).read_text())['segments'][0]['words']
        self.assertEqual(' '.join(w['word'] for w in words), first.replace('\n\n', ' ') + ' ' + second)
        isso, after = words[4], words[5]
        self.assertLess(isso['end'], before + .05)
        self.assertGreaterEqual(after['start'], before + .8 - .05)
        signal = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(DATA/record['path']), '-ac', '1',
                                                        '-ar', '8000', '-f', 'f32le', '-']), dtype=np.float32)
        silence = signal[round((before + .15) * 8000):round((before + .65) * 8000)]
        tone = signal[round(.2 * 8000):round(.7 * 8000)]
        self.assertLess(np.abs(silence).max(), .01)
        self.assertGreater(np.abs(tone).max(), .1)
        # A pause after the last words is still silence, at the end of the voice.
        ending = {'scenes': [{'narration': 'Resultado: isso.', 'pauses': [{'after': 'isso.', 'seconds': .8}]}]}
        with patch.object(elevenlabs, 'api', side_effect=fake_voice([])):
            closing = elevenlabs.synthesize(ending, settings, DATA/'pause-end-test')
        self.assertAlmostEqual(closing['duration'], len('Resultado: isso.') / 20 + .8, delta=.12)
        # Changing a pause changes what the voice says, so the saved audio no longer matches.
        longer = {'scenes': [project['scenes'][0], {**project['scenes'][1], 'pauses': [{**pause, 'seconds': 1.2}]}]}
        self.assertNotEqual(store.script_hash(longer), record['script_hash'])

    def free_project(self, scenes, style=FREE_STYLE):
        self.online()
        self.project = self.create_free().json()
        store.cancel(self.project['jobs'][0]['id'])
        response = self.edit(visual_style=style, accent='#f2b544', scenes=scenes)
        self.assertEqual(response.status_code, 200, response.text)
        return self.project

    def export(self):
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        job = store.claim()
        result = make_video(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        folder = DATA / result['directory']
        return folder, json.loads((folder/'timing.json').read_text())

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

    def test_captions_show_a_few_words_with_keywords_in_the_accent_inside_the_safe_area_in_preview_and_mp4(self):
        scenes = [empty_scene('Depois, a ficha do personagem com números exatos: idade, altura, peso e cicatriz.'),
                  empty_scene('Terceiro, o cenário sozinho, sem ninguém. Ele vira a referência do mundo.')]
        self.free_project(scenes)
        folder, timing = self.export()
        captions = timing['captions']
        self.assertTrue(all(2 <= len(c['text'].split()) <= 3 for c in captions), captions)
        self.assertEqual(' '.join(c['text'] for c in captions), ' '.join(s['narration'] for s in scenes))
        srt = (folder/'legendas.srt').read_text()
        self.assertTrue(all(c['text'] in srt for c in captions))
        fps, highlighted = 24, 0
        # The bottom strip of an export without narration carries its "PRÉVIA SEM NARRAÇÃO" mark, not a caption.
        area = (0, 0, 540, 900)
        for caption in captions:
            t = round((caption['start'] + caption['end']) / 2 * fps) / fps
            index = next(i for i, b in enumerate(timing['scenes']) if b['start'] <= t < b['end'])
            frame = self.mp4_frame(folder, t)
            preview = self.preview_frame(self.project['scenes'][index], t - timing['scenes'][index]['start'])
            self.assertLess(difference(frame.crop(area), preview.crop(area)), 1.5, caption)
            self.assertGreater(ink(frame, (0, 0, 465, 816)), 200, caption)
            # Nothing in the bottom 15% or in the right strip of the YouTube buttons.
            self.assertEqual((ink(frame, (0, 816, 540, 900)), ink(frame, (465, 0, 540, 816))), (0, 0), caption)
            keyword = any(word.strip('.,:') in ('ficha', 'cenário') for word in caption['text'].split())
            self.assertEqual(accent_pixels(frame) > 30, keyword, caption)
            highlighted += keyword
        self.assertEqual(highlighted, 2)

    def paused_scene(self):
        second = {'id': new_id(), 'anchor': 'O prompt completo', 'transition': 'cut', 'background': None, 'brand': False,
                  'blocks': [SceneBlock(height=100).model_dump()]}
        return empty_scene(PAUSED, pauses=[{'after': 'Resultado: isso.', 'seconds': .8}], shots=[second])

    def assert_pause_in_times(self, timing, report, said):
        """`said` is when "isso." ends; the next words, their caption and the plano they anchor wait the silence."""
        captions = timing['captions']
        before = next(c for c in captions if c['text'].endswith('isso.'))
        after = captions[captions.index(before)+1]
        self.assertEqual(before['text'], 'Resultado: isso.')
        self.assertLessEqual(before['end'], said + .15)
        self.assertGreaterEqual(after['start'], said + .8 - .05)
        self.assertGreaterEqual(report['shots'][1]['start'], said + .8 - .05)

    def inspect(self):
        response = self.client.post('/api/scene-layout/inspect', json={'scene': self.project['scenes'][0], 'project_id': self.project['id'],
                                    'accent': self.project['accent'], 'visual_style': self.project['visual_style']})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_a_pause_delays_the_following_captions_and_planos_in_the_voice_and_in_the_estimate(self):
        self.free_project([self.paused_scene()])
        _, timing = self.export()
        # Estimate: 2.7 words per second over the scene, plus the silence.
        words = len(PAUSED.split())
        duration = max(2.0, words/2.7 + .3)
        self.assertAlmostEqual(timing['duration_seconds'], duration + .8)
        self.assert_pause_in_times(timing, self.inspect(), duration * 2 / words)
        settings = integrations.read()
        store.enqueue(self.project['id'], 'final', self.project['revision'], 'voice', settings)
        job = store.claim()
        with patch.object(elevenlabs, 'api', side_effect=fake_voice([])):
            pipeline.produce(job)
        store.finish(job['id'], 'succeeded', 'Pronto')
        self.project = self.client.get(f'/api/projects/{self.project["id"]}').json()
        self.assertTrue(self.project['audio_matches_script'])
        folder, timing = self.export()
        self.assert_pause_in_times(timing, self.inspect(), len('Resultado: isso.') / 20)
        silent = self.mp4_frame(folder, len('Resultado: isso.') / 20 + .5)
        self.assertEqual(ink(silent, (0, 0, 540, 816)), 0)  # No caption during the silence.

    def test_a_loop_ends_on_the_first_frame_in_preview_and_mp4_unless_an_ending_follows(self):
        first = empty_scene('Seus vídeos de IA mudam de rosto a cada cena?', background={'kind': 'color', 'color': '#aa2211'})
        last = empty_scene('O prompt completo está no comentário fixado.', background={'kind': 'color', 'color': '#1144aa'})
        self.free_project([first, last], {**FREE_STYLE, 'loop': True})
        folder, timing = self.export()
        fps, top = 24, (0, 0, 540, 300)  # Above the captions: only the planos' backgrounds.
        end = timing['duration_seconds']
        closing_time = (math.ceil(end*fps) - 1) / fps
        opening, closing = self.mp4_frame(folder, 0).crop(top), self.mp4_frame(folder, closing_time).crop(top)
        before = self.mp4_frame(folder, end - .7).crop(top)
        self.assertLess(difference(opening, closing), 3)
        # The whole closing frame is the first plano, with no caption left over it.
        bare = Image.new('RGB', (540, 900), '#aa2211')
        self.assertLess(difference(self.mp4_frame(folder, closing_time).crop((0, 0, 540, 900)), bare), 3)
        self.assertGreater(difference(before, opening), 40)
        bounds = timing['scenes'][1]
        preview = self.preview_frame(self.project['scenes'][1], closing_time - bounds['start']).crop(top)
        self.assertLess(difference(preview, closing), 3)
        self.assertEqual(self.project['warnings'], [])
        # A video ending plays after the last frame, so the loop could not be seamless: it is not applied, and said so.
        clip = DATA / 'loop-ending.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=green:s=108x192:r=24', '-t', '0.8',
                        '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p', str(clip)], check=True)
        ending = self.client.post('/api/endings', files={'file': ('fim.mp4', clip.read_bytes(), 'video/mp4')}).json()
        self.assertEqual(self.edit(ending_id=ending['id']).status_code, 200)
        self.assertEqual(self.project['warnings'], ['O loop não é aplicado porque o Short termina com um vídeo de encerramento.'])
        folder, timing = self.export()
        self.assertLess(difference(self.mp4_frame(folder, closing_time).crop(top), before), 3)
        preview = self.preview_frame(self.project['scenes'][1], closing_time - bounds['start']).crop(top)
        self.assertLess(difference(preview, before), 3)

    def test_research_checks_only_the_listed_claims_and_an_unverified_one_becomes_a_warning(self):
        project, job = self.start_free()
        claims = ['O Kling gera clipes de até 10 segundos.', 'O Runway custa US$ 12 por mês.']
        research = {'sources': [{'title': 'Kling', 'url': 'https://example.com/kling'}],
                    'checks': [{'claim': claims[0], 'verified': True, 'source_url': 'https://example.com/kling', 'evidence': 'até 10 s'},
                               # Claimed as verified without a listed source: still unverified.
                               {'claim': claims[1], 'verified': True, 'source_url': 'https://example.com/runway', 'evidence': 'US$ 12'}]}
        with patch.object(bridge, 'invoke', side_effect=[{**FREE_SCRIPT, 'claims': claims}, research, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        call = invoke.call_args_list[1]
        self.assertTrue(call.kwargs['web'])
        self.assertIn(json.dumps(claims, ensure_ascii=False), call.args[1])
        self.assertNotIn('Corredor cilíndrico', call.args[1])  # Only the claims are researched, not the prompt.
        saved = store.get_project(project['id'])
        self.assertEqual(saved['warnings'], [f'Afirmação não verificada: {claims[1]}'])
        self.assertEqual(saved['sources'], 'https://example.com/kling')
        self.assertEqual([n for n in (s['narration'] for s in saved['scenes'])], [n for _, n, _ in BLOCKS])

    def test_an_idea_has_its_unverified_claims_softened_by_the_writer(self):
        project, job = self.start_free()
        idea = {**FREE_SCRIPT, 'mode': 'idea', 'claims': ['O Kling gera clipes de 2 minutos.']}
        unverified = {'sources': [], 'checks': []}
        softened = {**FREE_SCRIPT, 'mode': 'idea', 'claims': []}
        with patch.object(bridge, 'invoke', side_effect=[idea, unverified, softened, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        self.assertIn('Suavize ou remova', invoke.call_args_list[2].args[1])
        self.assertIn('O Kling gera clipes de 2 minutos.', invoke.call_args_list[2].args[1])
        self.assertEqual(store.get_project(project['id'])['warnings'], [])

    def test_a_claim_introduced_while_softening_is_checked_and_warned(self):
        project, job = self.start_free()
        idea = {**FREE_SCRIPT, 'mode': 'idea', 'claims': ['O Kling gera clipes de 2 minutos.']}
        softened = {**FREE_SCRIPT, 'mode': 'idea', 'claims': ['O Kling gera clipes de 10 segundos.']}
        nothing = {'sources': [], 'checks': []}
        with patch.object(bridge, 'invoke', side_effect=[idea, nothing, softened, nothing, free_direction(), APPROVED]) as invoke:
            pipeline.produce(job)
        self.assertIn('10 segundos', invoke.call_args_list[3].args[1])
        self.assertEqual(store.get_project(project['id'])['warnings'],
                         ['Afirmação não verificada: O Kling gera clipes de 10 segundos.'])

    def test_an_unreadable_conference_keeps_the_paid_work(self):
        project, job = self.start_free()
        unreadable = {'aprovado': 'talvez'}
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, free_direction(), unreadable,
                                                         FREE_SCRIPT, free_direction(), unreadable]):
            with self.assertRaisesRegex(ValueError, 'salvos'):
                pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual([s['narration'] for s in saved['scenes']], [n for _, n, _ in BLOCKS])
        self.assertTrue(saved['warnings'][0].startswith('Conferência: O agente de conferência entregou'))

    def test_format_briefs_keep_their_12000_character_limit(self):
        self.online()
        response = self.client.post('/api/projects', json={'title': 'Formato', 'brief': PROMPT, 'automation': 'plan'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn('Livre', response.json()['detail'])
        # The saved project decides the mode: an edit can neither turn a format into Livre nor pass the limit.
        self.assertEqual(self.edit(brief=PROMPT).status_code, 422)
        self.assertEqual(self.edit(free=True, brief=PROMPT).status_code, 422)
        self.assertFalse(store.get_project(self.project['id']).get('free'))

    def test_only_a_free_short_takes_the_generated_style(self):
        for path, body in (('/api/projects', {'title': 'Formato', 'visual_style': FREE_STYLE}),):
            self.assertEqual(self.client.post(path, json=body).status_code, 422)
        response = self.edit(visual_style=FREE_STYLE)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn('Short livre', response.json()['detail'])
        paused = [{**self.project['scenes'][0], 'narration': 'Resultado: isso.', 'pauses': [{'after': 'isso.', 'seconds': .8}]}]
        response = self.edit(scenes=paused)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn('Pausas', response.json()['detail'])

    def test_a_free_short_with_a_long_prompt_saves_in_the_editor(self):
        self.online()
        self.project = self.create_free().json()
        store.cancel(self.project['jobs'][0]['id'])
        response = self.edit(brief=PROMPT + '\n\nMais um ajuste.')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['free'])

    def test_cli_failures_in_research_and_conference_never_refuse_or_lose_the_paid_work(self):
        project, job = self.start_free()
        claims = ['O Kling gera clipes de até 10 segundos.']
        timeout = ValueError('O agente excedeu 15 minutos.')
        with patch.object(bridge, 'invoke', side_effect=[{**FREE_SCRIPT, 'claims': claims}, timeout, free_direction(), timeout,
                                                         ValueError('O CLI encerrou com erro.')]):
            with self.assertRaisesRegex(ValueError, 'salvos'):
                pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual([s['narration'] for s in saved['scenes']], [n for _, n, _ in BLOCKS])
        self.assertIn(f'Afirmação não verificada: {claims[0]}', saved['warnings'])
        self.assertTrue(any('15 minutos' in warning for warning in saved['warnings']))

    def test_repaired_text_always_fits_and_a_shortened_text_is_a_warning(self):
        project, job = self.start_free()
        unreadable = {'nodes': [{'id': f'n{i}', 'label': f'Etapa número {i} longa', 'icon': None, 'shape': 'circle',
                                 'x': 50, 'y': 10 + i * 10, 'size': 18, 'chart': None} for i in range(8)],
                      'links': [], 'steps': [{'source': None, 'target': 'n0', 'kind': 'request', 'anchor': None}]}
        crowded = free_direction()
        crowded['scenes'][1]['shots'][0]['blocks'] = [
            {'height': 4, 'object': text('flow', '', font_size=40, flow=unreadable)},
            {'height': 96, 'object': None}]
        crowded['scenes'][2]['shots'][0]['blocks'][0]['object'] = text('title', 'Supercalifragilístico' * 6, font_size=200)
        crowded['scenes'][4]['shots'][0]['blocks'] = [
            {'height': 5, 'object': text('paragraph', 'Uma ficha longa demais para caber no bloco estreito ' * 8, font_size=60)},
            {'height': 95, 'object': None}]
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, crowded, crowded, APPROVED]):
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        from mycut.block_render import validate_project
        validate_project(saved)  # Nothing left that the render would refuse after the voice is paid.
        self.assertTrue(any(w.startswith('Cena 5: o texto na tela foi encurtado') for w in saved['warnings']), saved['warnings'])

    def test_a_failed_second_round_keeps_the_first_rounds_work(self):
        project, job = self.start_free('pipeline')
        rejected = {'approved': False, 'issues': ['A cena 2 trocou o texto na tela.']}
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, free_direction(), rejected,
                                                         ValueError('O CLI encerrou com erro.')]), \
                patch.object(elevenlabs, 'synthesize') as voice:
            with self.assertRaisesRegex(ValueError, 'salvos'):
                pipeline.produce(job)
            voice.assert_not_called()
        saved = store.get_project(project['id'])
        self.assertEqual(len(saved['scenes']), len(BLOCKS))
        self.assertIn('Conferência: A cena 2 trocou o texto na tela.', saved['warnings'])

    def test_direction_problems_get_one_correction_and_are_then_repaired_instead_of_failing(self):
        project, job = self.start_free()
        flawed = free_direction()
        first = flawed['scenes'][0]['shots'][0]
        first['blocks'][0]['height'] = 20  # 20 + 70: does not sum 100.
        first['blocks'][0]['object'] = text('title', 'O PROBLEMA NÃO É A IA ' * 12, font_size=200)
        first['blocks'][1]['object'] = text('image', '', image_id='f' * 32)  # Not an available image.
        flawed['scenes'][3]['shots'][1]['anchor'] = 'frase que ninguém fala'
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, flawed, flawed, APPROVED]) as invoke:
            pipeline.produce(job)
        correction = invoke.call_args_list[2].args[1]
        for problem in ('somam 90', 'image_id de available_images', 'não cabe', 'frase que ninguém fala'):
            self.assertIn(problem, correction)
        saved = store.get_project(project['id'])
        first = saved['scenes'][0]
        self.assertAlmostEqual(sum(b['height'] for b in first['blocks']), 100)
        self.assertIsNone(first['blocks'][1]['object'])
        self.assertLess(first['blocks'][0]['object']['font_size'], 200)
        self.assertIsNone(saved['scenes'][3]['shots'][0]['anchor'])
        from mycut.block_render import validate_project
        validate_project(saved)  # The repaired production renders.

    def test_unusable_direction_falls_back_to_the_script_text_on_screen(self):
        project, job = self.start_free()
        broken = {'accent': 'teal', 'scenes': []}
        with patch.object(bridge, 'invoke', side_effect=[FREE_SCRIPT, broken, broken, APPROVED]):
            pipeline.produce(job)
        saved = store.get_project(project['id'])
        self.assertEqual([s['blocks'][0]['object']['text'] for s in saved['scenes']], [s for _, _, s in BLOCKS])
        self.assertEqual([s['narration'] for s in saved['scenes']], [n for _, n, _ in BLOCKS])

    def test_rejected_fidelity_keeps_the_paid_work_and_stops_before_the_voice(self):
        project, job = self.start_free('pipeline')
        rejected = {'approved': False, 'issues': ['A cena 3 trocou a fala do prompt.']}
        outputs = [FREE_SCRIPT, free_direction(), rejected, FREE_SCRIPT, free_direction(), rejected]
        with patch.object(bridge, 'invoke', side_effect=outputs) as invoke, patch.object(elevenlabs, 'synthesize') as voice:
            with self.assertRaisesRegex(ValueError, 'salvos'):
                pipeline.produce(job)
            voice.assert_not_called()
        self.assertIn('A cena 3 trocou a fala do prompt.', invoke.call_args_list[3].args[1])  # The writer corrects it once.
        saved = store.get_project(project['id'])
        self.assertEqual(len(saved['scenes']), len(BLOCKS))
        self.assertEqual(saved['warnings'], ['Conferência: A cena 3 trocou a fala do prompt.'])
        self.assertEqual(next(s for s in store.get_job(job['id'])['steps'] if s['name'] == 'reviewer')['state'], 'failed')

    def test_format_productions_keep_the_animation_only_rule(self):
        job = self.start_format()
        with patch.object(bridge, 'invoke', side_effect=ValueError('parar após o primeiro pedido')) as invoke:
            with self.assertRaises(ValueError):
                pipeline.produce(job)
        self.assertIn('nunca apresentadores humanos realistas', invoke.call_args.args[1])
        self.assertNotIn('personagens fictícios realistas', invoke.call_args.args[1])

    def start_format(self):
        self.online()
        project = self.client.post('/api/projects', json={'title': 'Formato', 'brief': 'Uma notícia', 'automation': 'plan'}).json()
        store.claim()
        return store.get_job(project['jobs'][0]['id'], private=True)

    def test_invalid_attachment_or_offline_agents_create_nothing(self):
        self.online()
        before = len(store.all_projects())
        files = set((DATA/'projects').glob('*/images/*.png'))
        response = self.create_free([('notas.png', b'not an image', 'image/png')])
        self.assertEqual(response.status_code, 422, response.text)
        (bridge.BRIDGE/'heartbeat.json').unlink()
        response = self.create_free([('ira.png', png('#225566'), 'image/png')])
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(store.all_projects()), before)
        self.assertEqual(store.jobs(), [])
        self.assertEqual(set((DATA/'projects').glob('*/images/*.png')), files)


if __name__ == '__main__':
    unittest.main()
