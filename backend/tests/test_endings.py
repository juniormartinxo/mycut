import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import test_studio  # Share the suite's isolated data directory, including worker subprocesses.

from asgi_client import ASGIClient
from mycut.api import app
from mycut import endings, store
from mycut.config import DATA
from mycut.media import digest
from mycut.models import ProjectInput
from mycut.production import make_video


class EndingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix='mycut-ending-fixtures-')
        cls.clip = Path(cls.fixture_dir.name) / 'ending.mp4'
        cls.silent = Path(cls.fixture_dir.name) / 'silent.mp4'
        for target, sound in ((cls.clip, True), (cls.silent, False)):
            command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=108x192:r=24']
            if sound:
                command += ['-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000']
            subprocess.run(command + ['-t', '0.8', '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p',
                                      '-c:a', 'aac', str(target)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        store.initialize()
        self.client = ASGIClient(app)
        self.project = self.client.post('/api/projects', json={'title': 'Encerramento em teste'}).json()

    def save(self, **changes):
        body = {key: self.project.get(key, field.default) for key, field in ProjectInput.model_fields.items()}
        body.update(changes)
        response = self.client.put(f'/api/projects/{self.project["id"]}', json=body)
        if response.status_code == 200:
            self.project = response.json()
        return response

    def upload(self, path=None):
        response = self.client.post('/api/endings', files={'file': ('tropa.mp4', (path or self.clip).read_bytes(), 'video/mp4')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def render(self, mode='preview'):
        job = store.enqueue(self.project['id'], mode, self.project['revision'])
        result = make_video(store.get_job(job['id'], private=True))
        store.finish(job['id'], 'succeeded', 'Teste concluído', result)
        return result, DATA / result['directory']

    def test_upload_reuse_range_and_per_project_choice(self):
        self.assertIsNone(self.project['ending_id'])
        clip = self.upload()
        self.assertTrue(clip['has_audio'])
        self.assertNotIn('path', clip)
        self.assertEqual(self.upload()['id'], clip['id'])
        self.assertEqual(self.client.get(clip['url'], headers={'Range': 'bytes=0-31'}).status_code, 206)
        self.assertEqual(self.client.get(clip['poster_url']).status_code, 200)
        self.assertEqual(self.save(ending_id=clip['id']).status_code, 200)
        self.assertEqual(self.client.get(f'/api/projects/{self.project["id"]}').json()['ending_id'], clip['id'])
        other = self.client.post('/api/projects', json={'title': 'Sem encerramento'}).json()
        self.assertIsNone(other['ending_id'])
        self.assertEqual(self.save(ending_id=None).status_code, 200)
        self.assertIn(clip['id'], [item['id'] for item in self.client.get('/api/endings').json()])

    def test_invalid_upload_and_unknown_selection_leave_project_unchanged(self):
        before = len(self.client.get('/api/endings').json())
        for name, content in [('bad.mp4', b'not video'), ('playlist.m3u8', b'#EXTM3U\nhttp://example.com')]:
            response = self.client.post('/api/endings', files={'file': (name, content, 'video/mp4')})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(self.client.get('/api/endings').json()), before)
        self.assertEqual(self.save(ending_id='f' * 32).status_code, 422)
        self.assertEqual(self.save(ending_id='../escape').status_code, 422)
        self.assertIsNone(self.client.get(f'/api/projects/{self.project["id"]}').json()['ending_id'])

    def test_preview_appends_real_picture_and_audio_only_when_enabled(self):
        clip = self.upload()
        self.save(scenes=[{'title': 'Teste', 'narration': 'Uma ideia clara.', 'layout': 'statement', 'items': ['Teste']}])
        plain, plain_dir = self.render()
        self.assertIsNone(plain['ending'])
        self.assertFalse(plain['has_audio'])
        self.save(ending_id=clip['id'])
        combined, folder = self.render()
        self.assertFalse(combined['has_narration'])
        self.assertTrue(combined['has_audio'])
        self.assertAlmostEqual(combined['duration'], plain['duration'] + clip['duration'], delta=.15)
        manifest = json.loads((folder / 'render-manifest.json').read_text())
        self.assertEqual(manifest['ending']['id'], clip['id'])
        self.assertEqual(manifest['video_sha256'], digest(folder / 'short.mp4'))
        self.assertEqual((plain_dir / 'legendas.srt').read_text(), (folder / 'legendas.srt').read_text())
        pixel = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(plain['duration'] + .3),
                                        '-i', str(folder / 'short.mp4'), '-vf', 'scale=1:1', '-frames:v', '1',
                                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        self.assertGreater(pixel[0], 180)
        self.assertLess(pixel[1], 40)
        import numpy as np
        signal = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(folder / 'short.mp4'),
                                         '-vn', '-ac', '1', '-ar', '8000', '-f', 'f32le', '-'])
        samples = np.frombuffer(signal, dtype=np.float32)
        self.assertLess(float(np.max(np.abs(samples[1000:6000]))), .001)
        self.assertGreater(float(np.max(np.abs(samples[int((plain['duration']+.2)*8000):]))), .02)
        self.save(ending_id=None)
        self.assertEqual(store.get_project(self.project['id'])['audio'] if 'audio' in self.project else None, None)

    def test_final_keeps_narration_with_silent_ending_and_detects_tampering(self):
        clip = self.upload(self.silent)
        self.assertFalse(clip['has_audio'])
        self.save(ending_id=clip['id'], scenes=[{'title':'Teste', 'narration':'Uma ideia clara.', 'layout':'statement', 'items':['Teste']}])
        folder = DATA / 'projects' / self.project['id']
        audio = folder / 'test.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
                        '-t', '1.2', str(audio)], check=True)
        alignment = folder / 'alignment.json'
        alignment.write_text(json.dumps({'audio_sha256':digest(audio), 'segments':[{'start':0, 'end':1.1, 'text':'Uma ideia clara.',
            'words':[{'word':word,'start':i*.35,'end':(i+1)*.35} for i,word in enumerate(['Uma','ideia','clara.'])]}]}))
        project = store.update_project(self.project['id'], {'audio': {'path':str(audio.relative_to(DATA)), 'name':'Teste',
            'sha256':digest(audio), 'duration':1.2, 'normalized':True, 'script_hash':store.script_hash(self.project),
            'alignment':str(alignment.relative_to(DATA))}}, self.project['revision'])
        self.project = self.client.get(f'/api/projects/{project["id"]}').json()
        result, rendered = self.render('final')
        self.assertEqual((result['width'],result['height']), (1080,1920))
        self.assertTrue(result['has_narration'])
        self.assertAlmostEqual(result['duration'], 1.2 + clip['duration'], delta=.15)
        record = endings.get(clip['id'])
        with self.assertRaisesRegex(ValueError, 'alterado'):
            endings.append_clip(rendered/'short.mp4', {**record, 'sha256':'bad'},1080,1920,30,True)


if __name__ == '__main__':
    unittest.main()
