import hashlib
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_studio  # Sets isolated DATA before the application modules are imported.
from asgi_client import ASGIClient
from mycut.api import app
from mycut import elevenlabs, integrations, store
from mycut.config import DATA, ROOT
from test_channels import CATALOG

HUMAN = {'kind': 'human', 'name': 'Autor'}
AGENT = {'kind': 'agent', 'name': 'Diretor'}


class EditDocumentTests(unittest.TestCase):
    """The editing document of a horizontal project (ADR 0014): every change goes through an operation."""

    def setUp(self):
        # Integration settings outlive a test; the next suites expect ElevenLabs disconnected.
        self.addCleanup(integrations.save_section, 'elevenlabs', integrations.DEFAULTS['elevenlabs'])
        integrations.save_section('elevenlabs', {**integrations.DEFAULTS['elevenlabs'], 'api_key': 'test-only-secret'})
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM edit_history'); db.execute('DELETE FROM edit_projects'); db.execute('DELETE FROM resources')
            db.execute("DELETE FROM channels WHERE id != 'default'")
        shutil.rmtree(DATA / 'resources', ignore_errors=True)

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def create(self, **values):
        response = self.client.post('/api/edit-projects', json={'title': 'História', 'author': HUMAN, **values})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_a_project_is_created_in_a_channel_with_its_own_format_and_recorded_author(self):
        channel = self.client.post('/api/channels', json={'name': 'Histórias dark', 'brand': '@dark'}).json()
        project = self.create(channel_id=channel['id'])
        self.assertEqual(project['format'], {'width': 1920, 'height': 1080, 'fps': 30})
        self.assertEqual((project['revision'], project['schema_version']), (1, 1))
        self.assertEqual(project['channel']['id'], channel['id'])
        self.assertEqual({t['kind'] for t in project['tracks']}, {'visual', 'text', 'narration', 'music', 'effects'})
        vertical = self.create(format={'width': 1080, 'height': 1920, 'fps': 30})
        self.assertEqual((vertical['format']['width'], vertical['format']['height'], vertical['channel']['id']), (1080, 1920, 'default'))
        history = self.client.get(f'/api/edit-projects/{project["id"]}/history').json()
        self.assertEqual([(h['revision'], h['author'], h['label']) for h in history['entries']],
                         [(1, HUMAN, 'Criar projeto')])
        self.assertEqual(self.client.post('/api/edit-projects', json={'title': 'X', 'author': HUMAN, 'channel_id': 'nenhum'}).status_code, 422)
        self.assertEqual(self.client.post('/api/edit-projects', json={'title': 'X'}).status_code, 422)

    def edit(self, project, *operations, author=HUMAN, expected=200, **values):
        response = self.client.post(f'/api/edit-projects/{project["id"]}/operations', json={
            'revision': project['revision'], 'author': author, 'operations': list(operations), **values})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def track(self, project, kind):
        return next(t['id'] for t in project['tracks'] if t['kind'] == kind)

    def test_scenes_tracks_and_items_change_through_operations_and_an_item_crosses_scenes(self):
        project = self.create()
        first = project['scenes'][0]['id']
        project = self.edit(project, {'op': 'add_scene', 'scene': {'id': 'abertura', 'title': 'Abertura', 'duration_ms': 4000}, 'index': 0},
                            {'op': 'update_scene', 'scene_id': first, 'duration_ms': 6000},
                            {'op': 'add_track', 'track': {'id': 'musica-2', 'kind': 'music', 'name': 'Trilha'}},
                            {'op': 'add_item', 'item': {'id': 'trilha', 'track_id': 'musica-2', 'start_ms': 1000, 'duration_ms': 8000}},
                            label='Montar abertura')
        self.assertEqual(project['revision'], 2)
        self.assertEqual([(s['id'], s['start_ms'], s['duration_ms']) for s in project['scenes']],
                         [('abertura', 0, 4000), (first, 4000, 6000)])
        music = next(i for i in project['items'] if i['id'] == 'trilha')
        # From 1 s to 9 s: the music starts in the opening and ends inside the next scene.
        self.assertEqual((music['start_ms'], music['duration_ms'], music['last_author']), (1000, 8000, HUMAN))
        self.assertEqual(project['duration_ms'], 10000)
        entries = self.client.get(f'/api/edit-projects/{project["id"]}/history').json()['entries']
        self.assertEqual((entries[-1]['label'], entries[-1]['author'], entries[-1]['revision']), ('Montar abertura', HUMAN, 2))
        self.assertEqual(set(entries[-1]['targets']), {'abertura', first, 'musica-2', 'trilha'})
        project = self.edit(project, {'op': 'move_scene', 'scene_id': 'abertura', 'index': 1}, author=AGENT)
        self.assertEqual([s['id'] for s in project['scenes']], [first, 'abertura'])
        self.assertEqual(self.client.get(f'/api/edit-projects/{project["id"]}').json()['revision'], 3)

    def test_a_stale_revision_or_an_invalid_target_is_refused_without_changing_the_document(self):
        project = self.create()
        text = self.track(project, 'text')
        current = self.edit(project, {'op': 'add_item', 'item': {'id': 'titulo', 'track_id': text, 'start_ms': 0, 'duration_ms': 2000, 'text': 'Era uma vez'}})
        before = (self.client.get(f'/api/edit-projects/{project["id"]}').json(),
                  self.client.get(f'/api/edit-projects/{project["id"]}/history').json())
        stale = self.edit(project, {'op': 'update_item', 'item_id': 'titulo', 'changes': {'start_ms': 500}}, expected=409)
        self.assertIn('mudou', stale['detail'])
        # The first operation is valid; the second names an item that does not exist, so neither is applied.
        self.edit(current, {'op': 'update_item', 'item_id': 'titulo', 'changes': {'start_ms': 500}},
                  {'op': 'update_item', 'item_id': 'nenhum', 'changes': {'start_ms': 0}}, expected=422)
        self.edit(current, {'op': 'add_item', 'item': {'track_id': 'faixa-inexistente', 'start_ms': 0, 'duration_ms': 1000}}, expected=422)
        self.edit(current, {'op': 'split_item', 'item_id': 'titulo', 'at_ms': 5000}, expected=422)
        self.edit(current, {'op': 'teleport_item', 'item_id': 'titulo'}, expected=422)
        after = (self.client.get(f'/api/edit-projects/{project["id"]}').json(),
                 self.client.get(f'/api/edit-projects/{project["id"]}/history').json())
        self.assertEqual(after, before)

    def history_step(self, project, action, expected=200, author=HUMAN):
        response = self.client.post(f'/api/edit-projects/{project["id"]}/{action}', json={'revision': project['revision'], 'author': author})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def timeline(self, project):
        return [(s['id'], s['duration_ms']) for s in project['scenes']], sorted(
            (i['id'], i['start_ms'], i['duration_ms'], i['source_start_ms']) for i in project['items'])

    def test_undo_and_redo_restore_simple_and_composite_requests_and_survive_a_restart(self):
        project = self.create()
        visual = self.track(project, 'visual')
        empty = self.timeline(project)
        project = self.edit(project, {'op': 'add_item', 'item': {'id': 'foto', 'track_id': visual, 'start_ms': 0, 'duration_ms': 4000}})
        inserted = self.timeline(project)
        # A cut is a composite request: the item shortens and a second one appears; undo takes both back.
        project = self.edit(project, {'op': 'split_item', 'item_id': 'foto', 'at_ms': 1500, 'new_id': 'foto-2'},
                            {'op': 'add_scene', 'scene': {'id': 'final', 'duration_ms': 3000}}, label='Cortar e estender')
        cut = self.timeline(project)
        self.assertEqual(cut[1], [('foto', 0, 1500, 0), ('foto-2', 1500, 2500, 1500)])
        self.assertEqual(project['undo']['label'], 'Cortar e estender')
        project = self.history_step(project, 'undo')
        self.assertEqual(self.timeline(project), inserted)
        self.assertEqual(project['redo']['label'], 'Cortar e estender')
        project = self.history_step(project, 'undo')
        self.assertEqual(self.timeline(project), empty)
        self.assertIsNone(project['undo'])
        self.history_step(project, 'undo', expected=409)
        stale = project
        project = self.history_step(project, 'redo')
        self.history_step(stale, 'redo', expected=409)

        # Restarting the service reopens the same document, revisions and history.
        self.context.__exit__(None, None, None)
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        project = self.client.get(f'/api/edit-projects/{project["id"]}').json()
        self.assertEqual((self.timeline(project), project['revision']), (inserted, 6))
        project = self.history_step(project, 'redo')
        self.assertEqual(self.timeline(project), cut)
        self.assertIsNone(project['redo'])
        entries = self.client.get(f'/api/edit-projects/{project["id"]}/history').json()['entries']
        self.assertEqual([(e['kind'], e['revision']) for e in entries],
                         [('create', 1), ('apply', 2), ('apply', 3), ('undo', 4), ('undo', 5), ('redo', 6), ('redo', 7)])

        # Editing after an undo discards what could still be redone.
        project = self.history_step(project, 'undo')
        project = self.edit(project, {'op': 'update_scene', 'scene_id': empty[0][0][0], 'title': 'Nova abertura'})
        self.assertIsNone(project['redo'])
        self.assertEqual(self.timeline(project), inserted)

    def test_each_item_keeps_its_last_author_and_a_later_agent_change_keeps_the_human_choice_protected(self):
        project = self.create()
        visual = self.track(project, 'visual')
        project = self.edit(project, {'op': 'add_item', 'item': {'id': 'mapa', 'track_id': visual, 'start_ms': 0, 'duration_ms': 3000}}, author=AGENT)
        # The author moves the item; the agent then changes its style: last author is the agent, the move stays protected.
        project = self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'start_ms': 1200}})
        project = self.edit(project, {'op': 'set_style', 'item_id': 'mapa', 'values': {'opacity': .6}}, author=AGENT)
        item = project['items'][0]
        self.assertEqual((item['last_author'], item['start_ms']), (AGENT, 1200))
        refused = self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'start_ms': 0}}, author=AGENT, expected=409)
        self.assertIn('início', refused['detail'])
        self.edit(project, {'op': 'remove_item', 'item_id': 'mapa'}, author=AGENT, expected=409)
        # The agent may still change what the author did not choose.
        project = self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'duration_ms': 2500}}, author=AGENT)
        # An explicit request to replace the choice releases it; undo brings back the choice and its protection.
        project = self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'start_ms': 0}}, author=AGENT, replace_human=True)
        self.assertEqual(project['items'][0]['start_ms'], 0)
        project = self.history_step(project, 'undo')
        self.assertEqual((project['items'][0]['start_ms'], project['items'][0]['last_author']), (1200, AGENT))
        self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'start_ms': 0}}, author=AGENT, expected=409)
        # Nor can the agent undo what the author did.
        moved = self.edit(project, {'op': 'update_item', 'item_id': 'mapa', 'changes': {'start_ms': 900}})
        self.history_step(moved, 'undo', author=AGENT, expected=409)
        project = self.history_step(moved, 'undo')
        # A request limited to a scope cannot reach other contents.
        scene = project['scenes'][0]['id']
        self.edit(project, {'op': 'update_scene', 'scene_id': scene, 'title': 'Outra'}, author=AGENT, scope=['mapa'], expected=422)
        self.edit(project, {'op': 'update_scene', 'scene_id': scene, 'title': 'Outra'}, author=AGENT, scope=[scene])

    def test_geometry_lives_in_a_composition_space_that_goes_past_the_frame(self):
        project = self.create()
        self.assertEqual(project['framing'], {'x': 0, 'y': 0, 'width': 1920, 'height': 1080})
        visual = self.track(project, 'visual')
        place = lambda item_id, x, y: {'op': 'add_item', 'item': {'id': item_id, 'track_id': visual, 'start_ms': 0, 'duration_ms': 1000,
                                                                  'geometry': {'x': x, 'y': y, 'width': 400, 'height': 300}}}
        project = self.edit(project, place('dentro', 100, 100), place('borda', 1700, 900), place('fora', 2600, -900),
                            {'op': 'add_item', 'item': {'id': 'cheio', 'track_id': visual, 'start_ms': 0, 'duration_ms': 1000}})
        items = {i['id']: i for i in project['items']}
        self.assertEqual({k: v['in_frame'] for k, v in items.items()}, {'dentro': 'inside', 'borda': 'partial', 'fora': 'outside', 'cheio': 'inside'})
        # Pixels of the composition space, not a share of the screen.
        self.assertEqual(items['fora']['geometry'], {'x': 2600, 'y': -900, 'width': 400, 'height': 300})
        self.assertEqual(items['cheio']['geometry'], {'x': 0, 'y': 0, 'width': 1920, 'height': 1080})
        vertical = self.create(format={'width': 1080, 'height': 1920, 'fps': 30})
        self.assertEqual((vertical['framing']['width'], vertical['framing']['height'], vertical['aspect']), (1080, 1920, '9:16'))

    def test_an_item_without_its_own_style_reports_the_inherited_value_and_removing_a_choice_inherits_again(self):
        project = self.create()
        text = self.track(project, 'text')
        project = self.edit(project, {'op': 'add_item', 'item': {'id': 'legenda', 'track_id': text, 'start_ms': 0, 'duration_ms': 1000, 'text': 'Olá'}})
        item = project['items'][0]
        self.assertEqual(item['style'], {})
        self.assertEqual(item['resolved_style']['color'], {'value': '#ffffff', 'inherited': True})
        project = self.edit(project, {'op': 'set_style', 'item_id': 'legenda', 'values': {'color': '#ffcc00'}})
        item = project['items'][0]
        # Only the chosen property is recorded; the others keep inheriting.
        self.assertEqual(item['style'], {'color': '#ffcc00'})
        self.assertEqual(item['resolved_style']['color'], {'value': '#ffcc00', 'inherited': False})
        self.assertTrue(item['resolved_style']['font_size']['inherited'])
        project = self.edit(project, {'op': 'set_style', 'item_id': 'legenda', 'values': {'color': None}})
        self.assertEqual(project['items'][0]['style'], {})
        self.assertEqual(project['items'][0]['resolved_style']['color'], {'value': '#ffffff', 'inherited': True})
        self.edit(project, {'op': 'set_style', 'item_id': 'legenda', 'values': {'volume': .5}}, expected=422)
        self.edit(project, {'op': 'set_style', 'item_id': 'legenda', 'values': {'color': 'amarelo'}}, expected=422)

    def test_the_project_uses_the_name_brand_and_voice_of_its_channel_until_it_has_its_own(self):
        voice = {'voice_id': 'maria456', 'model_id': 'eleven_multilingual_v2'}
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            channel = self.client.post('/api/channels', json={'name': 'Histórias dark', 'brand': '@dark', 'voice': voice}).json()
        project = self.create(channel_id=channel['id'])
        self.assertEqual(project['channel']['name'], 'Histórias dark')
        self.assertEqual({k: v['inherited'] for k, v in project['inherited'].items()}, {'channel_name': True, 'brand': True, 'voice': True})
        self.assertEqual((project['inherited']['channel_name']['value'], project['inherited']['brand']['value'],
                          project['inherited']['voice']['value']['voice_name']), ('Histórias dark', '@dark', 'Maria'))
        with patch.object(elevenlabs, 'catalog', return_value=CATALOG):
            project = self.edit(project, {'op': 'update_project', 'brand': '@outra', 'voice': {'voice_id': 'junior123', 'model_id': 'eleven_multilingual_v2'}})
            self.edit(project, {'op': 'update_project', 'voice': {'voice_id': 'nenhuma', 'model_id': 'eleven_multilingual_v2'}}, expected=422)
        self.assertEqual((project['inherited']['brand'], project['inherited']['voice']['value']['voice_name']),
                         ({'value': '@outra', 'inherited': False}, 'Junior'))
        self.assertTrue(project['inherited']['channel_name']['inherited'])
        project = self.edit(project, {'op': 'update_project', 'brand': None})
        self.assertEqual(project['inherited']['brand'], {'value': '@dark', 'inherited': True})

    def upload(self, project, content, name='foto.png', expected=200):
        response = self.client.post(f'/api/edit-projects/{project["id"]}/resources', data={
            'revision': str(project['revision']), 'author_kind': 'human', 'author_name': 'Autor'}, files={'file': (name, content, 'image/png')})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def test_importing_the_same_file_in_two_projects_keeps_one_content_with_two_references(self):
        content = b'\x89PNG mesma imagem' * 1000
        first, second = self.create(title='Um'), self.create(title='Dois')
        first = self.upload(first, content, 'capa.png')
        second = self.upload(second, content, 'outra-capa.png')
        digest = hashlib.sha256(content).hexdigest()
        self.assertEqual([(r['hash'], r['name'], r['size']) for r in first['resources']], [(digest, 'capa.png', len(content))])
        self.assertEqual(second['resources'][0]['name'], 'outra-capa.png')
        library = self.client.get('/api/resources').json()
        self.assertEqual([(r['hash'], r['size']) for r in library['resources']], [(digest, len(content))])
        self.assertEqual(sorted(r['project_id'] for r in library['resources'][0]['references']), sorted([first['id'], second['id']]))
        self.assertEqual(library['total_bytes'], len(content))
        file = self.client.get(f'/api/edit-projects/{first["id"]}/resources/{digest}')
        self.assertEqual((file.status_code, file.content), (200, content))
        # The resource's import is an operation of the author, recorded like any other.
        self.assertEqual(self.client.get(f'/api/edit-projects/{first["id"]}/history').json()['entries'][-1]['label'], 'Importar recurso')
        stored = [path for path in DATA.rglob('*') if path.is_file() and path.read_bytes() == content]
        self.assertEqual(len(stored), 1)

    def test_an_imported_svg_is_served_as_a_download_and_never_runs_in_the_studio(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>fetch("/api/edit-projects")</script></svg>'
        response = self.client.post(f'/api/edit-projects/{self.create()["id"]}/resources', data={
            'revision': '1', 'author_kind': 'human', 'author_name': 'Autor'}, files={'file': ('desenho.svg', svg, 'image/svg+xml')})
        project = response.json()
        file = self.client.get(f'/api/edit-projects/{project["id"]}/resources/{project["resources"][0]["hash"]}')
        self.assertEqual(file.headers['content-type'], 'application/octet-stream')
        self.assertEqual(file.headers['x-content-type-options'], 'nosniff')
        self.assertEqual(file.headers['content-security-policy'], 'sandbox')

    def test_no_project_resource_or_history_data_lives_where_git_versions_files(self):
        project = self.upload(self.create(), b'conteudo do teste')
        self.assertTrue(all(path.is_relative_to(DATA) for path in DATA.rglob('*')))
        # The default data folder of a checkout is ignored by Git, as everything under it.
        default = ROOT / '.data'
        for path in (default / 'studio.sqlite3', default / 'resources' / project['resources'][0]['hash'][:2] / project['resources'][0]['hash']):
            ignored = subprocess.run(['git', 'check-ignore', '-q', '--no-index', str(path)], cwd=ROOT)
            self.assertEqual(ignored.returncode, 0, path)

    def storage(self, project):
        return self.client.get(f'/api/edit-projects/{project["id"]}/storage').json()

    def test_storage_shows_the_space_of_each_project_and_a_cleanup_frees_only_what_nothing_references(self):
        shared, own = b'S' * 3000, b'P' * 5000
        other = self.upload(self.create(title='Outro'), shared, 'trilha.mp3')
        project = self.upload(self.upload(self.create(), shared, 'trilha.mp3'), own, 'foto.png')
        own_hash, shared_hash = hashlib.sha256(own).hexdigest(), hashlib.sha256(shared).hexdigest()
        visual = self.track(project, 'visual')
        project = self.edit(project, {'op': 'add_item', 'item': {'id': 'foto', 'track_id': visual, 'start_ms': 0, 'duration_ms': 1000, 'resource': own_hash}})
        usage = self.storage(project)
        self.assertEqual((usage['referenced_bytes'], usage['shared_bytes']), (8000, 3000))
        self.assertEqual(usage['cleanups'], [{'kind': 'history', 'label': 'Apagar o histórico de edição', 'entries': 4, 'frees_bytes': 0}])
        self.edit(project, {'op': 'remove_resource', 'hash': own_hash}, expected=422)
        # Removing the photo from the project frees nothing yet: undo still needs it.
        project = self.edit(project, {'op': 'remove_item', 'item_id': 'foto'}, {'op': 'remove_resource', 'hash': own_hash},
                            {'op': 'remove_resource', 'hash': shared_hash})
        self.assertEqual(self.client.get(f'/api/edit-projects/{project["id"]}/resources/{own_hash}').status_code, 200)
        usage = self.storage(project)
        self.assertEqual({r['hash']: (r['in_document'], r['in_history'], r['other_projects']) for r in usage['resources']},
                         {own_hash: (False, True, 0), shared_hash: (False, True, 1)})
        self.assertEqual(usage['cleanups'][0]['frees_bytes'], 5000)
        cleanup = lambda author, revision=project['revision']: self.client.post(f'/api/edit-projects/{project["id"]}/cleanup', json={
            'kind': 'history', 'revision': revision, 'author': author})
        self.assertEqual(cleanup(AGENT).status_code, 403)
        self.assertEqual(cleanup(HUMAN, 1).status_code, 409)
        done = cleanup(HUMAN)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()['freed_bytes'], 5000)
        project = done.json()['project']
        self.assertIsNone(project['undo'])
        self.assertEqual(self.client.get(f'/api/edit-projects/{project["id"]}/resources/{own_hash}').status_code, 404)
        library = self.client.get('/api/resources').json()
        self.assertEqual([(r['hash'], [ref['project_id'] for ref in r['references']]) for r in library['resources']], [(shared_hash, [other['id']])])
        self.assertEqual(self.client.get(f'/api/edit-projects/{other["id"]}/resources/{shared_hash}').content, shared)
        self.assertEqual(self.storage(project)['referenced_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
