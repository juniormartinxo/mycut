import io
import json
import unittest
from unittest.mock import patch

import test_studio  # Sets isolated DATA before the application modules are imported.
from asgi_client import ASGIClient
from mycut.api import app
from mycut import elevenlabs, integrations, pipeline, store, visuals
from mycut.models import ProjectInput
from test_free_short import fake_voice
from PIL import Image


CATALOG = {'voices': [{'id': 'junior123', 'name': 'Junior', 'category': 'cloned'},
                      {'id': 'maria456', 'name': 'Maria', 'category': 'premade'}],
           'models': [{'id': 'eleven_multilingual_v2', 'name': 'Multilingual v2'}]}


def pixels(png):
    return Image.open(io.BytesIO(png)).convert('RGB').tobytes()


class ChannelTests(unittest.TestCase):
    def setUp(self):
        # Integration settings outlive a test; the next suites expect ElevenLabs disconnected.
        self.addCleanup(integrations.save_section, 'elevenlabs', integrations.DEFAULTS['elevenlabs'])
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs'); db.execute('DELETE FROM projects')
            db.execute("DELETE FROM channels WHERE id != 'default'")

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_default_channel_exists_and_projects_without_choice_fall_into_it(self):
        channels = self.client.get('/api/channels').json()
        self.assertEqual([c['id'] for c in channels], ['default'])
        self.assertEqual(channels[0]['brand'], 'MYCUT')
        project = self.client.post('/api/projects', json={'title': 'Sem canal'}).json()
        self.assertEqual(project['channel']['id'], 'default')
        self.assertEqual(self.client.get('/api/projects/' + project['id']).json()['channel']['id'], 'default')

    def test_existing_shorts_join_the_default_channel_and_render_exactly_as_before(self):
        scene = {'title': 'Da ideia à ação', 'narration': 'Uma ideia.', 'layout': 'flow', 'items': ['Pedido', 'Execução']}
        legacy = {'title': 'Short antigo', 'description': '', 'tags': '', 'sources': '', 'accent': '#b8512f', 'revision': 4,
                  'visual_style': {'format_id': 'radar', 'channel_name': '@antigo'}, 'scenes': [scene]}
        untouched = {**legacy, 'title': 'Sem estilo', 'visual_style': None}
        before = {key: visuals.preview_png(scene, document, 360) for key, document in (('a' * 32, legacy), ('b' * 32, untouched))}
        with store.connect() as db:
            for project_id, document in (('a' * 32, legacy), ('b' * 32, untouched)):
                db.execute('INSERT INTO projects VALUES(?,?,?,?)', (project_id, json.dumps(document), 1, 1))
        store.initialize()
        for project_id in before:
            project = self.client.get('/api/projects/' + project_id).json()
            self.assertEqual((project['channel']['id'], project['revision'], project['updated_at']), ('default', 4, 1))
            preview = self.client.post('/api/scene-preview', json={'scene': scene, 'accent': project['accent'],
                                                                    'visual_style': project['visual_style'], 'project_id': project_id})
            self.assertEqual(pixels(preview.content), pixels(before[project_id]))
        self.assertEqual(store.get_project('a' * 32)['visual_style']['channel_name'], '@antigo')
        self.assertEqual(visuals.resolve(store.get_project('b' * 32))['channel_name'], 'MYCUT')

    def voiced(self, channel_id=None, own_voice=None, project=None):
        """A project in the channel with its narration filled in, voiced by the pipeline over a fake ElevenLabs."""
        project = project or self.client.post('/api/projects', json={'title': 'Com voz', 'channel_id': channel_id}).json()
        value = {key: project[key] for key in ProjectInput.model_fields}
        narration = 'Outra ideia clara.' if project.get('audio') else 'Uma ideia clara vira um vídeo melhor.'
        value.update(scenes=[dict(s, narration=narration) for s in project['scenes']])
        if own_voice:
            value['voice'] = own_voice
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            saved = self.client.put('/api/projects/' + project['id'], json=value)
        self.assertEqual(saved.status_code, 200, saved.text)
        response = self.client.post(f'/api/projects/{project["id"]}/run', json={'kind': 'voice', 'revision': saved.json()['revision']})
        self.assertEqual(response.status_code, 202, response.text)
        paths = []
        fake = fake_voice([])
        with patch.object(elevenlabs, 'api', side_effect=lambda key, method, path, **kw: paths.append(path) or fake(key, method, path, **kw)):
            pipeline.produce(store.get_job(store.claim()['id'], private=True))
        store.finish(response.json()['id'], 'succeeded', 'Voz pronta')
        return self.client.get('/api/projects/' + project['id']).json(), paths

    def test_the_voice_comes_from_the_project_then_its_channel_then_conexoes(self):
        integrations.save_section('elevenlabs', {**integrations.DEFAULTS['elevenlabs'], 'api_key': 'test-only-secret',
                                                 'voice_id': 'junior123', 'voice_name': 'Junior'})
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            created = self.client.post('/api/channels', json={'name': 'Histórias', 'voice': {
                'voice_id': 'maria456', 'model_id': 'eleven_multilingual_v2', 'speed': 1.1}})
            refused = self.client.post('/api/channels', json={'name': 'X', 'voice': {'voice_id': 'nenhuma', 'model_id': 'eleven_multilingual_v2'}})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(refused.status_code, 422)
        channel = created.json()
        self.assertEqual((channel['voice']['voice_name'], channel['voice']['speed']), ('Maria', 1.1))
        _, paths = self.voiced(channel['id'])
        self.assertTrue(all('/maria456/' in path for path in paths), paths)
        _, paths = self.voiced(channel['id'], own_voice={'voice_id': 'junior123', 'model_id': 'eleven_multilingual_v2'})
        self.assertTrue(all('/junior123/' in path for path in paths), paths)
        _, paths = self.voiced()
        self.assertTrue(all('/junior123/' in path for path in paths), paths)

    def test_changing_the_channel_voice_keeps_generated_voices_and_starts_nothing(self):
        integrations.save_section('elevenlabs', {**integrations.DEFAULTS['elevenlabs'], 'api_key': 'test-only-secret',
                                                 'voice_id': 'junior123', 'voice_name': 'Junior'})
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            channel = self.client.post('/api/channels', json={'name': 'Histórias', 'voice': {
                'voice_id': 'maria456', 'model_id': 'eleven_multilingual_v2'}}).json()
        project, _ = self.voiced(channel['id'])
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            changed = self.client.put('/api/channels/' + channel['id'], json={'name': 'Histórias', 'voice': {
                'voice_id': 'junior123', 'model_id': 'eleven_multilingual_v2'}})
        self.assertEqual(changed.status_code, 200, changed.text)
        after = self.client.get('/api/projects/' + project['id']).json()
        self.assertEqual((after['audio'], after['revision'], after['audio_matches_script']), (project['audio'], project['revision'], True))
        self.assertEqual(after['audio']['voice_id'], 'maria456')
        self.assertEqual(len(after['jobs']), 1)
        self.assertIsNone(store.claim())
        # A new narration of the same production keeps the voice it was created with; a new production takes the new one.
        _, paths = self.voiced(project=after)
        self.assertTrue(all('/maria456/' in path for path in paths), paths)
        _, paths = self.voiced(channel['id'])
        self.assertTrue(all('/junior123/' in path for path in paths), paths)

    def test_channels_are_created_edited_and_listed(self):
        created = self.client.post('/api/channels', json={'name': 'Histórias dark', 'brand': '@historiasdark'})
        self.assertEqual(created.status_code, 201, created.text)
        channel = created.json()
        self.assertEqual((channel['name'], channel['brand'], channel['voice']), ('Histórias dark', '@historiasdark', None))
        self.assertEqual((channel['templates'], channel['guidelines']), ({}, []))
        edited = self.client.put('/api/channels/' + channel['id'], json={'name': 'Contos dark', 'brand': 'CONTOS'})
        self.assertEqual(edited.status_code, 200, edited.text)
        listed = {c['id']: c for c in self.client.get('/api/channels').json()}
        self.assertEqual((listed[channel['id']]['name'], listed[channel['id']]['brand']), ('Contos dark', 'CONTOS'))
        self.assertEqual(self.client.put('/api/channels/' + 'f' * 32, json={'name': 'X'}).status_code, 404)
        self.assertEqual(self.client.post('/api/channels', json={'name': ' '}).status_code, 422)

    def test_new_project_uses_its_channel_brand_unless_it_chooses_its_own(self):
        channel = self.client.post('/api/channels', json={'name': 'Histórias', 'brand': 'CONTOS'}).json()
        plain = self.client.post('/api/projects', json={'title': 'Sem estilo', 'channel_id': channel['id']}).json()
        styled = self.client.post('/api/projects', json={'title': 'Com formato', 'channel_id': channel['id'],
                                                         'visual_style': {'format_id': 'radar'}}).json()
        own = self.client.post('/api/projects', json={'title': 'Própria', 'channel_id': channel['id'],
                                                      'visual_style': {'format_id': 'radar', 'channel_name': '@meu'}}).json()
        self.assertEqual(plain['channel'], {'id': channel['id'], 'name': 'Histórias', 'brand': 'CONTOS', 'voice': None})
        self.assertEqual(styled['visual_style']['channel_name'], 'CONTOS')
        self.assertEqual(own['visual_style']['channel_name'], '@meu')
        self.assertEqual(visuals.resolve(store.get_project(plain['id']))['channel_name'], 'CONTOS')
        scene = plain['scenes'][0]
        preview = self.client.post('/api/scene-preview', json={'scene': scene, 'accent': plain['accent'], 'project_id': plain['id']})
        expected = visuals.preview_png(scene, store.get_project(plain['id']), 360)
        self.assertEqual(pixels(preview.content), pixels(expected))
        # Editing the channel afterwards leaves the brand its projects already inherited.
        self.client.put('/api/channels/' + channel['id'], json={'name': 'Histórias', 'brand': 'OUTRA'})
        self.assertEqual(visuals.resolve(store.get_project(plain['id']))['channel_name'], 'CONTOS')
        self.assertEqual(self.client.get('/api/projects/' + styled['id']).json()['visual_style']['channel_name'], 'CONTOS')
        missing = self.client.post('/api/projects', json={'title': 'Canal errado', 'channel_id': 'f' * 32})
        self.assertEqual(missing.status_code, 422)


if __name__ == '__main__':
    unittest.main()
