import copy
import io
import os
import tempfile
import unittest
from PIL import Image

TEMP = tempfile.TemporaryDirectory(prefix='mycut-library-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut import store, scene_layout
from mycut.api import app
from mycut.models import ProjectInput
from mycut.media import data_path


def png(color='#c04020'):
    stream = io.BytesIO()
    Image.new('RGB', (60, 40), color).save(stream, 'PNG')
    return stream.getvalue()


def gif():
    frames = [Image.new('RGB', (60, 40), color) for color in ('#c04020', '#2040c0')]
    stream = io.BytesIO()
    frames[0].save(stream, 'GIF', save_all=True, append_images=frames[1:], duration=100, loop=0)
    return stream.getvalue()


class ImageLibraryTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs')
            db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'Biblioteca'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def upload(self, content, name):
        response = self.client.post(f'/api/projects/{self.project["id"]}/images?revision={self.project["revision"]}',
                                    files={'file': (name, content, 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()
        return self.project['images'][-1]['id']

    def delete(self, image_id, revision=None):
        return self.client.request('DELETE', f'/api/projects/{self.project["id"]}/images/{image_id}',
                                   params={'revision': revision or self.project['revision']})

    def edit(self, **changes):
        body = {key: self.project[key] for key in ProjectInput.model_fields}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()

    def test_unused_image_is_removed_with_its_files(self):
        keep, drop = self.upload(png(), 'fica.png'), self.upload(gif(), 'sai.gif')
        record = next(r for r in store.get_project(self.project['id'])['images'] if r['id'] == drop)
        paths = [data_path(record['path']), data_path(record['animation']['path'])]
        self.assertTrue(all(path.is_file() for path in paths))
        response = self.delete(drop)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([image['id'] for image in response.json()['images']], [keep])
        self.assertFalse(any(path.exists() for path in paths))
        self.project = response.json()
        self.assertEqual(self.client.get(f'/api/projects/{self.project["id"]}/images/{drop}').status_code, 404)
        self.assertEqual(self.delete(drop).status_code, 404)

    def test_image_in_use_or_stale_revision_is_kept(self):
        image_id = self.upload(png(), 'usada.png')
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['shots'] = [scene_layout.Shot(anchor=None, background={'kind': 'image', 'asset_id': image_id},
                                            blocks=scene_layout.empty_blocks()).model_dump()]
        self.edit(scenes=[scene])
        response = self.delete(image_id)
        self.assertEqual(response.status_code, 409)
        self.assertIn('em uso na cena 1', response.json()['detail'])
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['shots'] = []
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='image', asset_id=image_id).model_dump()
        self.edit(scenes=[scene])
        self.assertEqual(self.delete(image_id).status_code, 409)
        self.assertEqual(self.delete(image_id, revision=self.project['revision']-1).status_code, 409)
        record = store.get_project(self.project['id'])['images'][0]
        self.assertTrue(data_path(record['path']).is_file())
        scene['blocks'][1]['object'] = None
        self.edit(scenes=[scene])
        self.assertEqual(self.delete(image_id).status_code, 200)


if __name__ == '__main__':
    unittest.main()
