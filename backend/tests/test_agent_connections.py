"""Diagnostics exercise ASGI + file queue + real subprocesses, with fixture CLIs."""
import copy
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import test_studio
from mycut import agent_models, agent_runner, agent_tests, browser, bridge, commands, integrations


def uuid_hex():
    import uuid
    return uuid.uuid4().hex


class AgentConnectionTests(unittest.TestCase):
    def setUp(self):
        test_studio.StudioTests.setUp(self)
        shutil.rmtree(bridge.BRIDGE, ignore_errors=True)
        integrations.save_section('commands', commands.DEFAULTS)
        integrations.save_section('browser', integrations.DEFAULTS['browser'])
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

    def test_configured_command_runs_on_host_with_its_variables(self):
        self.assertEqual(integrations.public()['commands'], {p: p for p in bridge.PROVIDERS})
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {'HOME': home}):
            script = Path(home)/'fake-claude.py'
            script.write_text(
                'import json, os, re, sys\n'
                'prompt = sys.stdin.read()\n'
                'challenge = re.search(r\'challenge="(\\w+)"\', prompt)[1]\n'
                'number = int(re.search(r\'Calcule (\\d+)\\+17\', prompt)[1])\n'
                'print(json.dumps({"structured_output": {"challenge": challenge, "answer": number+17,\n'
                '      "reply": os.environ["MYCUT_FIXTURE"]}, "modelUsage": {"claude-model": {"outputTokens": 1}}}))\n')
            command = f'MYCUT_FIXTURE=~/perfil {shlex.quote(sys.executable)} {shlex.quote(str(script))}'
            response = self.client.put('/api/integrations/commands', json={'codex': 'codex', 'claude': command, 'grok': 'grok'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['commands']['claude'], command)
            self.assertTrue((bridge.BRIDGE/'refresh-models').exists())
            _, folder = self.start()
            agent_runner.run_request(folder/'request.json')
            result = self.client.get('/api/integrations/agents/tests/'+folder.name).json()
        self.assertEqual(result['state'], 'succeeded', result)
        self.assertEqual(result['reply'], home+'/perfil')
        self.assertEqual(result['verification'], 'match')

    def test_invalid_or_missing_commands_are_reported(self):
        for command in ('', 'CLAUDE_CONFIG_DIR=/tmp/x', 'claude "aberto', 'claude\n--help'):
            response = self.client.put('/api/integrations/commands', json={'codex': 'codex', 'claude': command, 'grok': 'grok'})
            self.assertEqual(response.status_code, 422, command)
        self.assertEqual(integrations.public()['commands']['claude'], 'claude')
        integrations.save_section('commands', {'grok': 'mycut-command-that-does-not-exist'})
        self.assertIsNone(commands.launcher('grok'))
        with self.assertRaisesRegex(ValueError, 'Confira o comando em Conexões'):
            agent_runner.command('grok', '', Path(tempfile.gettempdir()), {}, False)
        agent_runner.heartbeat()
        self.assertFalse(bridge.status()['providers']['grok'])

    def test_browser_is_offered_to_each_cli_with_only_reading_tools(self):
        navigator = {'command': '/bin/npx', 'args': ['-y', browser.PACKAGE, '--browserUrl=http://127.0.0.1:9222']}
        schema = {'type': 'object'}
        with tempfile.TemporaryDirectory() as temp, patch.object(commands.shutil, 'which', side_effect=lambda name: '/bin/'+name):
            folder = Path(temp)
            claude = agent_runner.command('claude', '', folder, schema, True, navigator)
            config = json.loads(claude[claude.index('--mcp-config')+1])
            self.assertEqual(config['mcpServers'], {'navegador': navigator})
            allowed = claude[claude.index('--allowedTools')+1].split(',')
            self.assertIn('mcp__navegador__take_snapshot', allowed)
            self.assertNotIn('mcp__navegador__fill', allowed)
            codex = ' '.join(agent_runner.command('codex', '', folder, schema, True, navigator))
            self.assertIn('enabled_tools = ["navigate_page"', codex)
            self.assertIn('new_page = {approval_mode = "approve"}', codex)
            self.assertNotIn('fill_form', codex)
            grok = agent_runner.command('grok', '', folder, schema, True, navigator)
            self.assertEqual(grok[:3], ['env', 'GROK_CLAUDE_MCPS_ENABLED=false', 'GROK_CURSOR_MCPS_ENABLED=false'])
            self.assertIn('--trust', grok)
            self.assertIn('MCPTool(navegador__click)', grok)
            self.assertNotIn('MCPTool', grok)  # A global deny would override the browser allows.
            self.assertIn('chrome-devtools-mcp', (folder/'.grok'/'config.toml').read_text())
            # Without the browser, every MCP server stays closed.
            self.assertIn('{"mcpServers": {}}', agent_runner.command('claude', '', folder, schema, True))
            self.assertIn('mcp_servers={}', agent_runner.command('codex', '', folder, schema, True))
            self.assertIn('MCPTool', agent_runner.command('grok', '', folder, schema, True))

    def test_research_prompt_explains_browser_or_its_absence(self):
        prompts = []
        def capture(provider, model, folder, schema, web, navigator=None):
            prompts.append(((folder/'prompt.txt').read_text(), navigator))
            return [sys.executable, '-c', 'print(\'{"structured_output": {"ok": true}}\')']
        for prepared in ((None, 'Chrome não encontrado no Windows.'), ({'command': 'npx', 'args': []}, '')):
            folder = bridge.BRIDGE/'requests'/uuid_hex()
            folder.mkdir(parents=True)
            (folder/'lease').touch()
            bridge.atomic_json(folder/'request.json', {'provider': 'claude', 'model': '', 'prompt': 'Pesquise.',
                               'schema': {'type': 'object'}, 'web': True, 'expires': time.time()+30})
            with patch.object(browser, 'prepare', return_value=prepared), patch.object(agent_runner, 'command', side_effect=capture):
                agent_runner.run_request(folder/'request.json')
            self.assertEqual(json.loads((folder/'response.json').read_text()), {'result': {'ok': True}, 'usage': []})
        self.assertIn('NAVEGADOR INDISPONÍVEL: Chrome não encontrado no Windows.', prompts[0][0])
        self.assertIsNone(prompts[0][1])
        self.assertIn('take_snapshot', prompts[1][0])
        self.assertEqual(prompts[1][1], {'command': 'npx', 'args': []})

    def test_grok_interim_objects_keep_the_final_answer(self):
        output = json.dumps({'text': '{"title":""}{"title":"Final"}', 'structuredOutput': None})
        self.assertEqual(agent_runner.parse_result('grok', Path(tempfile.gettempdir()), output), {'title': 'Final'})

    def test_browser_settings_and_test_round_trip(self):
        for body in ({'enabled': True, 'chrome_path': '', 'port': 80}, {'enabled': True, 'chrome_path': 'a\nb', 'port': 9222}):
            self.assertEqual(self.client.put('/api/integrations/browser', json=body).status_code, 422)
        body = {'enabled': True, 'chrome_path': ' C:\\Chrome\\chrome.exe ', 'port': 9333}
        saved = self.client.put('/api/integrations/browser', json=body).json()
        self.assertEqual(saved['browser'], {'enabled': True, 'chrome_path': 'C:\\Chrome\\chrome.exe', 'port': 9333})
        response = self.client.post('/api/integrations/browser/test')
        self.assertEqual(response.status_code, 422)  # Runner from before the browser.
        self.assertIn('Reinicie', response.text)
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time': time.time(), 'protocol': 3, 'providers': {},
                           'browser': {'enabled': True, 'available': False, 'version': ''}})
        test_id = self.client.post('/api/integrations/browser/test').json()['id']
        with patch.object(browser, 'probe', return_value='Chrome/157.0'):
            agent_runner.test_browser()
        result = self.client.get('/api/integrations').json()
        self.assertEqual(result['browser_test']['id'], test_id)
        self.assertEqual(result['browser_test']['version'], 'Chrome/157.0')
        self.assertFalse((bridge.BRIDGE/'browser-test').exists())
        self.client.post('/api/integrations/browser/test')
        with patch.object(browser, 'probe', side_effect=ValueError('Chrome não encontrado no Windows.')):
            agent_runner.test_browser()
        self.assertIn('Chrome não encontrado', self.client.get('/api/integrations').json()['browser_test']['error'])
        self.client.put('/api/integrations/browser', json={**body, 'enabled': False})
        self.assertEqual(browser.prepare(), (None, ''))
        self.assertEqual(self.client.post('/api/integrations/browser/test').status_code, 422)

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
