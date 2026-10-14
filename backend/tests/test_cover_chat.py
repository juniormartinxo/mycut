"""Cover chat: real API/store/worker code and image decoding; only the agent CLIs are fixtures."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import test_automation as fixtures
from mycut import agent_runner, bridge, commands, costs, covers, store
from mycut.config import DATA

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
       '<rect width="1080" height="1920" fill="#123456"/><image href="anexo-1.png" x="0" y="0" width="540" height="540"/></svg>')


def png(color='#fa4400', size=(600, 400)):
    output = io.BytesIO()
    Image.new('RGB', size, color).save(output, format='PNG')
    return output.getvalue()


class CoverChatTests(unittest.TestCase):
    setUp = fixtures.AutomationTests.setUp
    tearDown = fixtures.AutomationTests.tearDown
    edit = fixtures.AutomationTests.edit
    fill = fixtures.AutomationTests.fill

    def online(self, protocol=bridge.IMAGES_PROTOCOL):
        bridge.atomic_json(bridge.BRIDGE/'heartbeat.json', {'time': time.time(), 'protocol': protocol,
                                                         'providers': {'codex': True, 'claude': True, 'grok': True}})

    def send(self, text='Uma capa com fundo azul', provider='grok', files=()):
        return self.client.post(f'/api/projects/{self.project["id"]}/cover/messages',
                                data={'text': text, 'provider': provider, 'model': ''},
                                files=[('files', (f'ref{i}.png', content, 'image/png')) for i, content in enumerate(files)])

    def generate(self, outputs=(), result=None):
        """Run the claimed cover job with a fake CLI that saves `outputs` like the runner does."""
        prompts = []
        def invoke(config, prompt, schema, attachments=(), images=False, request_id=None, **kwargs):
            prompts.append({'config': config, 'prompt': prompt, 'schema': schema, 'attachments': list(attachments), 'images': images})
            folder = bridge.BRIDGE/'requests'/request_id/'outputs'
            folder.mkdir(parents=True, exist_ok=True)
            for index, content in enumerate(outputs, 1):
                (folder/f'{index}.jpg').write_bytes(content)
            return result or {'message': 'Criei uma capa azul.'}
        job = store.claim(covers=True)
        self.assertIsNotNone(job)
        with patch.object(bridge, 'invoke', side_effect=invoke):
            try:
                output = covers.produce(job)
            except ValueError as exc:
                store.finish(job['id'], 'failed', str(exc))
                raise
        store.finish(job['id'], 'succeeded', 'Imagem pronta', output)
        return job, prompts

    def test_chat_image_runs_beside_production_and_becomes_the_cover_only_when_chosen(self):
        self.online()
        self.fill()
        response = self.send(files=[png()])
        self.assertEqual(response.status_code, 202, response.text)
        message = response.json()
        self.assertEqual((message['state'], message['provider'], len(message['attachments'])), ('queued', 'grok', 1))
        self.assertEqual(self.client.get(message['attachments'][0]['url']).status_code, 200)
        # One generation at a time, but it never locks the script or blocks a production.
        self.assertEqual(self.send('Outra').status_code, 409)
        self.assertEqual(self.edit(title='Editado durante a capa').status_code, 200)
        production = store.enqueue(self.project['id'], 'preview', self.project['revision'])
        self.assertEqual([job['id'] for job in self.client.get(f'/api/projects/{self.project["id"]}').json()['jobs']], [production['id']])
        self.assertEqual(store.claim()['id'], production['id'])
        job, prompts = self.generate([png('#2255aa', (941, 1672))])
        self.assertTrue(prompts[0]['images'])
        self.assertEqual(len(prompts[0]['attachments']), 1)
        data = json.loads(prompts[0]['prompt'].split('\nDADOS:\n')[1])
        self.assertEqual(data['request'], 'Uma capa com fundo azul')
        # The agent sees the project as it was when the message was sent.
        self.assertEqual(data['project']['title'], 'Teste de produção')
        self.assertIn('image_gen', prompts[0]['prompt'])
        chat = self.client.get(f'/api/projects/{self.project["id"]}/cover/messages').json()
        self.assertEqual((chat[0]['state'], chat[0]['reply'], len(chat[0]['images'])), ('succeeded', 'Criei uma capa azul.', 1))
        self.assertNotIn('path', json.dumps(chat))
        image = Image.open(io.BytesIO(self.client.get(chat[0]['images'][0]['url']).content))
        self.assertEqual(image.size, (941, 1672))
        self.assertNotIn('cover', store.get_project(self.project['id']))
        store.cancel(production['id'])
        current = store.get_project(self.project['id'])
        chosen = self.client.post(f'/api/projects/{self.project["id"]}/cover/select',
                                  json={'job_id': job['id'], 'image_id': '1', 'revision': current['revision']})
        self.assertEqual(chosen.status_code, 200, chosen.text)
        cover = chosen.json()['cover']
        self.assertEqual(cover['chat_image'], f'{job["id"]}/1')
        self.assertIn('Grok', cover['name'])
        saved = Image.open(io.BytesIO(self.client.get(cover['url']).content))
        self.assertEqual(saved.size, (1080, 1920))
        self.assertEqual(saved.getpixel((540, 960)), (34, 85, 170))

    def test_follow_up_sends_history_and_previous_image_for_edits(self):
        self.online()
        self.send()
        first, _ = self.generate([png('#2255aa')])
        self.assertEqual(self.send('Deixe o fundo mais escuro', provider='codex').status_code, 202)
        _, prompts = self.generate([png('#112244')], {'message': 'Escureci o fundo.'})
        data = json.loads(prompts[0]['prompt'].split('\nDADOS:\n')[1])
        self.assertEqual(data['conversation'], [{'user': 'Uma capa com fundo azul', 'agent': 'Criei uma capa azul.', 'provider': 'grok'}])
        self.assertEqual(data['attachments'], [{'file': 'anexo-1.png', 'origin': 'imagem anterior desta conversa'}])
        self.assertEqual(prompts[0]['attachments'][0], DATA/f'projects/{self.project["id"]}/renders/{first["id"]}/images/1.png')
        self.assertEqual(prompts[0]['config']['provider'], 'codex')

    def test_claude_draws_svg_with_attachments_and_cannot_reference_other_files(self):
        self.online()
        self.send(provider='claude', files=[png('#ff0000')])
        _, prompts = self.generate(result={'message': 'Desenhei em SVG.', 'svg': SVG})
        self.assertIn('svg', prompts[0]['schema']['required'])
        chat = self.client.get(f'/api/projects/{self.project["id"]}/cover/messages').json()
        image = Image.open(io.BytesIO(self.client.get(chat[0]['images'][0]['url']).content))
        self.assertEqual(image.size, (1080, 1920))
        self.assertEqual(image.getpixel((900, 1500)), (18, 52, 86))
        self.assertEqual(image.getpixel((100, 100)), (255, 0, 0))
        for unsafe in (SVG.replace('anexo-1.png', '/data/private/integrations.json'),
                       SVG.replace('<rect', '<script>alert(1)</script><rect'),
                       '<!DOCTYPE svg [<!ENTITY x "y">]>' + SVG):
            with self.subTest(unsafe=unsafe[:60]):
                self.send(provider='claude')
                with self.assertRaises(ValueError):
                    self.generate(result={'message': 'Desenhei.', 'svg': unsafe})

    def test_reply_without_image_fails_and_requests_are_validated(self):
        self.online()
        self.send()
        with self.assertRaisesRegex(ValueError, 'sem gerar imagem'):
            self.generate()
        self.assertEqual(self.client.get(f'/api/projects/{self.project["id"]}/cover/messages').json()[0]['state'], 'failed')
        self.assertEqual(self.send(text='   ').status_code, 422)
        self.assertEqual(self.send(provider='other').status_code, 422)
        self.assertEqual(self.send(files=[b'not an image']).status_code, 422)
        self.assertEqual(self.send(files=[png()]*5).status_code, 422)
        self.online(protocol=3)
        self.assertIn('agents.sh', self.send().json()['detail'])
        self.assertEqual(store.cover_jobs(self.project['id'])[-1]['state'], 'failed')
        # Rejected messages leave no attachments behind.
        self.assertEqual(len(list((DATA/'projects'/self.project['id']/'renders').iterdir())), 1)

    def test_cover_generation_costs_appear_as_their_own_version(self):
        self.online()
        self.send()
        job = store.claim(covers=True)
        def invoke(config, prompt, schema, request_id=None, **kwargs):
            stdout = json.dumps({'modelUsage': {'grok-4.7-build': {'inputTokens': 10, 'outputTokens': 5, 'costUSD': .02}}})
            bridge.atomic_json(bridge.BRIDGE/'requests'/request_id/'response.json',
                               {'result': {}, 'usage': costs.extract('grok', '', stdout)})
            (bridge.BRIDGE/'requests'/request_id/'outputs').mkdir()
            (bridge.BRIDGE/'requests'/request_id/'outputs'/'1.png').write_bytes(png())
            return {'message': 'Pronto.'}
        with patch.object(bridge, 'invoke', side_effect=invoke):
            store.finish(job['id'], 'succeeded', 'Imagem pronta', covers.produce(job))
        usage = self.client.get(f'/api/projects/{self.project["id"]}/usage').json()
        version = next(v for v in usage['versions'] if v['id'] == job['id'])
        self.assertEqual((version['kind'], version['calls'][0]['step']), ('cover', 'cover'))
        self.assertAlmostEqual(usage['total']['usd'], .02)


class RunnerImageTests(unittest.TestCase):
    def test_image_commands_expose_only_image_tools(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(commands.shutil, 'which', side_effect=lambda name: '/bin/'+name):
            folder = Path(temp)
            attachment = folder/'inputs'/'anexo-1.png'
            codex = agent_runner.command('codex', '', folder, {'type': 'object'}, False, images=[attachment])
            self.assertIn(f'--image={attachment}', codex)
            self.assertIn('features.shell_tool=false', codex)
            self.assertEqual(codex[-1], '-')
            grok = agent_runner.command('grok', 'm', folder, {'type': 'object'}, False, images=[])
            self.assertEqual(grok[grok.index('--tools')+1], 'image_gen,image_edit')
            self.assertIn('--disable-web-search', grok)
            claude = agent_runner.command('claude', '', folder, {'type': 'object'}, False, images=[attachment])
            self.assertEqual(claude[claude.index('--tools')+1], 'Read')
            self.assertEqual(claude[claude.index('--allowedTools')+1], f'Read(/{folder}/inputs/**)')
            self.assertEqual(agent_runner.command('claude', '', folder, {'type': 'object'}, False, images=[])[-1], '')

    def test_runner_copies_attachments_and_collects_generated_images(self):
        with tempfile.TemporaryDirectory() as home:
            session = '00000000-test-0000-0000-000000000001'
            images = Path(home)/'grok'/'sessions'/'%2Ftmp%2Fx'/session/'images'
            images.mkdir(parents=True)
            (images/'1.jpg').write_bytes(png())
            (images/'notes.txt').write_text('ignored')
            codex = Path(home)/'codex'/'generated_images'/'0199-thread-id'
            codex.mkdir(parents=True)
            (codex/'exec-1.png').write_bytes(png())
            with patch.dict(os.environ, {'GROK_HOME': str(Path(home)/'grok'), 'CODEX_HOME': str(Path(home)/'codex')}):
                self.assertEqual(agent_runner.generated('grok', json.dumps({'sessionId': session})), [images/'1.jpg'])
                self.assertEqual(agent_runner.generated('grok', json.dumps({'sessionId': '../..'})), [])
                self.assertEqual(agent_runner.generated('codex', '{"type":"thread.started","thread_id":"0199-thread-id"}\n'), [codex/'exec-1.png'])
                folder = bridge.BRIDGE/'requests'/'image-roundtrip'
                (folder/'inputs').mkdir(parents=True, exist_ok=True)
                (folder/'inputs'/'anexo-1.png').write_bytes(png())
                (folder/'lease').touch()
                request = folder/'request.json'
                request.write_text(json.dumps({'provider': 'grok', 'model': '', 'prompt': 'capa', 'schema': {'type': 'object'},
                                               'web': False, 'expires': time.time()+30, 'kind': 'image', 'attachments': ['anexo-1.png']}))
                seen = {}
                def command(provider, model, temp, schema, web, navigator=None, images=None):
                    seen.update(images=images, prompt=(temp/'prompt.txt').read_text(), copied=images[0].read_bytes() == png())
                    return [sys.executable, '-c', 'import json; print(json.dumps({"sessionId": "%s", "text": "{\\"message\\": \\"ok\\"}"}))' % session]
                with patch.object(agent_runner, 'command', side_effect=command):
                    agent_runner.run_request(request)
            response = json.loads((folder/'response.json').read_text())
            self.assertEqual(response['result'], {'message': 'ok'})
            self.assertTrue(seen['copied'])
            self.assertIn('ARQUIVOS ANEXADOS', seen['prompt'])
            self.assertEqual(bridge.outputs('image-roundtrip'), [folder/'outputs'/'1.jpg'])
            request.write_text(json.dumps({'provider': 'grok', 'model': '', 'prompt': 'capa', 'schema': {}, 'web': False,
                                           'expires': time.time()+30, 'kind': 'image', 'attachments': ['../../private/integrations.json']}))
            for name in ('response.json', 'started'):
                (folder/name).unlink()
            agent_runner.run_request(request)
            self.assertIn('Anexo inválido', json.loads((folder/'response.json').read_text())['error'])

    def test_runner_finds_images_when_a_wrapper_sets_the_cli_home_only_for_the_child(self):
        # Profile managers (e.g. `cloak exec grok --profile x`) export GROK_HOME/CODEX_HOME only to the CLI.
        session = '01a13b3c-3189-72d2-8554-96ff3a590364'
        with tempfile.TemporaryDirectory() as home:
            script = ('import json, os, pathlib, time; time.sleep(2.5); '
                      f'folder = pathlib.Path(os.environ["GROK_HOME"])/"sessions"/"%2Ftmp%2Fx"/"{session}"/"images"; '
                      'folder.mkdir(parents=True); '
                      f'folder.joinpath("1.jpg").write_bytes(bytes.fromhex("{png().hex()}")); '
                      f'print(json.dumps({{"sessionId": "{session}", "text": json.dumps({{"message": "ok"}})}}))')
            wrapper = [sys.executable, '-c', 'import os, sys; os.execvpe(sys.argv[1], sys.argv[1:], {**os.environ, "GROK_HOME": sys.argv[-1]})',
                       sys.executable, '-c', script, home]
            folder = bridge.BRIDGE/'requests'/'wrapped-home'
            folder.mkdir(parents=True, exist_ok=True)
            (folder/'lease').touch()
            request = folder/'request.json'
            request.write_text(json.dumps({'provider': 'grok', 'model': '', 'prompt': 'capa', 'schema': {'type': 'object'},
                                           'web': False, 'expires': time.time()+30, 'kind': 'image', 'attachments': []}))
            environment = {k: v for k, v in os.environ.items() if k != 'GROK_HOME'}
            with patch.dict(os.environ, environment, clear=True), patch.object(agent_runner, 'command', return_value=wrapper):
                agent_runner.run_request(request)
            self.assertEqual(json.loads((folder/'response.json').read_text())['result'], {'message': 'ok'})
            self.assertEqual([path.name for path in bridge.outputs('wrapped-home')], ['1.jpg'])


if __name__ == '__main__':
    unittest.main()
