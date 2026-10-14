"""Diagnostics exercise ASGI + file queue + real subprocesses, with fixture CLIs."""
import copy
import json
import shutil
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import test_studio
from mycut import agent_models, agent_runner, agent_tests, bridge, integrations


class AgentConnectionTests(unittest.TestCase):
    def setUp(self):
        test_studio.StudioTests.setUp(self)
        shutil.rmtree(bridge.BRIDGE, ignore_errors=True)
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {
            'time': time.time(), 'protocol': 2, 'providers': {p: True for p in bridge.PROVIDERS}})
        bridge.atomic_json(bridge.BRIDGE/'models.json', {
            p: {'models': [{'id': p+'-model', 'name': p.title()+' Model'}],
                'checked_at': time.time(), 'source': 'cache', 'error': ''} for p in bridge.PROVIDERS})
        self.choice = {'role': 'writer', 'provider': 'claude', 'model': 'claude-model'}

    tearDown = test_studio.StudioTests.tearDown

    def start(self, choice=None):
        response = self.client.post('/api/integrations/agents/tests', json=choice or self.choice)
        self.assertEqual(response.status_code, 202, response.text)
        result = response.json()
        return result, bridge.BRIDGE/'requests'/result['id']

    def execute(self, folder, reported='claude-model', bad_challenge=False, author_metadata=False):
        request = json.loads((folder/'request.json').read_text())
        result = {'challenge': 'wrong' if bad_challenge else request['challenge'],
                  'answer': request['answer'], 'reply': 'Recebi a solicitação.'}
        envelope = {'structured_output': result}
        if reported:
            target = result if author_metadata else envelope
            target['modelUsage'] = {reported: {'inputTokens': 20, 'outputTokens': 10}}
        args = [sys.executable, '-c', 'print('+repr(json.dumps(envelope))+')']
        with patch.object(agent_runner, 'command', return_value=args):
            agent_runner.run_request(folder/'request.json')
        return self.client.get('/api/integrations/agents/tests/'+folder.name).json()

    def test_probe_uses_unsaved_selection_and_confirms_envelope_model(self):
        before = copy.deepcopy(integrations.public()['agents'])
        initial, folder = self.start()
        self.assertEqual(initial['state'], 'queued')
        result = self.execute(folder)
        self.assertEqual(result['state'], 'succeeded', result)
        self.assertEqual(result['verification'], 'match')
        self.assertEqual(result['reported_models'], ['claude-model'])
        self.assertGreater(result['elapsed'], 0)
        self.assertEqual(integrations.public()['agents'], before)
        self.assertEqual(self.client.get('/api/integrations/agents/tests').json()['writer']['id'], initial['id'])

    def test_wrong_model_is_visible_not_a_successful_identity_check(self):
        _, folder = self.start()
        result = self.execute(folder, reported='other-model')
        self.assertEqual(result['state'], 'succeeded')
        self.assertEqual(result['verification'], 'mismatch')

    def test_model_authored_identity_does_not_confirm_model(self):
        _, folder = self.start()
        result = self.execute(folder, author_metadata=True)
        self.assertEqual(result['verification'], 'unknown')
        self.assertEqual(result['reported_models'], [])
        self.assertEqual(agent_models.reported_models('codex', '{"modelUsage":{"codex-model":{"inputTokens":5}}}'), [])

    def test_default_model_is_resolved_and_wrong_challenge_fails(self):
        _, folder = self.start({**self.choice, 'model': ''})
        self.assertEqual(self.execute(folder)['verification'], 'resolved')
        _, folder = self.start()
        result = self.execute(folder, bad_challenge=True)
        self.assertEqual(result['state'], 'failed')
        self.assertIn('não cumpriu', result['error'])

    def test_unknown_cross_provider_and_display_names_rejected_before_queueing(self):
        for value in ('grok-model', 'Claude Model', 'CLAUDE-MODEL', 'invented'):
            response = self.client.post('/api/integrations/agents/tests', json={**self.choice, 'model': value})
            self.assertEqual(response.status_code, 422, response.text)
        settings = copy.deepcopy(integrations.DEFAULTS['agents'])
        settings['writer'] = {'provider': 'claude', 'model': 'grok-model'}
        self.assertEqual(self.client.put('/api/integrations/agents', json=settings).status_code, 422)
        self.assertEqual(list((bridge.BRIDGE/'requests').glob('*')), [])

    def test_single_active_probe_cancel_and_expiration(self):
        initial, folder = self.start()
        self.assertEqual(self.client.post('/api/integrations/agents/tests', json=self.choice).status_code, 409)
        cancelled = self.client.post('/api/integrations/agents/tests/'+initial['id']+'/cancel').json()
        self.assertEqual(cancelled['state'], 'cancelled')
        with patch.object(agent_runner.subprocess, 'Popen') as process:
            agent_runner.run_request(folder/'request.json')
            process.assert_not_called()
        _, folder = self.start()
        request = json.loads((folder/'request.json').read_text())
        bridge.atomic_json(folder/'request.json', {**request, 'expires': time.time()-1})
        self.assertEqual(agent_tests.get(folder.name)['state'], 'expired')
        with patch.object(agent_runner.subprocess, 'Popen') as process:
            agent_runner.run_request(folder/'request.json')
            process.assert_not_called()

    def test_cancel_running_process_and_reject_late_success(self):
        _, folder = self.start()
        (folder/'started').touch()
        self.assertEqual(agent_tests.cancel(folder.name)['state'], 'cancelling')
        bridge.atomic_json(folder/'response.json', {'result': {'reply': 'late'}, 'reported_models': ['claude-model']})
        self.assertEqual(agent_tests.get(folder.name)['state'], 'cancelled')

    def test_cancel_terminates_real_child_without_leaving_runner_busy(self):
        _, folder = self.start()
        args = [sys.executable, '-c', 'import time;time.sleep(30)']
        timer = threading.Timer(.2, lambda: (folder/'cancel').touch())
        started = time.monotonic()
        timer.start()
        try:
            with patch.object(agent_runner, 'command', return_value=args):
                agent_runner.run_request(folder/'request.json')
        finally:
            timer.cancel()
        self.assertLess(time.monotonic()-started, 5)
        self.assertEqual(agent_tests.get(folder.name)['state'], 'cancelled')

    def test_cli_errors_are_actionable_without_forwarding_private_output(self):
        for diagnostic, expected in [('OAuth session expired and could not be refreshed', 'entre novamente'),
                                     ('EACCES permission denied /private/account', 'permissão local'),
                                     ('rate limit', 'limite de uso'), ('model not found', 'recusou o modelo')]:
            message = agent_runner.failure_message('claude', diagnostic+' secret-key', '', 'test-id')
            self.assertIn(expected, message)
            self.assertNotIn('secret-key', message)
            self.assertNotIn('/private/account', message)

    def test_old_runner_requires_restart_and_paths_are_private(self):
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time': time.time(), 'providers': {'claude': True}})
        response = self.client.post('/api/integrations/agents/tests', json=self.choice)
        self.assertEqual(response.status_code, 422)
        self.assertIn('Atualize o executor', response.text)
        self.assertEqual(self.client.get('/api/integrations/agents/tests/not-a-test').status_code, 404)

    def test_cache_discovery_exports_no_keys_and_filters_hidden_models(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'models.json'
            path.write_text(json.dumps({'identity': 'private-account', 'models': {
                'grok-model': {'api_key': 'secret', 'api_base_url': 'private-endpoint',
                               'info': {'name': 'Grok Model', 'extra_headers': {'Authorization': 'secret'}}},
                'hidden-model': {'info': {'hidden': True}},
            }}))
            entries = agent_models.cached_models('grok', path)
            self.assertEqual(entries, [{'id': 'grok-model', 'name': 'Grok Model'}])
            path.write_text(json.dumps({'models': [{'slug': 'codex-model', 'display_name': 'Codex Model', 'visibility': 'list'},
                                                  {'slug': 'hidden-model', 'visibility': 'hide'}]}))
            self.assertEqual(agent_models.cached_models('codex', path), [{'id': 'codex-model', 'name': 'Codex Model'}])

    def test_grok_usage_and_invalid_metadata_are_handled_without_trusting_text(self):
        self.assertEqual(agent_models.reported_models('grok', json.dumps({
            'text': '{"model":"fake"}', 'modelUsage': {'grok-model': {'inputTokens': 10}}})), ['grok-model'])
        for output in ('invalid', '{"modelUsage":[]}', '{"modelUsage":{"model":{"inputTokens":"bad"}}}'):
            self.assertEqual(agent_models.reported_models('grok', output), [])
