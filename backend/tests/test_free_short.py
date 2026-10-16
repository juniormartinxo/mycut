"""Short livre (ADR 0005): the prompt is the specification. Only external CLIs are fixtures."""
import io
import json
import time
import unittest
from PIL import Image
import test_studio  # Sets isolated DATA before the application modules are imported.
from unittest.mock import patch
from mycut import bridge, elevenlabs, integrations, pipeline, store
from mycut.config import DATA

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


FREE_SCRIPT = {'mode': 'script', 'title': 'Da ideia ao filme com IA #Shorts', 'description': 'Método em 4 etapas.',
               'tags': 'IA, Shorts', 'claims': [],
               'scenes': [{'timing': t, 'narration': n, 'screen_text': [s], 'visual': f'Bloco {t}'} for t, n, s in BLOCKS]}


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
    return {'accent': '#f2b544', 'scenes': scenes}


APPROVED = {'approved': True, 'issues': []}


def png(color):
    out = io.BytesIO()
    Image.new('RGB', (64, 96), color).save(out, format='PNG')
    return out.getvalue()


class FreeShortTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown

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
                         (FREE_SCRIPT['title'], '#f2b544', [], ''))
        steps = {s['name']: s['state'] for s in store.get_job(job['id'])['steps']}
        self.assertEqual(steps, {'writer': 'succeeded', 'research': 'skipped', 'director': 'succeeded', 'reviewer': 'succeeded'})

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
