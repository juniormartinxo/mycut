import os
import unittest
from unittest.mock import patch

import test_studio  # Reuse the suite's isolated DATA, including renderer subprocesses.
from asgi_client import ASGIClient
from mycut.api import app


class HttpPortTests(unittest.TestCase):
    def test_selected_port_accepts_mutations_and_other_origins_remain_blocked(self):
        with patch.dict(os.environ, {'MYCUT_PORT': '18325'}), ASGIClient(app) as client:
            for origin in ('http://localhost:18325', 'http://127.0.0.1:18325',
                           'http://localhost:5173'):
                response = client.post('/api/projects', json={'title': 'Porta automática'}, headers={'Origin': origin})
                self.assertEqual(response.status_code, 201, origin)
                self.assertEqual(client.get('/api/projects/' + response.json()['id']).json()['title'], 'Porta automática')
            for origin in ('http://localhost:8321', 'http://localhost:18326',
                           'https://localhost:18325', 'null', 'https://evil.example',
                           'http://localhost:18325.evil.example'):
                response = client.post('/api/projects', json={'title': 'Bloqueado'}, headers={'Origin': origin})
                self.assertEqual(response.status_code, 403, origin)

    def test_health_identifies_the_actual_instance(self):
        with patch.dict(os.environ, {'MYCUT_INSTANCE': 'isolated-port-test'}), ASGIClient(app) as client:
            result = client.get('/api/health')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['instance'], 'isolated-port-test')


if __name__ == '__main__':
    unittest.main()
