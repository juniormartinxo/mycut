"""Regression for agent-approved empty diagrams; provider calls stay simulated."""
import copy
import unittest
from unittest.mock import patch
import test_automation as fixtures
from mycut import bridge, elevenlabs, integrations, pipeline, store


class SceneAgentTests(unittest.TestCase):
    setUp = fixtures.AutomationTests.setUp
    tearDown = fixtures.AutomationTests.tearDown
    edit = fixtures.AutomationTests.edit
    fill = fixtures.AutomationTests.fill
    configure = fixtures.AutomationTests.configure
    start = fixtures.AutomationTests.start

    def runner(self, repair=False):
        self.director_calls = []
        def invoke(config, prompt, schema, **kwargs):
            if schema['title'] == 'Direction':
                self.director_calls.append(prompt)
                result = copy.deepcopy(fixtures.DIRECTION)
                if not repair or len(self.director_calls) == 1:
                    for scene in result['scenes']:
                        scene['items'] = []
                return result
            return {'Research': fixtures.RESEARCH, 'Script': fixtures.SCRIPT,
                    'Review': {'approved': True, 'issues': []}}[schema['title']]
        return invoke

    def test_empty_diagrams_cannot_pass_even_when_reviewer_approves(self):
        job = self.start('plan')
        with patch.object(bridge, 'invoke', side_effect=self.runner()), patch.object(elevenlabs, 'synthesize') as voice:
            with self.assertRaisesRegex(ValueError, 'direção|visua'):
                pipeline.produce(job)
            voice.assert_not_called()
        self.assertEqual(len(self.director_calls), 2)
        self.assertEqual(store.get_project(self.project['id'])['revision'], self.project['revision'])

    def test_incomplete_direction_is_corrected_before_it_is_published(self):
        job = self.start('plan')
        with patch.object(bridge, 'invoke', side_effect=self.runner(repair=True)):
            pipeline.produce(job)
        saved = store.get_project(self.project['id'])
        self.assertEqual([s['items'] for s in saved['scenes']], [s['items'] for s in fixtures.DIRECTION['scenes']])
        self.assertEqual(len(self.director_calls), 2)
        self.assertIn('items', self.director_calls[1])

    def test_color_chosen_at_creation_survives_the_agents(self):
        self.configure()
        response = self.client.post('/api/projects', json={
            'title': 'Cor definida antes', 'brief': 'Pauta de teste', 'automation': 'plan', 'accent': '#123456'})
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()
        self.assertEqual(project['accent'], '#123456')
        self.assertTrue(project['accent_locked'])
        store.claim()
        job = store.get_job(project['jobs'][0]['id'], private=True)
        with patch.object(bridge, 'invoke', side_effect=[fixtures.RESEARCH, fixtures.SCRIPT, fixtures.DIRECTION, {'approved': True, 'issues': []}]):
            pipeline.produce(job)
        self.assertEqual(store.get_project(project['id'])['accent'], '#123456')

    def test_visual_only_run_keeps_narration_audio_and_color(self):
        self.configure()
        self.edit(scenes=[{**s, 'narration': n} for s, n in zip(fixtures.DIRECTION['scenes'], fixtures.PARAGRAPHS)], accent='#123456', accent_locked=True)
        current = store.get_project(self.project['id'])
        audio = {'path': 'unchanged.wav', 'sha256': 'original', 'script_hash': store.script_hash(current)}
        current = store.update_project(current['id'], {'audio': audio, 'research': fixtures.RESEARCH}, current['revision'])
        response = self.client.post(f'/api/projects/{current["id"]}/run', json={'kind': 'scenes', 'revision': current['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        store.claim()
        job = store.get_job(response.json()['id'], private=True)
        with patch.object(bridge, 'invoke', side_effect=[fixtures.DIRECTION, {'approved': True, 'issues': []}]) as invoke, patch.object(elevenlabs, 'synthesize') as voice:
            pipeline.produce(job)
            self.assertEqual([c.args[2]['title'] for c in invoke.call_args_list], ['Direction', 'Review'])
            voice.assert_not_called()
        saved = store.get_project(current['id'])
        self.assertEqual([s['narration'] for s in saved['scenes']], fixtures.PARAGRAPHS)
        self.assertEqual(saved['audio'], audio)
        self.assertEqual(saved['accent'], current['accent'])

    def test_blank_labels_and_incomplete_comparisons_are_rejected(self):
        for layout, items in [('flow', []), ('flow', ['Só um']), ('flow', ['A', '  ']), ('comparison', ['A']), ('comparison', ['A', 'B', 'C']), ('statement', ['\n'])]:
            with self.subTest(layout=layout, items=items), self.assertRaises(ValueError):
                pipeline.Visual.model_validate({'title': 'Cena', 'layout': layout, 'items': items})

    def test_automatic_color_is_chosen_by_the_director(self):
        job = self.start('plan')
        self.assertFalse(job['snapshot']['accent_locked'])
        with patch.object(bridge, 'invoke', side_effect=[fixtures.RESEARCH, fixtures.SCRIPT, fixtures.DIRECTION, {'approved': True, 'issues': []}]):
            pipeline.produce(job)
        self.assertEqual(store.get_project(self.project['id'])['accent'], fixtures.DIRECTION['accent'])

    def test_provider_failure_is_not_treated_as_invalid_output_to_retry(self):
        job = self.start('plan')
        with patch.object(bridge, 'invoke', side_effect=[fixtures.RESEARCH, fixtures.SCRIPT, ValueError('CLI indisponível')]) as invoke:
            with self.assertRaisesRegex(ValueError, 'CLI indisponível'):
                pipeline.produce(job)
        self.assertEqual(invoke.call_count, 3)
        self.assertEqual(store.get_project(self.project['id'])['revision'], self.project['revision'])

    def test_visual_only_run_requires_script_but_not_research_cli_or_voice(self):
        self.configure()
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time': fixtures.time.time(), 'providers': {'codex': True, 'grok': False, 'claude': False}})
        agents = integrations.read()['agents']
        agents['director'] = agents['reviewer'] = {'provider': 'codex', 'model': ''}
        integrations.save_section('agents', agents)
        integrations.save_section('elevenlabs', {'api_key': '', 'voice_id': ''})
        url = f'/api/projects/{self.project["id"]}/run'
        invalid = self.client.post(url, json={'kind': 'scenes', 'revision': self.project['revision']})
        self.assertEqual(invalid.status_code, 409, invalid.text)
        self.fill()
        # This endpoint is the legacy diagram flow; blocks use reviewed proposals.
        self.edit(scenes=[{k: v for k, v in scene.items() if k not in ('id', 'blocks')}
                          for scene in self.project['scenes']])
        valid = self.client.post(url, json={'kind': 'scenes', 'revision': self.project['revision']})
        self.assertEqual(valid.status_code, 202, valid.text)
