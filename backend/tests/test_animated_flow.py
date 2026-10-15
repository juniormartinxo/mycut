import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops, ImageStat

TEMP = tempfile.TemporaryDirectory(prefix='mycut-flow-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut import store, scene_chat, scene_layout, block_render, flow, pipeline
from mycut.api import app
from mycut.models import ProjectInput
from mycut.config import DATA
from mycut.production import make_video, estimated_timing

NARRATION = ('Seu pedido chega ao agente de IA, que chama uma ferramenta. '
             'A ferramenta devolve os dados e o agente monta a resposta para você.')


def reference_flow(anchors=True):
    """Usuário → Agente de IA → Ferramenta → Resposta, the example from MYC-1."""
    words = ['pedido', 'chama', 'devolve', 'resposta'] if anchors else [None]*4
    return {
        'nodes': [
            {'id': 'usuario', 'label': 'Usuário', 'icon': 'user', 'shape': 'circle', 'x': 20, 'y': 14, 'size': 22, 'chart': None},
            {'id': 'agente', 'label': 'Agente de IA', 'icon': 'bot', 'shape': 'rounded', 'x': 50, 'y': 46, 'size': 24, 'chart': None},
            {'id': 'ferramenta', 'label': 'Ferramenta', 'icon': 'wrench', 'shape': 'circle', 'x': 80, 'y': 14, 'size': 22, 'chart': None},
            {'id': 'resposta', 'label': 'Resposta', 'icon': None, 'shape': 'rounded', 'x': 50, 'y': 84, 'size': 56,
             'chart': {'kind': 'bars', 'values': [12, 30, 54], 'labels': ['seg', 'ter', 'qua'], 'maximum': None, 'unit': '%'}},
        ],
        'links': [{'source': 'usuario', 'target': 'agente'}, {'source': 'agente', 'target': 'ferramenta'},
                  {'source': 'agente', 'target': 'resposta'}],
        'steps': [{'source': 'usuario', 'target': 'agente', 'kind': 'request', 'anchor': words[0]},
                  {'source': 'agente', 'target': 'ferramenta', 'kind': 'request', 'anchor': words[1]},
                  {'source': 'ferramenta', 'target': 'agente', 'kind': 'result', 'anchor': words[2]},
                  {'source': 'agente', 'target': 'resposta', 'kind': 'result', 'anchor': words[3]}],
    }


def difference(first, second):
    return sum(ImageStat.Stat(ImageChops.difference(first.convert('RGB'), second.convert('RGB'))).mean)/3


class AnimatedFlowTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs')
            db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'Fluxo animado'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def edit(self, **changes):
        body = {key: self.project[key] for key in ProjectInput.model_fields}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        if response.status_code == 200:
            self.project = response.json()
        return response

    def flow_scene(self, spec=None, font_size=30):
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['narration'] = NARRATION
        scene['blocks'][0]['object'] = scene_layout.VisualObject(type='title', text='Como o agente responde', font_size=64).model_dump()
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='flow', font_size=font_size, flow=spec).model_dump()
        return scene

    def test_reference_flow_is_saved_reopened_and_older_objects_keep_their_shape(self):
        scene = self.flow_scene(reference_flow())
        response = self.edit(scenes=[scene])
        self.assertEqual(response.status_code, 200, response.text)
        store.initialize()
        saved = store.get_project(self.project['id'])['scenes'][0]['blocks']
        self.assertEqual(saved[1]['object']['flow'], scene_layout.VisualObject.model_validate(scene['blocks'][1]['object']).model_dump()['flow'])
        self.assertEqual(saved[1]['object']['type'], 'flow')
        # A title (or any existing object) is stored exactly as before: no flow key at all.
        self.assertNotIn('flow', saved[0]['object'])
        self.assertNotIn('flow', scene_layout.VisualObject(type='image').model_dump())

    def test_invalid_flows_are_rejected(self):
        broken = []
        spec = reference_flow()
        spec['steps'][0]['target'] = 'ninguem'
        broken.append(spec)
        spec = reference_flow()
        spec['links'] = spec['links'][:1]
        broken.append(spec)  # a pulse without a connection
        spec = reference_flow()
        spec['nodes'][0]['icon'] = 'icone-inexistente'
        broken.append(spec)
        spec = reference_flow()
        spec['nodes'][3]['chart'] = {'kind': 'gauge', 'values': [10, 20], 'labels': [], 'maximum': None, 'unit': ''}
        broken.append(spec)
        for spec in broken:
            scene = self.flow_scene(reference_flow())
            scene['blocks'][1]['object']['flow'] = spec
            self.assertEqual(self.edit(scenes=[scene]).status_code, 422)
        scene = self.flow_scene()
        scene['blocks'][0]['object']['flow'] = reference_flow()
        self.assertEqual(self.edit(scenes=[scene]).status_code, 422)

    def test_missing_flow_and_label_overflow_save_as_draft_but_block_export(self):
        scene = self.flow_scene(None)
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        issues = block_render.inspect(scene, self.project)['issues']
        self.assertEqual([i['kind'] for i in issues], ['missing_flow'])
        with self.assertRaisesRegex(ValueError, 'Fluxo animado'):
            block_render.validate_project(self.project)
        spec = reference_flow()
        spec['nodes'][1]['label'] = 'Agente de inteligência IA'
        scene = self.flow_scene(spec, font_size=90)
        report = self.client.post('/api/scene-layout/inspect', json={'scene': scene, 'accent': self.project['accent'],
                                                                     'project_id': self.project['id']}).json()
        self.assertEqual(report['issues'][0]['kind'], 'overflow')
        fitted = report['issues'][0]['font_size']
        self.assertTrue(fitted and fitted < 90)
        scene['blocks'][1]['object']['font_size'] = fitted
        self.assertFalse(block_render.inspect(scene, self.project)['issues'])
        self.assertEqual(report['clock']['source'], 'estimate')
        self.assertAlmostEqual(report['clock']['duration'], flow.estimate_clock(NARRATION)['duration'])

    def test_anchors_follow_the_narration_and_unanchored_steps_spread_over_the_scene(self):
        clock = flow.estimate_clock(NARRATION)
        words = NARRATION.split()
        anchored = reference_flow()
        self.assertEqual(flow.resolve_anchors(anchored, NARRATION),
                         [words.index('pedido'), words.index('chama'), words.index('devolve'), words.index('resposta')])
        starts = flow.schedule(anchored, NARRATION, clock)
        spoken = [clock['words'][words.index(w)] for w in ('pedido', 'chama', 'devolve', 'resposta')]
        self.assertEqual(starts[:3], spoken[:3])
        # "resposta" is spoken near the end: the step is pulled back so the chart finishes inside the scene.
        latest = clock['duration']-flow.TRAVEL-flow.BUILD-.2
        self.assertGreater(spoken[3], latest)
        self.assertAlmostEqual(starts[3], latest)
        # Multi-word anchors match a phrase; anchors are searched in speaking order.
        phrase = reference_flow()
        phrase['steps'][3]['anchor'] = 'monta a resposta'
        self.assertEqual(flow.resolve_anchors(phrase, NARRATION)[3], words.index('monta'))
        free = flow.schedule(reference_flow(anchors=False), NARRATION, clock)
        self.assertLess(free[0], 1)
        self.assertAlmostEqual(free[-1], clock['duration']-flow.TRAVEL-flow.BUILD-.2)
        self.assertEqual(sorted(free), free)
        partial = reference_flow()
        partial['steps'][1]['anchor'] = None
        partial['steps'][2]['anchor'] = 'palavra-que-nao-existe'
        mixed = flow.schedule(partial, NARRATION, clock)
        self.assertLess(mixed[0], mixed[1])
        self.assertLess(mixed[1], mixed[2])
        self.assertLess(mixed[2], mixed[3])
        self.assertEqual(flow.anchor_warnings(partial, NARRATION), [2])
        scene = self.flow_scene(partial)
        self.assertEqual([w['step'] for w in block_render.inspect(scene, self.project)['warnings']], [2])
        self.assertFalse(block_render.inspect(scene, self.project)['issues'])
        # Aligned narration: the same anchor follows the real spoken time of the word.
        timing = estimated_timing({'scenes': [{'narration': 'Uma frase antes.'}, {'narration': NARRATION}]})
        clock = flow.clock_from_timing(timing, 1)
        self.assertEqual(len(clock['words']), len(words))
        self.assertAlmostEqual(clock['words'][0], 0)

    def test_imported_narration_without_alignment_is_reported_as_synced_at_export(self):
        scene = self.flow_scene(reference_flow())
        project = {'scenes': [scene], 'audio': {'duration': 9.0}}
        project['audio']['script_hash'] = store.script_hash(project)
        self.assertEqual(flow.scene_clock(project, scene)['source'], 'export')
        self.assertEqual(flow.scene_clock(project, {**scene, 'narration': 'Outra fala.'})['source'], 'estimate')
        project['audio']['script_hash'] = 'f'*64
        self.assertEqual(flow.scene_clock(project, scene)['source'], 'estimate')

    def test_timeline_enters_draws_pulses_and_reacts_in_cause_and_effect_order(self):
        clock = flow.estimate_clock(NARRATION)
        spec = reference_flow()
        plan = flow.Plan(spec, NARRATION, clock)
        self.assertLessEqual(plan.arrivals[-1]+flow.BUILD, clock['duration'])
        order = ['usuario', 'agente', 'ferramenta', 'resposta']
        self.assertEqual(sorted(order, key=plan.appear.get), order)
        for i, step in enumerate(spec['steps']):
            lane = plan.lanes[(frozenset((step['source'], step['target'])), step['kind'])] if i != 2 else None
            if lane:
                self.assertLessEqual(lane['end'], plan.starts[i]+1e-9)
            self.assertGreater(plan.arrivals[i], plan.starts[i])
            self.assertGreaterEqual(plan.starts[i], plan.appear[step['target']])
        # The agent highlights on arrival, works, then its departure (sending) starts the next step.
        arrival, departure = plan.arrivals[0], plan.starts[1]
        glow, working, burst, received = plan.work('agente', arrival+.01)
        self.assertGreater(glow, .9)
        self.assertTrue(received)
        self.assertTrue(plan.work('agente', arrival+flow.HIGHLIGHT+.1)[1])
        self.assertFalse(plan.work('agente', departure+.01)[1])
        self.assertIsNotNone(plan.work('agente', departure+.01)[2])
        self.assertFalse(plan.work('ferramenta', departure-.01)[3])
        # Results use their own lane, beside the request lane on the same connection.
        layout = flow.Layout(scene_layout.VisualObject(type='flow', font_size=30, flow=spec).model_dump(), 940, 816,
                             {'text_color': '#29231F', 'background': '#FBF8F1', 'accent': '#c85e37'})
        self.assertNotEqual(layout.lane('agente', 'ferramenta', 'request'), layout.lane('ferramenta', 'agente', 'result')[::-1])

    def test_rendered_states_change_over_time_and_charts_build_progressively(self):
        scene = self.flow_scene(reference_flow())
        project = store.get_project(self.project['id'])
        composition = block_render.BlockComposition(scene, project)
        renderer = composition.flows[0][0]
        plan = renderer.plan
        x, y, w, h = map(round, scene_layout.geometry(scene['blocks'])[1]['object'])
        crop = lambda t: composition.frame(t).crop((x, y, x+w, y+h))
        empty = crop(0)
        middle = crop(plan.starts[1]+.2)
        final = crop(None)
        self.assertGreater(difference(empty, middle), .5)
        self.assertGreater(difference(middle, final), .5)
        self.assertEqual(difference(final, crop(plan.end+1)), 0)
        # Chart: bars grow over the build, then stay complete.
        node = renderer.layout.nodes['resposta']
        box = tuple(round(v) for v in (node['cx']-node['hw'], node['cy']-node['hh'], node['cx']+node['hw'], node['cy']+node['hh']))
        accent = lambda image: sum(1 for r, g, b, a in image.crop(box).get_flattened_data() if a > 200 and r > 170 and g < 120 and b < 90)
        begin = plan.arrivals[3]
        sizes = [accent(renderer.layer(begin+offset)) for offset in (.1, .45, .8, 1.5)]
        self.assertEqual(sorted(sizes), sizes)
        self.assertGreater(sizes[-1], sizes[0]*2)
        composition.close()

    def test_existing_objects_stay_static(self):
        scene = self.flow_scene(None)
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='paragraph', text='Texto estático', font_size=40).model_dump()
        composition = block_render.BlockComposition(scene, store.get_project(self.project['id']))
        self.assertEqual(composition.flows, [])
        self.assertEqual(difference(composition.frame(0), composition.frame(4.5)), 0)
        self.assertEqual(difference(composition.frame(0), composition.frame(None)), 0)

    def test_preview_matches_exported_mp4_at_three_scene_times(self):
        scene = self.flow_scene(reference_flow())
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        clock = flow.estimate_clock(NARRATION)
        plan = flow.Plan(reference_flow(), NARRATION, clock)
        fps = 24
        # Frame-aligned instants inside the pulse to the tool, the result coming back and the chart build.
        times = [round((plan.starts[1]+.25)*fps)/fps, round((plan.starts[2]+.3)*fps)/fps, round((plan.arrivals[3]+.4)*fps)/fps]
        store.enqueue(self.project['id'], 'preview', self.project['revision'])
        result = make_video(store.claim())
        video = DATA / result['directory'] / 'short.mp4'
        x, y, w, h = scene_layout.geometry(scene['blocks'])[1]['object']
        box = tuple(round(v/2) for v in (x, y, x+w, y+h))
        exported, previews = [], []
        for t in times:
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf', f'select=eq(n\\,{round(t*fps)})',
                                           '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', 'pipe:1'])
            with Image.open(io.BytesIO(raw)) as image:
                exported.append(image.convert('RGB').crop(box))
            response = self.client.post('/api/scene-preview', json={'scene': scene, 'project_id': self.project['id'],
                                        'accent': self.project['accent'], 'elapsed': t, 'width': 'full'})
            self.assertEqual(response.status_code, 200, response.text)
            with Image.open(io.BytesIO(response.content)) as image:
                previews.append(image.convert('RGB').resize((540, 960), Image.Resampling.LANCZOS).crop(box))
        for i, (preview, frame) in enumerate(zip(previews, exported)):
            same = difference(preview, frame)
            self.assertLess(same, 2.5, (times[i], same))
            for j, other in enumerate(exported):
                if j != i:
                    self.assertGreater(difference(preview, other), same+.3, (times[i], times[j]))

    def test_agent_builds_the_chosen_flow_through_a_reviewed_proposal(self):
        scene = self.flow_scene(None)
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        scene = self.project['scenes'][0]
        target = scene['blocks'][1]['object']['id']
        body = scene_chat.MessageRequest(scene_id=scene['id'], scope='object', target_id=target,
                                         text='Monte um Fluxo animado.', revision=self.project['revision'])
        with patch.object(scene_chat.bridge, 'require'), patch.object(scene_chat.agent_models, 'validate'):
            job_id = scene_chat.enqueue(self.project['id'], body)['id']
        job = store.get_job(job_id, private=True)
        bad, good = copy.deepcopy(scene['blocks']), copy.deepcopy(scene['blocks'])
        broken = reference_flow()
        broken['steps'][0]['anchor'] = 'palavra ausente'
        bad[1]['object']['flow'] = broken
        good[1]['object']['flow'] = reference_flow()
        replies = iter([scene_chat.Proposal(reply='Primeira versão.', blocks=bad), scene_chat.Proposal(reply='Fluxo montado.', blocks=good)])
        calls = []

        def fake_agent(job, role, instructions, payload, model, attempt=1, **_):
            calls.append(payload['issues_to_fix'])
            self.assertIn('Fluxo animado', instructions)
            self.assertIn('bot', payload['flow_icons'])
            return next(replies)
        with patch('mycut.pipeline.agent', side_effect=fake_agent):
            scene_chat.run(job)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], [])
        self.assertIn('âncora', calls[1][0])
        output = json.loads((DATA / 'projects' / self.project['id'] / 'renders' / job_id / 'result.json').read_text())
        store.finish(job_id, 'succeeded', 'Proposta pronta', output)
        message = scene_chat.messages(self.project['id'])['messages'][0]
        self.assertFalse(message['stale'])
        accepted = self.client.post(f'/api/projects/{self.project["id"]}/scene-proposals/{job_id}',
                                    json={'decision': 'accepted', 'revision': self.project['revision']})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        saved = accepted.json()['scenes'][0]['blocks'][1]['object']
        self.assertEqual([n['id'] for n in saved['flow']['nodes']], ['usuario', 'agente', 'ferramenta', 'resposta'])

    def test_director_puts_the_flow_in_new_productions_and_corrects_bad_anchors(self):
        visual = pipeline.Visual(title='Como o agente responde', layout='flow', items=['Pedido', 'Resposta'],
                                 flow=reference_flow())
        scene = pipeline.directed_scene(visual, NARRATION, self.project)
        self.assertEqual(scene['blocks'][1]['object']['type'], 'flow')
        self.assertEqual(scene['blocks'][0]['object']['text'], 'Como o agente responde')
        self.assertNotIn('flow', scene)
        legacy = pipeline.directed_scene(visual, NARRATION, {'scenes': [{'blocks': None}]})
        self.assertIsNone(legacy['blocks'])
        with self.assertRaises(ValueError):
            pipeline.Visual(title='X', layout='flow', items=['a', 'b'], flow=reference_flow(), image_id='a'*32)
        broken = reference_flow()
        broken['steps'][1]['anchor'] = 'inexistente'
        answers = iter([pipeline.Direction(accent='#c85e37', scenes=[{**visual.model_dump(), 'flow': broken}]),
                        pipeline.Direction(accent='#c85e37', scenes=[visual])])
        seen = []

        def fake_agent(job, role, instructions, payload, model, attempt=1, **_):
            seen.append((instructions, payload))
            return next(answers)
        job = {'id': 'x', 'snapshot': {**self.project, 'accent_locked': True}}
        with patch.object(pipeline, 'agent', side_effect=fake_agent):
            direction = pipeline.create_direction(job, {'narration': [NARRATION]}, {}, [])
        self.assertEqual(len(seen), 2)
        self.assertIn('Fluxo animado', seen[0][0])
        self.assertIn('wrench', seen[0][1]['flow_icons'])
        self.assertIn('scenes[0].flow', seen[1][1]['issues_to_fix'][-1])
        self.assertIsNotNone(direction.scenes[0].flow)


    def direct(self, answer):
        """create_direction with a director that returns the same flow on every attempt."""
        visual = pipeline.Visual(title='Como o agente responde', layout='flow', items=['Pedido', 'Resposta'], flow=answer)
        calls = []

        def fake_agent(job, role, instructions, payload, model, attempt=1, **_):
            calls.append(payload['issues_to_fix'])
            return pipeline.Direction(accent='#c85e37', scenes=[visual.model_dump()])
        job = {'id': 'x', 'snapshot': {**self.project, 'accent_locked': True}}
        with patch.object(pipeline, 'agent', side_effect=fake_agent):
            direction = pipeline.create_direction(job, {'narration': [NARRATION]}, {}, [])
        self.assertEqual(len(calls), 2)
        return direction.scenes[0], pipeline.directed_scene(direction.scenes[0], NARRATION, self.project)

    def test_last_attempt_drops_unknown_anchors_instead_of_failing_the_production(self):
        answer = reference_flow()
        answer['steps'][1]['anchor'] = 'palavra que nunca foi dita'
        visual, scene = self.direct(answer)
        steps = scene['blocks'][1]['object']['flow']['steps']
        self.assertEqual([s['anchor'] for s in steps], ['pedido', None, 'devolve', 'resposta'])
        self.assertEqual(scene['blocks'][1]['object']['font_size'], pipeline.FLOW_FONT)
        self.assertFalse(block_render.inspect(scene, self.project)['warnings'])

    def test_last_attempt_fits_labels_or_falls_back_to_the_paragraph(self):
        crowded = reference_flow()
        crowded['nodes'][3].update(size=34, label='Resposta final do agente')  # a chart title must fit on one line
        visual, scene = self.direct(crowded)
        obj = scene['blocks'][1]['object']
        self.assertEqual(obj['type'], 'flow')
        self.assertLess(obj['font_size'], pipeline.FLOW_FONT)
        self.assertFalse(block_render.inspect(scene, self.project)['issues'])
        impossible = reference_flow()
        impossible['nodes'][3].update(size=6, label='Resposta final do agente')
        visual, scene = self.direct(impossible)
        self.assertIsNone(visual.flow)
        self.assertEqual(scene['blocks'][1]['object']['type'], 'paragraph')
        self.assertEqual(scene['blocks'][1]['object']['text'], 'Pedido\n\nResposta')


if __name__ == '__main__':
    unittest.main()
