import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import wave
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TEMP = tempfile.TemporaryDirectory(prefix='mycut-tests-')
os.environ['MYCUT_DATA_DIR'] = TEMP.name
os.environ['MYCUT_SEED'] = '0'
from asgi_client import ASGIClient
from mycut.api import app
from mycut import store
from mycut.config import DATA
from mycut.models import ProjectInput
from mycut.worker import run_once


def audio_file():
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
        wav.writeframes(b'\x00\x00' * 16000)
    return out.getvalue()


class StudioTests(unittest.TestCase):
    def setUp(self):
        store.initialize()
        self.context = ASGIClient(app)
        self.client = self.context.__enter__()
        # Isolated data only; no user's material is modified by tests.
        with store.connect() as db:
            db.execute('DELETE FROM jobs'); db.execute('DELETE FROM projects')
        self.project = self.client.post('/api/projects', json={'title': 'Teste de produção'}).json()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def edit(self, **changes):
        value = {
            key: self.project[key] for key in ProjectInput.model_fields
        }
        value.update(changes)
        result = self.client.put('/api/projects/' + self.project['id'], json=value)
        if result.status_code == 200:
            self.project = result.json()
        return result

    def fill(self):
        scenes = [dict(s, narration='Uma ideia clara vira um vídeo melhor.') for s in self.project['scenes']]
        return self.edit(scenes=scenes)

    def test_project_persists_and_optimistic_conflict_preserves_text(self):
        original = {k:self.project[k] for k in ProjectInput.model_fields}
        self.assertEqual(self.edit(title='Meu título').status_code, 200)
        stale = self.client.put('/api/projects/' + self.project['id'], json=original)
        self.assertEqual(stale.status_code,409)
        self.assertEqual(store.get_project(self.project['id'])['title'], 'Meu título')
        store.initialize()
        self.assertEqual(store.get_project(self.project['id'])['revision'],2)

    def test_rejects_empty_final_and_unfilled_scenes(self):
        url=f'/api/projects/{self.project["id"]}/renders'
        self.assertEqual(self.client.post(url,json={'mode':'preview','revision':1}).status_code,409)
        self.fill()
        self.assertEqual(self.client.post(url,json={'mode':'final','revision':2}).status_code,409)

    def test_audio_import_binds_script_and_requires_explicit_reconfirmation(self):
        self.fill()
        url=f'/api/projects/{self.project["id"]}/assets/audio?revision={self.project["revision"]}'
        response=self.client.post(url,files={'file':('../../voice.wav',audio_file(),'audio/wav')})
        self.assertEqual(response.status_code,200,response.text)
        self.project=response.json()
        self.assertTrue(self.project['audio_matches_script'])
        asset=self.client.get(self.project['audio']['url'])
        self.assertEqual(asset.status_code,200)
        record=store.get_project(self.project['id'])['audio']
        self.assertTrue((DATA/record['path']).resolve().is_relative_to(DATA))
        scenes=[dict(s,narration='O roteiro agora mudou completamente.') for s in self.project['scenes']]
        self.edit(scenes=scenes)
        self.assertFalse(self.project['audio_matches_script'])
        self.assertEqual(self.client.post(f'/api/projects/{self.project["id"]}/renders',json={'mode':'final','revision':self.project['revision']}).status_code,409)
        confirm=self.client.post(f'/api/projects/{self.project["id"]}/confirm-audio?revision={self.project["revision"]}')
        self.assertTrue(confirm.json()['audio_matches_script'])

    def test_invalid_upload_does_not_change_project(self):
        self.fill()
        response=self.client.post(f'/api/projects/{self.project["id"]}/assets/audio?revision=2',files={'file':('bad.wav',b'not an audio','audio/wav')})
        self.assertEqual(response.status_code,422)
        self.assertEqual(store.get_project(self.project['id'])['revision'],2)
        self.assertNotIn('audio',store.get_project(self.project['id']))

    def test_cover_upload_becomes_valid_vertical_image(self):
        from PIL import Image
        image=io.BytesIO(); Image.new('RGB',(80,80),'orange').save(image,'PNG')
        response=self.client.post(f'/api/projects/{self.project["id"]}/assets/cover?revision=1',files={'file':('cover.png',image.getvalue(),'image/png')})
        self.assertEqual(response.status_code,200,response.text)
        data=self.client.get(response.json()['cover']['url']).content
        self.assertEqual(Image.open(io.BytesIO(data)).size,(1080,1920))

    def test_small_vertical_cover_fills_the_frame(self):
        from PIL import Image
        # Image generators deliver 9:16 covers smaller than the frame, such as 572×1024.
        image=io.BytesIO(); Image.new('RGB',(572,1024),'#202020').save(image,'JPEG')
        response=self.client.post(f'/api/projects/{self.project["id"]}/assets/cover?revision=1',files={'file':('capa.jpg',image.getvalue(),'image/jpeg')})
        self.assertEqual(response.status_code,200,response.text)
        cover=Image.open(io.BytesIO(self.client.get(response.json()['cover']['url']).content)).convert('RGB')
        self.assertEqual(cover.size,(1080,1920))
        for point in ((2,2),(1077,960),(540,1917)):
            self.assertTrue(all(value<60 for value in cover.getpixel(point)),point)
        # A square image is not cropped into a strip: it keeps bars above and below.
        square=io.BytesIO(); Image.new('RGB',(800,800),'#202020').save(square,'PNG')
        response=self.client.post(f'/api/projects/{self.project["id"]}/assets/cover?revision={response.json()["revision"]}',files={'file':('quadrada.png',square.getvalue(),'image/png')})
        cover=Image.open(io.BytesIO(self.client.get(response.json()['cover']['url']).content)).convert('RGB')
        self.assertEqual(cover.getpixel((540,960)),(32,32,32))
        self.assertGreater(min(cover.getpixel((540,5))),200)

    def test_comparison_preserves_both_sides_and_rejects_hidden_options(self):
        scenes = self.project['scenes']
        scenes[0].update(layout='comparison', items=['Remote Control\nComputador ativo', 'Cloud Sessions\nExecução na nuvem'])
        self.assertEqual(self.edit(scenes=scenes).status_code, 200)
        scenes = self.project['scenes']
        comparison = scenes[0]
        self.assertEqual(len(comparison['items']), 2)
        comparison['items'][0] += '!'
        self.assertEqual(self.edit(scenes=scenes).status_code, 200)
        self.assertIn('Cloud Sessions', self.project['scenes'][0]['items'][1])
        self.assertIn('\n', self.project['scenes'][0]['items'][1])
        scenes[0]['items'].append('Uma terceira opção seria cortada no render')
        self.assertEqual(self.edit(scenes=scenes).status_code, 422)

    def test_queue_is_atomic_and_edits_are_locked_while_producing(self):
        self.fill()
        def enqueue(_):
            try: return store.enqueue(self.project['id'],'preview',self.project['revision'])['id']
            except store.Conflict: return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(enqueue,range(4)))
        self.assertEqual(sum(x is not None for x in ids),1)
        self.assertEqual(self.edit(title='Mudança concorrente').status_code,409)
        job_id=next(x for x in ids if x)
        store.cancel(job_id)
        self.assertEqual(self.edit(title='Mudança permitida').status_code,200)

    def test_recovery_keeps_queued_jobs_and_marks_interrupted_work(self):
        self.fill()
        job=store.enqueue(self.project['id'],'preview',self.project['revision'])
        store.recover(); self.assertEqual(store.get_job(job['id'])['state'],'queued')
        self.assertIsNotNone(store.claim())
        store.recover(); self.assertEqual(store.get_job(job['id'])['state'],'failed')

    def test_local_mutations_reject_foreign_origin(self):
        response=self.client.post('/api/projects',json={'title':'unexpected'},headers={'Origin':'https://external.example'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(len(store.all_projects()),1)

    def test_internal_files_are_not_exposed(self):
        self.assertEqual(self.client.get('/api/jobs/missing/files/worker.log').status_code,404)
        self.assertEqual(self.client.get('/api/projects/missing/assets/audio').status_code,404)
        self.assertNotIn('document',self.client.get('/api/projects').json()[0])

    def test_caption_paragraphs_and_bounds_are_validated(self):
        scenes=[dict(s,narration='Uma linha.\n\nOutra linha.') for s in self.project['scenes']]
        self.assertEqual(self.edit(scenes=scenes).status_code,200)
        self.assertEqual(self.project['scenes'][0]['narration'],'Uma linha. Outra linha.')
        self.assertEqual(self.edit(accent='url(evil)').status_code,422)
        self.assertEqual(self.edit(scenes=[]).status_code,422)

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg is needed for the production integration test')
    def test_real_preview_render_download_range_zip_and_history(self):
        self.fill()
        job=store.enqueue(self.project['id'],'preview',self.project['revision'])
        self.assertTrue(run_once())
        result=store.get_job(job['id'])
        self.assertEqual(result['state'],'succeeded',result['message'])
        self.assertFalse(result['output']['has_audio'])
        video=self.client.get(f'/api/jobs/{job["id"]}/files/short.mp4',headers={'Range':'bytes=0-99'})
        self.assertEqual(video.status_code,206)
        self.assertEqual(len(video.content),100)
        response=self.client.get(f'/api/jobs/{job["id"]}/package')
        with zipfile.ZipFile(io.BytesIO(response.content)) as package:
            self.assertIn('short.mp4',package.namelist())
            self.assertIn('legendas.srt',package.namelist())
            self.assertIn('Teste de produção',package.read('publicacao.txt').decode())
        self.assertEqual(self.edit(title='Nova revisão').status_code,200)
        self.assertNotEqual(store.get_job(job['id'])['revision'],self.project['revision'])
        self.assertEqual(self.client.get(f'/api/jobs/{job["id"]}/files/short.mp4').status_code,200)


if __name__ == '__main__':
    unittest.main()
