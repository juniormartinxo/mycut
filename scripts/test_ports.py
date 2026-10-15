"""Port conflicts, Docker bind races and failure boundaries; no production data."""
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import launch
import ports


class PortTests(unittest.TestCase):
    def test_skips_consecutive_linux_listeners_and_keeps_reservation(self):
        with contextlib.ExitStack() as stack:
            for port in range(21000, 65000, 3):
                sockets = []
                try:
                    for candidate in range(port, port + 3):
                        listener = socket.socket()
                        sockets.append(listener)
                        listener.bind(('127.0.0.1', candidate))
                        listener.listen()
                    break
                except OSError:
                    for listener in sockets:
                        listener.close()
            else:
                self.fail('Não há três portas livres para o teste.')
            for listener in sockets:
                stack.enter_context(listener)
            with patch.object(ports, 'windows_available', return_value=True):
                with ports.reserve_port(port) as selected:
                    self.assertGreaterEqual(selected.getsockname()[1], port + 3)
                    with socket.socket() as competitor, self.assertRaises(OSError):
                        competitor.bind(selected.getsockname())

    def test_windows_is_probed_before_linux_reserves_the_port(self):
        with socket.socket() as temporary:
            temporary.bind(('127.0.0.1', 0))
            port = temporary.getsockname()[1]
        def probe(candidate):
            with socket.socket() as probe_socket:
                probe_socket.bind(('127.0.0.1', candidate))
            return True
        with patch.object(ports, 'windows_available', side_effect=probe):
            with ports.reserve_port(port) as selected:
                self.assertEqual(selected.getsockname()[1], port)

    def test_windows_conflicts_are_skipped(self):
        with patch.object(ports, 'windows_available', side_effect=[False, False, True]) as windows:
            with ports.reserve_port(24000) as selected:
                self.assertEqual(selected.getsockname()[1], 24002)
        self.assertEqual([call.args[0] for call in windows.call_args_list], [24000, 24001, 24002])

    def test_exhaustion_and_invalid_ports_fail_without_wrapping(self):
        with patch.object(ports, 'windows_available', return_value=False):
            with self.assertRaisesRegex(RuntimeError, '65535'):
                ports.reserve_port(65535)
        for port in (0, 1023, 65536):
            with self.assertRaises(ValueError):
                ports.reserve_port(port)

    def test_windows_probe_failure_is_not_treated_as_a_free_port(self):
        with patch.object(ports, 'windows_available', side_effect=RuntimeError('interop indisponível')):
            with self.assertRaisesRegex(RuntimeError, 'interop'):
                ports.reserve_port(24000)


class DockerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mycut-ports-test-')
        self.addCleanup(self.temp.cleanup)
        self.data = patch.object(launch, 'DATA', Path(self.temp.name))
        self.data.start()
        self.addCleanup(self.data.stop)
        self.api = {'ID': 'abcdef0123456789', 'State': 'running',
                    'Publishers': [{'TargetPort': 8321, 'PublishedPort': 24000}]}

    def reservation(self, port):
        class Reserved:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def getsockname(self):
                return ('127.0.0.1', port)
        return Reserved()

    def test_docker_bind_race_retries_and_records_only_success(self):
        conflict = subprocess.CompletedProcess([], 1, '', 'Bind: address already in use')
        success = subprocess.CompletedProcess([], 0, '', '')
        with patch.object(launch, 'containers', side_effect=[{}, {'api': self.api}]), \
             patch.object(launch, 'reserve_port', side_effect=self.reservation), \
             patch.object(launch, 'compose', side_effect=[conflict, success]) as compose, \
             patch.object(launch, 'host_matches', return_value=True):
            self.assertEqual(launch.start_docker(24000), 'http://127.0.0.1:24001')
        self.assertEqual([call.kwargs['port'] for call in compose.call_args_list], [24000, 24001])
        self.assertEqual(json.loads((launch.DATA / 'http.json').read_text())['port'], 24001)

    def test_non_port_docker_failure_does_not_scan_other_ports(self):
        failure = subprocess.CompletedProcess([], 1, '', 'image does not exist')
        with patch.object(launch, 'containers', return_value={}), \
             patch.object(launch, 'reserve_port', side_effect=self.reservation), \
             patch.object(launch, 'compose', return_value=failure) as compose:
            with self.assertRaisesRegex(RuntimeError, 'image does not exist'):
                launch.start_docker(24000)
        self.assertEqual(compose.call_count, 1)
        self.assertFalse((launch.DATA / 'http.json').exists())

    def test_running_application_keeps_its_port_and_containers(self):
        current = {'api': self.api, 'worker': {'State': 'running'}}
        with patch.object(launch, 'containers', return_value=current), \
             patch.object(launch, 'host_matches', return_value=True), \
             patch.object(launch, 'compose') as compose, \
             patch.object(launch, 'wait_for_idle') as wait:
            self.assertEqual(launch.start_docker(8321), 'http://127.0.0.1:24000')
        compose.assert_not_called()
        wait.assert_not_called()

    def test_unrelated_app_on_old_port_is_not_reused(self):
        current = {'api': self.api, 'worker': {'State': 'running'}}
        with patch.object(launch, 'containers', side_effect=[current, {'api': self.api}]), \
             patch.object(launch, 'host_matches', side_effect=[False, True]), \
             patch.object(launch, 'wait_for_idle') as wait, \
             patch.object(launch, 'reserve_port', side_effect=self.reservation) as reserve, \
             patch.object(launch, 'compose', return_value=subprocess.CompletedProcess([], 0, '', '')):
            launch.start_docker(24001)
        wait.assert_called_once()
        reserve.assert_called_once_with(24001)


class HealthTests(unittest.TestCase):
    def test_another_app_can_return_any_json_without_stopping_the_port_search(self):
        for body in ('[]', '42', 'null', '{"status":"ok","instance":"another-app"}'):
            response = contextlib.nullcontext(io.BytesIO(body.encode()))
            with patch.object(ports.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                self.assertFalse(ports.host_matches(8321, 'expected-instance'))


if __name__ == '__main__':
    unittest.main()
