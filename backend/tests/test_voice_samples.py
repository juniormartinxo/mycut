"""Real ASGI, local MP3 cache and ffprobe; only ElevenLabs HTTP is simulated."""
import base64
import copy
import json
import shutil
import subprocess
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import test_studio  # Selects an isolated data directory before importing the app.
from mycut import elevenlabs, integrations, store, voice_tests
from mycut.config import DATA


class VoiceSamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mp3 = subprocess.run([
            'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.5',
            '-f', 'mp3', 'pipe:1'], capture_output=True, check=True).stdout

    def setUp(self):
        test_studio.StudioTests.setUp(self)
        shutil.rmtree(DATA / 'voice-tests', ignore_errors=True)
        self.previous = integrations.read()['elevenlabs']
        integrations.save_section('elevenlabs', {
            **integrations.DEFAULTS['elevenlabs'], 'api_key': 'test-only-secret',
            'voice_id': 'saved-voice', 'voice_name': 'Voz salva'})
        self.catalog = {'voices': [
            {'voice_id': 'junior123', 'name': 'Junior', 'category': 'cloned',
             'preview_url': 'https://example.com/preview.mp3'},
            {'voice_id': 'no-preview', 'name': 'Sem amostra', 'preview_url': None},
            {'voice_id': 'invalid-preview', 'name': 'Inválida', 'preview_url': 'javascript:alert(1)'},
        ], 'has_more': False}
        self.body = {'text': 'Teste da voz.', 'settings': {
            'voice_id': 'junior123', 'voice_name': 'Nome não confiável',
            'model_id': 'eleven_multilingual_v2', 'stability': .4, 'similarity_boost': .8, 'speed': 1.1}}
        self.calls = []
        self.response = {'audio_base64': base64.b64encode(self.mp3).decode()}
        self.paid_error = False
        original_client = httpx.Client

        def transport(request):
            self.calls.append(request)
            self.assertEqual(request.headers['xi-api-key'], 'test-only-secret')
            if request.url.path == '/v2/voices':
                return httpx.Response(200, json=self.catalog)
            if request.url.path == '/v1/models':
                return httpx.Response(200, json=[{'model_id': 'eleven_multilingual_v2',
                    'name': 'Multilingual v2', 'can_do_text_to_speech': True}])
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.url.path, '/v1/text-to-speech/junior123/with-timestamps')
            if self.paid_error:
                raise httpx.ReadTimeout('test-only-secret')
            return httpx.Response(200, json=self.response)

        self.http = patch.object(elevenlabs.httpx, 'Client',
            side_effect=lambda **kw: original_client(transport=httpx.MockTransport(transport), **kw))
        self.http.start()

    def tearDown(self):
        self.http.stop()
        integrations.save_section('elevenlabs', self.previous)
        test_studio.StudioTests.tearDown(self)

    def post(self, body=None):
        return self.client.post('/api/integrations/elevenlabs/tests', json=body or self.body)

    def test_catalog_samples_and_history_never_generate_speech(self):
        result = self.client.get('/api/integrations/elevenlabs/catalog')
        self.assertEqual(result.status_code, 200, result.text)
        voices = result.json()['voices']
        self.assertEqual(voices[0]['preview_url'], 'https://example.com/preview.mp3')
        self.assertIsNone(voices[1]['preview_url'])
        self.assertIsNone(voices[2]['preview_url'])
        self.assertEqual(self.client.get('/api/integrations/elevenlabs/tests').json(), [])
        self.assertTrue(all(r.method == 'GET' for r in self.calls))
        self.assertNotIn('test-only-secret', result.text)

    def test_generate_current_selection_cache_replay_and_history(self):
        settings_before = integrations.read()
        result = self.post()
        self.assertEqual(result.status_code, 200, result.text)
        first = result.json()
        self.assertFalse(first['cached'])
        self.assertEqual(first['voice_name'], 'Junior')
        self.assertLess(first['duration'], 1)  # Short utterances must be accepted.
        posted = [r for r in self.calls if r.method == 'POST']
        self.assertEqual(len(posted), 1)
        self.assertEqual(json.loads(posted[0].content), {'text': self.body['text'],
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {'stability': .4, 'similarity_boost': .8, 'speed': 1.1}})
        self.assertEqual(posted[0].url.params['output_format'], 'mp3_44100_128')
        self.assertEqual(integrations.read(), settings_before)
        self.assertEqual(store.jobs(), [])
        for _ in range(2):
            replay = self.client.get(first['url'])
            self.assertEqual(replay.content, self.mp3)
            self.assertIn('audio/mpeg', replay.headers['content-type'])
        repeat = self.post().json()
        self.assertTrue(repeat['cached'])
        self.assertEqual(first['id'], repeat['id'])
        self.assertEqual(len([r for r in self.calls if r.method == 'POST']), 1)
        history = self.client.get('/api/integrations/elevenlabs/tests')
        self.assertEqual(history.json()[0]['id'], first['id'])
        self.assertNotIn('test-only-secret', result.text + history.text)
        self.assertEqual(self.client.get(first['url'], headers={'Range': 'bytes=0-9'}).status_code, 206)
        self.body['settings']['speed'] = .9
        changed = self.post().json()
        self.assertNotEqual(changed['id'], first['id'])
        self.assertEqual(len([r for r in self.calls if r.method == 'POST']), 2)

    def test_catalog_uses_registered_language_without_guessing_from_multilingual_support(self):
        self.catalog['voices'] = [
            {'voice_id': 'br', 'name': 'Junior', 'labels': {'language': 'PT_br', 'accent': 'pt-brazilian'}},
            {'voice_id': 'en', 'name': 'English voice', 'labels': {'language': 'en', 'accent': 'american', 'private': 'hidden-label'},
             'verified_languages': [{'language': 'pt', 'locale': 'pt-BR'}]},
            {'voice_id': 'unknown', 'name': 'Voz sem idioma', 'labels': None,
             'verified_languages': [{'language': 'pt', 'locale': 'pt-BR'}]},
            {'voice_id': 'invalid', 'name': 'Dado inválido', 'labels': {'language': ['pt'], 'accent': None}},
        ]
        response = self.client.get('/api/integrations/elevenlabs/catalog')
        self.assertEqual(response.status_code, 200, response.text)
        voices = response.json()['voices']
        self.assertEqual([v['language'] for v in voices], ['pt', 'en', None, None])
        self.assertEqual([v['accent'] for v in voices], ['pt-brazilian', 'american', None, None])
        self.assertNotIn('hidden-label', response.text)
        self.assertTrue(all(r.method == 'GET' for r in self.calls))

    def test_validation_and_unknown_selection_do_not_charge(self):
        for text in ('', ' \n ', 'x' * 301):
            body = {**self.body, 'text': text}
            self.assertEqual(self.post(body).status_code, 422)
        invalid = copy.deepcopy(self.body)
        invalid['settings']['speed'] = 8
        self.assertEqual(self.post(invalid).status_code, 422)
        invalid['settings']['speed'] = 1
        invalid['settings']['voice_id'] = 'unavailable'
        self.assertEqual(self.post(invalid).status_code, 422)
        invalid['settings']['voice_id'] = 'junior123'
        invalid['settings']['model_id'] = 'unavailable'
        self.assertEqual(self.post(invalid).status_code, 422)
        self.assertFalse(any(r.method == 'POST' for r in self.calls))

    def test_cache_is_scoped_to_connection_and_audio_path_is_validated(self):
        first = self.post().json()
        integrations.save_section('elevenlabs', {'api_key': 'another-test-key'})
        self.assertEqual(self.client.get('/api/integrations/elevenlabs/tests').json(), [])
        self.assertEqual(self.client.get(first['url']).status_code, 404)
        self.assertEqual(self.client.get('/api/integrations/elevenlabs/tests/invalid/audio').status_code, 404)
        integrations.save_section('elevenlabs', {'api_key': ''})
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(self.client.get(first['url']).status_code, 422)

    def test_invalid_provider_audio_is_not_published(self):
        for response in ({}, {'audio_base64': 'bad base64'},
                         {'audio_base64': base64.b64encode(b'not audio').decode()}):
            self.response = response
            self.assertEqual(self.post().status_code, 422)
        self.assertEqual(self.client.get('/api/integrations/elevenlabs/tests').json(), [])

    def test_generation_failure_is_not_retried_and_secrets_are_not_returned(self):
        self.paid_error = True
        result = self.post()
        self.assertEqual(result.status_code, 422)
        self.assertNotIn('test-only-secret', result.text)
        self.assertEqual(len([r for r in self.calls if r.method == 'POST']), 1)
        self.assertEqual(self.client.get('/api/integrations/elevenlabs/tests').json(), [])

    def test_parallel_requests_cannot_generate_twice(self):
        entered, finish = threading.Event(), threading.Event()
        original_api = elevenlabs.api

        def delayed(key, method, path, **kwargs):
            if method == 'POST':
                entered.set()
                if not finish.wait(5):
                    raise AssertionError('Test did not release the generation')
            return original_api(key, method, path, **kwargs)

        body = voice_tests.VoiceTestRequest(**self.body)
        with patch.object(elevenlabs, 'api', side_effect=delayed), ThreadPoolExecutor() as pool:
            first = pool.submit(voice_tests.generate, body)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(store.Conflict):
                    voice_tests.generate(body)
            finally:
                finish.set()
            self.assertFalse(first.result()['cached'])
            self.assertTrue(voice_tests.generate(body)['cached'])
        self.assertEqual(len([r for r in self.calls if r.method == 'POST']), 1)
