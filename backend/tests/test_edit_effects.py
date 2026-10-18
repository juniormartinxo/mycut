import json
import shutil
import unittest

import test_studio  # Sets isolated DATA before the application modules are imported.
from asgi_client import ASGIClient
from mycut.api import app
from mycut import store
from mycut.config import DATA

HUMAN = {'kind': 'human', 'name': 'Autor'}
AGENT = {'kind': 'agent', 'name': 'Diretor'}


class EditEffectsTests(unittest.TestCase):
    """Effects of the editor (Q22) are operations on the editing document, with undo and the author's protection."""

    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM edit_exports'); db.execute('DELETE FROM edit_history'); db.execute('DELETE FROM edit_projects')
            db.execute('DELETE FROM resources')
        shutil.rmtree(DATA / 'resources', ignore_errors=True)
        response = self.client.post('/api/edit-projects', json={'title': 'Efeitos', 'author': HUMAN})
        self.assertEqual(response.status_code, 201, response.text)
        self.project = response.json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def track(self, kind):
        return next(t['id'] for t in self.project['tracks'] if t['kind'] == kind)

    def edit(self, *operations, author=HUMAN, expected=200, **values):
        response = self.client.post(f'/api/edit-projects/{self.project["id"]}/operations', json={
            'revision': self.project['revision'], 'author': author, 'operations': list(operations), **values})
        self.assertEqual(response.status_code, expected, response.text)
        if expected == 200:
            self.project = response.json()
        return response.json()

    def step(self, action, author=HUMAN):
        response = self.client.post(f'/api/edit-projects/{self.project["id"]}/{action}',
                                    json={'revision': self.project['revision'], 'author': author})
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()

    def item(self, item_id):
        return next(i for i in self.project['items'] if i['id'] == item_id)

    def add(self, item_id, kind, **values):
        self.edit({'op': 'add_item', 'item': {'id': item_id, 'track_id': self.track(kind), 'start_ms': 0,
                                              'duration_ms': 4000, **values}})

    def test_points_in_time_of_a_property_are_set_edited_and_undone_by_operations(self):
        self.add('titulo', 'text', text='Olá')
        self.assertEqual(self.item('titulo')['keyframes'], {})
        points = [{'at_ms': 0, 'value': 0, 'easing': 'linear'}, {'at_ms': 1000, 'value': 1, 'easing': 'ease'}]
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'opacity', 'points': points})
        self.assertEqual(self.item('titulo')['keyframes'], {'opacity': points})
        self.assertIn('keyframes.opacity', self.item('titulo')['human'])
        # A point stays editable: the same operation moves it and changes its value.
        moved = [points[0], {'at_ms': 1500, 'value': 0.8, 'easing': 'ease'}]
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'opacity', 'points': moved})
        self.assertEqual(self.item('titulo')['keyframes']['opacity'], moved)
        self.step('undo')
        self.assertEqual(self.item('titulo')['keyframes']['opacity'], points)
        # The author's points are protected from an agent unless the request explicitly replaces them.
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'opacity', 'points': None},
                  author=AGENT, expected=409)
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'opacity', 'points': None},
                  author=AGENT, replace_human=True)
        self.assertEqual(self.item('titulo')['keyframes'], {})

    def test_points_in_time_are_validated_per_property(self):
        self.add('titulo', 'text', text='Olá')
        self.add('fundo', 'visual')
        self.add('trilha', 'music')
        bad = [
            ('titulo', 'opacity', [{'at_ms': 0, 'value': 2, 'easing': 'linear'}]),
            ('titulo', 'opacity', [{'at_ms': 500, 'value': 1, 'easing': 'linear'}, {'at_ms': 500, 'value': 0, 'easing': 'linear'}]),
            ('titulo', 'zoom', [{'at_ms': 0, 'value': 1.2, 'easing': 'linear'}]),
            ('trilha', 'x', [{'at_ms': 0, 'value': 10, 'easing': 'linear'}]),
            ('fundo', 'rotation', [{'at_ms': 0, 'value': 10, 'easing': 'bounce'}]),
            ('fundo', 'blur', [{'at_ms': 0, 'value': -1, 'easing': 'linear'}]),
        ]
        for item_id, name, points in bad:
            with self.subTest(item=item_id, property=name):
                self.edit({'op': 'set_keyframes', 'item_id': item_id, 'property': name, 'points': points}, expected=422)
        self.edit({'op': 'set_keyframes', 'item_id': 'fundo', 'property': 'zoom',
                   'points': [{'at_ms': 3000, 'value': 1.3, 'easing': 'ease'}, {'at_ms': 0, 'value': 1, 'easing': 'linear'}]})
        # Points are kept in time order.
        self.assertEqual([p['at_ms'] for p in self.item('fundo')['keyframes']['zoom']], [0, 3000])

    def test_entrances_and_exits_depend_on_the_kind_of_content_and_fit_in_the_item(self):
        self.add('fundo', 'visual')
        self.add('titulo', 'text', text='Olá')
        self.add('trilha', 'music')
        self.edit({'op': 'update_item', 'item_id': 'fundo', 'changes': {'enter': {'kind': 'dissolve', 'duration_ms': 600},
                                                                         'exit': {'kind': 'fade', 'duration_ms': 400}}})
        self.assertEqual(self.item('fundo')['enter'], {'kind': 'dissolve', 'duration_ms': 600})
        self.assertIn('enter', self.item('fundo')['human'])
        self.edit({'op': 'update_item', 'item_id': 'titulo', 'changes': {'enter': {'kind': 'type', 'duration_ms': 1200},
                                                                          'exit': {'kind': 'sink', 'duration_ms': 300}}})
        self.edit({'op': 'update_item', 'item_id': 'trilha', 'changes': {'enter': {'kind': 'fade', 'duration_ms': 2000}}})
        refused = [('fundo', 'enter', 'type'), ('trilha', 'enter', 'dissolve'), ('titulo', 'exit', 'dissolve'),
                   ('fundo', 'exit', 'dissolve')]
        for item_id, side, kind in refused:
            with self.subTest(item=item_id, side=side, kind=kind):
                self.edit({'op': 'update_item', 'item_id': item_id, 'changes': {side: {'kind': kind, 'duration_ms': 300}}},
                          expected=422)
        # A transition never lasts longer than its item; when both overlap, the composition shortens them.
        self.edit({'op': 'update_item', 'item_id': 'trilha', 'changes': {'exit': {'kind': 'fade', 'duration_ms': 4500}}},
                  expected=422)
        self.step('undo')
        self.assertIsNone(self.item('trilha')['enter'])
        # An item can be inserted with its effects already chosen.
        self.add('entra', 'text', text='Entra', enter={'kind': 'pop', 'duration_ms': 500}, speed=None)
        self.assertEqual((self.item('entra')['enter'], self.item('entra')['speed']), ({'kind': 'pop', 'duration_ms': 500}, 1.0))
        self.edit({'op': 'update_item', 'item_id': 'fundo', 'changes': {'enter': None}})
        self.assertIsNone(self.item('fundo')['enter'])

    def test_speed_and_freeze_change_the_time_the_clip_occupies_and_leave_the_next_items_in_place(self):
        self.add('clipe', 'visual', source_start_ms=1000)
        self.edit({'op': 'add_item', 'item': {'id': 'seguinte', 'track_id': self.track('visual'), 'start_ms': 4000, 'duration_ms': 3000}},
                  {'op': 'add_item', 'item': {'id': 'legenda', 'track_id': self.track('text'), 'start_ms': 4000, 'duration_ms': 1000, 'text': 'Depois'}})
        # Twice as fast: the same 4 s of media now take 2 s of the timeline.
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 2}})
        self.assertEqual((self.item('clipe')['speed'], self.item('clipe')['duration_ms']), (2, 2000))
        # A held frame adds its time to the clip; the media still ends where it did.
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'freeze': {'at_ms': 1000, 'duration_ms': 1500}}})
        self.assertEqual(self.item('clipe')['duration_ms'], 3500)
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 0.75}})
        # 4 s of media at 0.75× take 5333 ms, plus the 1.5 s hold.
        self.assertEqual(self.item('clipe')['duration_ms'], 6833)
        self.assertEqual(self.item('clipe')['source_start_ms'], 1000)
        self.assertEqual([(self.item(i)['start_ms'], self.item(i)['duration_ms']) for i in ('seguinte', 'legenda')],
                         [(4000, 3000), (4000, 1000)])
        self.step('undo')
        self.assertEqual((self.item('clipe')['speed'], self.item('clipe')['duration_ms']), (2, 3500))
        # Cutting a clip at 2× keeps the media continuous: the second part starts where the first one left the media.
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'freeze': None}})
        self.assertEqual(self.item('clipe')['duration_ms'], 2000)
        self.edit({'op': 'split_item', 'item_id': 'clipe', 'at_ms': 500, 'new_id': 'resto'})
        self.assertEqual((self.item('clipe')['duration_ms'], self.item('resto')['source_start_ms'], self.item('resto')['speed']),
                         (500, 2000, 2))

    def test_speed_and_freeze_are_for_visual_items_and_a_frame_is_held_inside_the_clip(self):
        self.add('titulo', 'text', text='Olá')
        self.add('clipe', 'visual')
        self.edit({'op': 'update_item', 'item_id': 'titulo', 'changes': {'speed': 2}}, expected=422)
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 0}}, expected=422)
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 5}}, expected=422)
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'freeze': {'at_ms': 4001, 'duration_ms': 500}}}, expected=422)
        # The clip's duration was the author's choice, so an agent changing its speed needs an explicit request.
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 2}}, author=AGENT, expected=409)

    def test_a_document_from_before_the_effects_opens_with_items_without_effects(self):
        self.add('titulo', 'text', text='Olá')
        with store.connect() as db:
            document = json.loads(db.execute('SELECT document FROM edit_projects WHERE id=?', (self.project['id'],)).fetchone()[0])
            for item in document['items']:
                for name in ('keyframes', 'enter', 'exit', 'speed', 'freeze'):
                    del item[name]
            document['schema_version'] = 1
            db.execute('UPDATE edit_projects SET document=? WHERE id=?', (json.dumps(document), self.project['id']))
        self.project = self.client.get(f'/api/edit-projects/{self.project["id"]}').json()
        item = self.item('titulo')
        self.assertEqual((self.project['schema_version'], item['keyframes'], item['enter'], item['speed'], item['freeze']),
                         (2, {}, None, 1.0, None))
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'y',
                   'points': [{'at_ms': 0, 'value': 100}, {'at_ms': 500, 'value': 0}]})
        self.assertEqual(self.item('titulo')['keyframes']['y'][0]['easing'], 'linear')

    def test_cutting_an_item_keeps_its_entrance_on_the_first_part_its_exit_on_the_second_and_its_ramps(self):
        self.add('titulo', 'text', text='Olá', enter={'kind': 'fade', 'duration_ms': 300}, exit={'kind': 'sink', 'duration_ms': 300})
        self.edit({'op': 'set_keyframes', 'item_id': 'titulo', 'property': 'opacity',
                   'points': [{'at_ms': 0, 'value': 0}, {'at_ms': 1000, 'value': 1}]})
        self.edit({'op': 'split_item', 'item_id': 'titulo', 'at_ms': 500, 'new_id': 'resto'})
        first, rest = self.item('titulo'), self.item('resto')
        self.assertEqual((first['enter'], first['exit']), ({'kind': 'fade', 'duration_ms': 300}, None))
        self.assertEqual((rest['enter'], rest['exit']), (None, {'kind': 'sink', 'duration_ms': 300}))
        # The ramp goes on across the cut: each part gets the value of the moment of the cut.
        self.assertEqual([(p['at_ms'], p['value']) for p in first['keyframes']['opacity']], [(0, 0), (500, 0.5)])
        self.assertEqual([(p['at_ms'], p['value']) for p in rest['keyframes']['opacity']], [(0, 0.5), (500, 1)])

    def test_a_new_speed_keeps_the_held_frame_on_the_same_moment_of_the_media(self):
        self.add('clipe', 'visual')
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'freeze': {'at_ms': 3000, 'duration_ms': 500}}})
        self.edit({'op': 'update_item', 'item_id': 'clipe', 'changes': {'speed': 2}})
        self.assertEqual((self.item('clipe')['freeze'], self.item('clipe')['duration_ms']), ({'at_ms': 1500, 'duration_ms': 500}, 2500))

    def test_an_export_waiting_in_line_keeps_its_media_through_a_cleanup_of_the_history(self):
        content = b'imagem do teste'
        response = self.client.post(f'/api/edit-projects/{self.project["id"]}/resources', data={'revision': self.project['revision']},
                                    files={'file': ('foto.png', content, 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()
        digest = self.project['resources'][0]['hash']
        self.add('foto', 'visual', resource=digest)
        asked = self.client.post(f'/api/edit-projects/{self.project["id"]}/exports', json={'revision': self.project['revision'], 'author': HUMAN})
        self.assertEqual(asked.status_code, 201, asked.text)
        self.edit({'op': 'remove_item', 'item_id': 'foto'}, {'op': 'remove_resource', 'hash': digest})
        cleanup = self.client.post(f'/api/edit-projects/{self.project["id"]}/cleanup',
                                   json={'kind': 'history', 'revision': self.project['revision'], 'author': HUMAN})
        self.assertEqual(cleanup.json()['freed_bytes'], 0)
        self.assertEqual(self.client.get(f'/api/edit-projects/{self.project["id"]}/resources/{digest}').content, content)
        # Removing the export is the author's choice too: what only it held leaves the acervo.
        removed = self.client.request('DELETE', f'/api/edit-projects/{self.project["id"]}/exports/{asked.json()["id"]}', json={'author': HUMAN})
        self.assertEqual(removed.json(), {'exports': []})
        self.assertEqual(self.client.get(f'/api/edit-projects/{self.project["id"]}/resources/{digest}').status_code, 404)
        self.assertEqual(self.client.get('/api/resources').json()['resources'], [])


if __name__ == '__main__':
    unittest.main()
