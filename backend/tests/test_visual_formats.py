import copy
import io
import json
import socket
import subprocess
import unittest
from unittest.mock import patch
from PIL import Image
import test_automation as fixtures
from mycut import visuals, scene_images, store, bridge, pipeline
from mycut.config import DATA
from mycut.worker import run_once


def png(color='#fa4400'):
    output = io.BytesIO()
    Image.new('RGB', (600, 400), color).save(output, format='PNG')
    return output.getvalue()


class VisualFormatTests(unittest.TestCase):
    setUp = fixtures.AutomationTests.setUp
    tearDown = fixtures.AutomationTests.tearDown
    edit = fixtures.AutomationTests.edit
    fill = fixtures.AutomationTests.fill
    configure = fixtures.AutomationTests.configure

    def test_catalog_and_previews_use_four_different_compositions(self):
        catalog = self.client.get('/api/short-formats').json()
        self.assertEqual(len(catalog['formats']), 4)
        self.assertEqual(set(catalog['fonts']), set(visuals.FONT_NAMES))
        samples = []
        for item in catalog['formats']:
            response = self.client.get(item['preview_url'])
            self.assertEqual(response.status_code, 200)
            with Image.open(io.BytesIO(response.content)) as image:
                self.assertEqual(image.size, (270, 480))
            samples.append(response.content)
        self.assertEqual(len(set(samples)), 4)
        self.assertEqual(self.client.get('/api/short-formats/unknown/preview.png').status_code, 404)

    def test_customization_persists_and_invalid_values_are_rejected(self):
        style = {'format_id': 'radar', 'channel_name': '@JuniorIA', 'font': 'mono', 'background': '#102030',
                 'text_color': '#abcdef', 'media_mode': 'mixed', 'image_source': 'both'}
        response = self.client.post('/api/projects', json={'title': 'Formato personalizado', 'visual_style': style})
        self.assertEqual(response.status_code, 201, response.text)
        project = response.json()
        self.assertEqual(project['visual_style'], style)
        self.assertEqual(project['accent'], visuals.preset('radar')['accent'])
        self.assertTrue(project['accent_locked'])
        self.assertEqual(self.client.get(f'/api/projects/{project["id"]}').json()['visual_style'], style)
        for invalid in [{'format_id': 'missing'}, {'font': '../../secret'}, {'text_color': 'red'}, {'background': '#fff'}, {'media_mode': 'people'}, {'channel_name': 'x'*41}]:
            self.assertEqual(self.client.post('/api/projects', json={'title': 'Inválido', 'visual_style': invalid}).status_code, 422)

    def test_channel_name_changes_only_the_header_and_can_be_hidden_in_every_format(self):
        scene = {'title': 'Uma ideia por vez', 'layout': 'flow', 'items': ['Entrada', 'Resultado']}
        for selected in visuals.FORMATS:
            with self.subTest(format=selected['id']):
                body = {'scene': scene, 'accent': selected['accent'], 'visual_style': {'format_id': selected['id']}}
                before = Image.open(io.BytesIO(self.client.post('/api/scene-preview', json=body).content))
                headers = [before.crop((0, 20, 360, 60)).tobytes()]
                for name in ['@JuniorIA', '']:
                    body['visual_style']['channel_name'] = name
                    after = Image.open(io.BytesIO(self.client.post('/api/scene-preview', json=body).content))
                    headers.append(after.crop((0, 20, 360, 60)).tobytes())
                    self.assertEqual(before.crop((0, 60, 360, 640)).tobytes(), after.crop((0, 60, 360, 640)).tobytes())
                    cover = visuals.cover_frame(body, fixtures.DIRECTION['cover'])
                    expected = visuals.Composition({'title': fixtures.DIRECTION['cover']['headline'], 'layout': 'flow',
                                                   'items': fixtures.DIRECTION['cover']['labels']}, body).frame()
                    self.assertEqual(cover.crop((0, 60, 1080, 180)).tobytes(), expected.crop((0, 60, 1080, 180)).tobytes())
                self.assertEqual(len(set(headers)), 3)
        response = self.edit(visual_style={'channel_name': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['visual_style']['channel_name'], '')
        self.assertEqual(self.client.get(f'/api/projects/{self.project["id"]}').json()['visual_style']['channel_name'], '')

    def test_font_background_text_and_accent_change_the_real_preview(self):
        body = {'scene': {'title': 'Teste de formato', 'layout': 'flow', 'items': ['Entrada', 'Resultado']},
                'accent': '#ab1234', 'visual_style': {'format_id': 'editorial', 'background': '#123456', 'text_color': '#fffafa', 'font': 'serif'}}
        first = self.client.post('/api/scene-preview', json=body)
        self.assertEqual(first.status_code, 200, first.text[:50] if first.status_code != 200 else '')
        with Image.open(io.BytesIO(first.content)) as image:
            self.assertEqual(image.getpixel((0, 200)), (18, 52, 86))
        for key, value in [('font', 'mono'), ('text_color', '#00ffff')]:
            modified = copy.deepcopy(body)
            modified['visual_style'][key] = value
            self.assertNotEqual(self.client.post('/api/scene-preview', json=modified).content, first.content)
        modified = copy.deepcopy(body)
        modified['accent'] = '#11ff00'
        self.assertNotEqual(self.client.post('/api/scene-preview', json=modified).content, first.content)

    def test_image_upload_preview_scope_and_animation_only_mode(self):
        response = self.client.post(f'/api/projects/{self.project["id"]}/images?revision={self.project["revision"]}',
                                    files={'file': ('diagrama.png', png(), 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()
        record = self.project['images'][0]
        self.assertNotIn('path', record)
        self.assertEqual(self.client.get(record['url']).status_code, 200)
        scene = {'title': 'Imagem e explicação', 'layout': 'statement', 'items': ['Uma imagem relevante'], 'image_id': record['id']}
        body = {'scene': scene, 'project_id': self.project['id'], 'accent': '#123456',
                'visual_style': {'format_id': 'tutorial', 'media_mode': 'mixed'}}
        image = Image.open(io.BytesIO(self.client.post('/api/scene-preview', json=body).content))
        self.assertEqual(image.getpixel((180, 330)), (250, 68, 0))
        body['visual_style']['media_mode'] = 'animations'
        animated = Image.open(io.BytesIO(self.client.post('/api/scene-preview', json=body).content))
        self.assertNotEqual(animated.getpixel((180, 330)), (250, 68, 0))
        other = self.client.post('/api/projects', json={'title': 'Outro'}).json()
        body['project_id'] = other['id']
        body['visual_style']['media_mode'] = 'mixed'
        self.assertEqual(self.client.post('/api/scene-preview', json=body).status_code, 422)
        self.assertEqual(self.client.get(f'/api/projects/{other["id"]}/images/{record["id"]}').status_code, 404)
        self.assertEqual(self.edit(scenes=[scene]).status_code, 200)
        self.assertEqual(self.edit(scenes=[{**scene, 'image_id': 'f'*32}]).status_code, 422)

    def test_animation_mode_never_fetches_and_source_collection_keeps_provenance(self):
        research = {**fixtures.RESEARCH, 'images': [{'title': 'Diagrama', 'url': 'https://cdn.example.com/test.png',
                     'source_url': fixtures.RESEARCH['sources'][0]['url']}]}
        with patch.object(scene_images, 'fetch_image', return_value=png()) as fetch:
            scene_images.collect(research, self.project)
            fetch.assert_not_called()
            images, notes = scene_images.collect(research, {**self.project, 'visual_style': {'media_mode': 'mixed', 'image_source': 'both'}})
            self.assertEqual(fetch.call_count, 1)
        self.assertFalse(notes)
        self.assertEqual(images[0]['page_url'], research['images'][0]['source_url'])
        self.assertEqual(images[0]['source_url'], research['images'][0]['url'])
        research['images'][0]['source_url'] = 'https://unverified.example/'
        with patch.object(scene_images, 'fetch_image') as fetch:
            images, notes = scene_images.collect(research, {**self.project, 'visual_style': {'media_mode': 'mixed'}})
            fetch.assert_not_called()
        self.assertFalse(images)
        self.assertTrue(notes)

    def test_remote_images_block_private_networks_and_credentials(self):
        for url in ['http://example.com/a.png', 'https://user:secret@example.com/a', 'https://example.com:8443/a', 'file:///etc/passwd']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                scene_images.public_target(url)
        for address in ['127.0.0.1', '10.0.0.2', '169.254.169.254', '::1', '::ffff:127.0.0.1']:
            with patch.object(socket, 'getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]):
                with self.subTest(address=address), self.assertRaises(ValueError):
                    scene_images.public_target('https://example.com/a.png')

    def test_switching_image_origin_filters_the_director_and_preserves_the_library(self):
        imported = scene_images.import_image(png(), self.project['id'], 'Importada')
        sourced = scene_images.import_image(png('#224466'), self.project['id'], 'Da fonte',
                                           'https://cdn.example.com/a.png', fixtures.RESEARCH['sources'][0]['url'])
        project = {**self.project, 'images': [imported, sourced]}
        for origin, expected in [('sources', [sourced]), ('library', [imported]), ('both', [imported, sourced])]:
            with self.subTest(origin=origin):
                project['visual_style'] = {'format_id': 'radar', 'media_mode': 'mixed', 'image_source': origin}
                with patch.object(scene_images, 'fetch_image') as fetch:
                    images, notes = scene_images.collect(fixtures.RESEARCH, project)
                    fetch.assert_not_called()
                self.assertEqual(images, [imported, sourced])
                self.assertFalse(notes)
                direction = copy.deepcopy(fixtures.DIRECTION)
                direction['scenes'][0]['image_id'] = expected[0]['id']
                with patch.object(pipeline, 'agent', return_value=pipeline.Direction(**direction)) as agent:
                    result = pipeline.create_direction({'snapshot': project}, fixtures.SCRIPT, fixtures.RESEARCH, [])
                payload = agent.call_args.args[3]
                self.assertEqual([item['id'] for item in payload['available_images']], [item['id'] for item in expected])
                self.assertEqual(result.scenes[0].image_id, expected[0]['id'])
                self.assertEqual(project['images'], [imported, sourced])
                self.assertTrue(all((DATA / item['path']).exists() for item in images))
        project['visual_style']['media_mode'] = 'animations'
        self.assertEqual(scene_images.eligible(project), [])

    def test_director_cannot_choose_an_image_from_an_excluded_origin(self):
        imported = scene_images.import_image(png(), self.project['id'], 'Importada')
        project = {**self.project, 'images': [imported],
                   'visual_style': {'format_id': 'radar', 'media_mode': 'mixed', 'image_source': 'sources'}}
        images, notes = scene_images.collect(fixtures.RESEARCH, project)
        self.assertEqual(images, [imported])
        self.assertTrue(notes)
        direction = copy.deepcopy(fixtures.DIRECTION)
        direction['scenes'][0]['image_id'] = imported['id']
        with patch.object(pipeline, 'agent', return_value=pipeline.Direction(**direction)) as agent, patch.object(store, 'step'):
            with self.assertRaisesRegex(ValueError, 'image_id'):
                pipeline.create_direction({'id': 'test', 'snapshot': project}, fixtures.SCRIPT, fixtures.RESEARCH, [])
            self.assertEqual(agent.call_count, 2)

    def test_redirect_is_revalidated_and_tls_connection_uses_the_verified_ip(self):
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        private = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))
        with patch.object(socket, 'getaddrinfo', side_effect=[[public], [private]]), \
             patch.object(socket, 'create_connection') as connect, \
             patch.object(scene_images.ssl, 'create_default_context') as context, \
             patch.object(scene_images.http.client, 'HTTPSConnection') as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 302
            response.getheader.return_value = 'https://internal.example/secret'
            with self.assertRaisesRegex(ValueError, 'público'):
                scene_images.fetch_image('https://example.com/image.png')
            connect.assert_called_once_with(('93.184.216.34', 443), timeout=12)
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname='example.com')
            connection.assert_called_once()

    def test_real_video_contains_the_selected_image_and_custom_cover(self):
        response = self.client.post(f'/api/projects/{self.project["id"]}/images?revision={self.project["revision"]}',
                                    files={'file': ('diagrama.png', png(), 'image/png')})
        self.project = response.json()
        self.edit(scenes=[{'title': 'Imagem da pauta', 'narration': 'Você pode acompanhar o resultado.', 'layout': 'statement',
                          'items': ['Resultado'], 'image_id': self.project['images'][0]['id']}],
                  visual_style={'format_id': 'radar', 'media_mode': 'mixed', 'background': '#223344'})
        folder = DATA / 'projects' / self.project['id'] / 'test-cover'
        folder.mkdir(parents=True)
        cover = pipeline.cover_image({**self.project, 'visual_style': {'format_id': 'editorial'}}, pipeline.Cover(**fixtures.DIRECTION['cover']), folder)
        current = store.update_project(self.project['id'], {'cover': cover}, self.project['revision'])
        job = store.enqueue(current['id'], 'preview', current['revision'])
        run_once()
        result = store.get_job(job['id'])
        self.assertEqual(result['state'], 'succeeded', result['message'])
        output = DATA / result['output']['directory']
        with Image.open(output / 'capa.png') as generated:
            self.assertEqual(generated.getpixel((0, 200)), (34, 51, 68))
        with Image.open(DATA / cover['path']) as original:
            self.assertEqual(original.getpixel((0, 200)), (247, 243, 235))
        frame = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', '1.5', '-i', str(output/'short.mp4'),
                                         '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], timeout=30)
        offset = (495*540+270)*3
        self.assertTrue(all(abs(actual-expected) <= 10 for actual,expected in zip(frame[offset:offset+3], (250,68,0))))

    def test_agent_receives_format_and_assigns_a_downloaded_image(self):
        self.configure()
        self.edit(visual_style={'format_id': 'impact', 'font': 'mono', 'background': '#eedd88',
                                'text_color': '#112233', 'media_mode': 'mixed', 'image_source': 'both'}, accent='#883311', accent_locked=True)
        research = {**fixtures.RESEARCH, 'images': [{'title': 'Diagrama', 'url': 'https://cdn.example.com/a.png',
                     'source_url': fixtures.RESEARCH['sources'][0]['url']}]}
        prompts = {}
        def invoke(config, prompt, schema, **kwargs):
            prompts[schema['title']] = json.loads(prompt.split('\nDADOS:\n')[1])
            if schema['title'] == 'Direction':
                result = copy.deepcopy(fixtures.DIRECTION)
                result['scenes'][0]['image_id'] = prompts['Direction']['available_images'][0]['id']
                return result
            return {'Research': research, 'Script': fixtures.SCRIPT, 'Review': {'approved': True, 'issues': []}}[schema['title']]
        job = store.enqueue(self.project['id'], 'preview', self.project['revision'], 'plan', fixtures.integrations.read())
        store.claim()
        with patch.object(bridge, 'invoke', side_effect=invoke), patch.object(scene_images, 'fetch_image', return_value=png()):
            pipeline.produce(store.get_job(job['id'], private=True))
        saved = store.get_project(self.project['id'])
        self.assertEqual(saved['scenes'][0]['image_id'], saved['images'][0]['id'])
        self.assertEqual(prompts['Script']['visual_style']['format_id'], 'impact')
        self.assertEqual(prompts['Direction']['visual_style']['font'], 'mono')
        self.assertEqual(saved['accent'], '#883311')
        with Image.open(DATA / saved['cover']['path']) as cover:
            self.assertEqual(cover.getpixel((0, 200)), (238, 221, 136))

    def test_each_format_has_animation_and_renders_a_real_video(self):
        scene = {'title': 'Uma ideia por vez', 'narration': 'Você escolhe. O agente executa.', 'layout': 'flow', 'items': ['Seu pedido', 'Resultado']}
        for selected in visuals.FORMATS:
            with self.subTest(format=selected['id']):
                self.edit(scenes=[scene], visual_style={'format_id': selected['id']}, accent=selected['accent'])
                composition = visuals.Composition(scene, self.project, 270)
                self.assertNotEqual(composition.frame(.2).tobytes(), composition.frame(2).tobytes())
                job = store.enqueue(self.project['id'], 'preview', self.project['revision'])
                run_once()
                result = store.get_job(job['id'])
                self.assertEqual(result['state'], 'succeeded', result['message'])
                self.assertEqual((result['output']['width'], result['output']['height']), (540, 960))
                manifest = json.loads((DATA / result['output']['directory'] / 'render-manifest.json').read_text())
                self.assertEqual(manifest['visual_style']['format_id'], selected['id'])
