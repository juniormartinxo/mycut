import copy
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

TEMP = tempfile.TemporaryDirectory(prefix='mycut-gif-tests-')
os.environ.setdefault('MYCUT_DATA_DIR', TEMP.name)
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut import store, scene_layout, block_render, scene_images
from mycut.api import app
from mycut.models import ProjectInput
from mycut.media import data_path

RED, BLUE = (220, 30, 30), (30, 60, 220)


def gif(colors=(RED, BLUE), delays=(200, 300), size=(120, 80), transparent=False):
    """A GIF whose frames are solid colors; a transparent one leaves the right half see-through."""
    frames = []
    for color in colors:
        frame = Image.new('RGBA', size, (*color, 255))
        if transparent:
            frame.paste((0, 0, 0, 0), (size[0]//2, 0, size[0], size[1]))
        frames.append(frame)
    stream = io.BytesIO()
    frames[0].save(stream, 'GIF', save_all=True, append_images=frames[1:], duration=list(delays), loop=0, disposal=2)
    return stream.getvalue()


def webp(frames=((*RED, 255), (*BLUE, 255)), size=(120, 80)):
    images = [Image.new('RGBA', size, color) for color in frames]
    stream = io.BytesIO()
    if len(images) > 1:
        images[0].save(stream, 'WEBP', save_all=True, append_images=images[1:], duration=[200, 300], loop=0, lossless=True)
    else:
        images[0].save(stream, 'WEBP', lossless=True)
    return stream.getvalue()


def center(image, box):
    x, y, w, h = map(round, box)
    return image.convert('RGB').getpixel((x+w//4, y+h//2))


def near(color, target):
    return all(abs(a-b) < 40 for a, b in zip(color, target))


class GifImageTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        with store.connect() as db:
            db.execute('DELETE FROM jobs')
            db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'GIFs'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def upload(self, content, name='animado.gif'):
        return self.client.post(f'/api/projects/{self.project["id"]}/images?revision={self.project["revision"]}',
                                files={'file': (name, content, 'image/gif')})

    def edit(self, **changes):
        body = {key: self.project[key] for key in ProjectInput.model_fields}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()

    def test_animated_gif_import_keeps_file_and_first_frame(self):
        response = self.upload(gif())
        self.assertEqual(response.status_code, 200, response.text)
        image = response.json()['images'][-1]
        self.assertTrue(image['animated'])
        self.assertNotIn('animation', image)
        self.assertNotIn('path', image)
        record = store.get_project(self.project['id'])['images'][-1]
        self.assertEqual(record['animation']['frames'], 2)
        self.assertAlmostEqual(record['animation']['duration'], .5)
        with Image.open(data_path(record['path'])) as poster:
            self.assertEqual(poster.format, 'PNG')
            self.assertTrue(near(poster.convert('RGB').getpixel((10, 10)), RED))
        served = self.client.get(image['url'])
        self.assertEqual(served.headers['content-type'], 'image/gif')
        self.assertEqual(served.content, gif())

    def test_single_frame_gif_is_a_still_image(self):
        response = self.upload(gif(colors=(RED,), delays=(100,)))
        self.assertEqual(response.status_code, 200, response.text)
        image = response.json()['images'][-1]
        self.assertFalse(image['animated'])
        self.assertEqual(self.client.get(image['url']).headers['content-type'], 'image/png')

    def test_too_many_frames_are_rejected(self):
        with patch.object(scene_images, 'ANIMATION_FRAMES', 1):
            response = self.upload(gif())
        self.assertEqual(response.status_code, 422)
        self.assertIn('animação', response.text)

    def test_frames_follow_the_gif_timing_and_loop(self):
        record = scene_images.import_image(gif(delays=(200, 300)), self.project['id'], 'animado.gif')
        reader = scene_images.AnimatedImage(record)
        moments = (None, 0, .19, .21, .49, .51, 1.25)
        # Played once, the last frame holds; in loop, the GIF starts over.
        self.assertEqual([reader.frame(t)[0] for t in moments], [0, 0, 0, 1, 1, 1, 1])
        self.assertEqual([reader.frame(t, loop=True)[0] for t in moments], [0, 0, 0, 1, 1, 0, 1])
        reader.close()
        # Delays under 20 ms play at 100 ms, as in browsers.
        record = scene_images.import_image(gif(delays=(0, 0)), self.project['id'], 'rapido.gif')
        self.assertAlmostEqual(record['animation']['duration'], .2)

    def test_image_block_and_background_play_the_gif(self):
        response = self.upload(gif(transparent=True))
        self.assertEqual(response.status_code, 200, response.text)
        self.project = response.json()
        image_id = self.project['images'][-1]['id']
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='image', asset_id=image_id, fit='contain').model_dump()
        self.edit(scenes=[scene])
        project = store.get_project(self.project['id'])
        box = scene_layout.geometry(project['scenes'][0]['blocks'])[1]['object']
        composition = block_render.BlockComposition(project['scenes'][0], project)
        self.assertTrue(near(center(composition.frame(None), box), RED))
        self.assertTrue(near(center(composition.frame(.1), box), RED))
        self.assertTrue(near(center(composition.frame(.3), box), BLUE))
        self.assertTrue(near(center(composition.frame(.6), box), BLUE))
        # The transparent half shows the scene behind it, not a filled color.
        x, y, w, h = map(round, box)
        frame = composition.frame(.3).convert('RGB')
        self.assertFalse(near(frame.getpixel((x+w*3//4, y+h//2)), RED) or near(frame.getpixel((x+w*3//4, y+h//2)), BLUE))
        composition.close()
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['blocks'][1]['object'] = None
        scene['background'] = {'kind': 'image', 'asset_id': image_id}
        self.edit(scenes=[scene])
        project = store.get_project(self.project['id'])
        composition = block_render.BlockComposition(project['scenes'][0], project)
        first, later = composition.frame(.1).convert('RGB'), composition.frame(.3).convert('RGB')
        self.assertTrue(near(first.getpixel((100, 960)), RED))
        self.assertTrue(near(later.getpixel((100, 960)), BLUE))
        composition.close()

    def test_animated_webp_plays_like_a_gif(self):
        response = self.upload(webp(), 'animado.webp')
        self.assertEqual(response.status_code, 200, response.text)
        image = response.json()['images'][-1]
        self.assertTrue(image['animated'])
        self.assertEqual(self.client.get(image['url']).headers['content-type'], 'image/webp')
        record = store.get_project(self.project['id'])['images'][-1]
        self.assertAlmostEqual(record['animation']['duration'], .5)
        reader = scene_images.AnimatedImage(record)
        frames = [reader.frame(t)[1].convert('RGB').getpixel((10, 10)) for t in (0, .3, 2)]
        reader.close()
        self.assertEqual([near(color, target) for color, target in zip(frames, (RED, BLUE, BLUE))], [True]*3)

    def test_transparent_still_images_keep_their_transparency(self):
        for name, content in (('logo.webp', webp(frames=((*RED, 0),))), ('logo.png', None)):
            if content is None:
                stream = io.BytesIO()
                Image.new('RGBA', (120, 80), (*RED, 0)).save(stream, 'PNG')
                content = stream.getvalue()
            response = self.upload(content, name)
            self.assertEqual(response.status_code, 200, response.text)
            self.project = response.json()
            record = store.get_project(self.project['id'])['images'][-1]
            self.assertFalse(self.project['images'][-1]['animated'])
            with Image.open(data_path(record['path'])) as poster:
                self.assertEqual(poster.mode, 'RGBA')
                self.assertEqual(poster.getpixel((10, 10))[3], 0)
        # An opaque WebP stays RGB, as before.
        record = scene_images.import_image(webp(frames=((*RED, 255),)), self.project['id'], 'foto.webp')
        with Image.open(data_path(record['path'])) as poster:
            self.assertEqual(poster.mode, 'RGB')

    def test_loop_is_chosen_per_object_and_background(self):
        response = self.upload(gif())
        self.project = response.json()
        image_id = self.project['images'][-1]['id']
        scene = copy.deepcopy(self.project['scenes'][0])
        scene['blocks'][1]['object'] = scene_layout.VisualObject(type='image', asset_id=image_id, playback='loop').model_dump()
        scene['background'] = {'kind': 'image', 'asset_id': image_id, 'playback': 'loop'}
        self.edit(scenes=[scene])
        saved = self.project['scenes'][0]
        self.assertEqual(saved['blocks'][1]['object']['playback'], 'loop')
        self.assertEqual(saved['background']['playback'], 'loop')
        project = store.get_project(self.project['id'])
        box = scene_layout.geometry(project['scenes'][0]['blocks'])[1]['object']
        composition = block_render.BlockComposition(project['scenes'][0], project)
        self.assertTrue(near(center(composition.frame(.6), box), RED))
        self.assertTrue(near(composition.frame(.6).convert('RGB').getpixel((100, 960)), RED))
        composition.close()
        # Played once is the default and is not stored, so older objects keep their shape.
        self.assertNotIn('playback', scene_layout.VisualObject(type='image').model_dump())
        with self.assertRaises(ValueError):
            scene_layout.VisualObject(type='title', playback='loop')
        with self.assertRaises(ValueError):
            scene_layout.Background(kind='color', color='#000000', playback='loop')


if __name__ == '__main__':
    unittest.main()
