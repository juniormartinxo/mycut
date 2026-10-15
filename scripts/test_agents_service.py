"""Isolated checks for service installation; no real CLIs, jobs or systemd changes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('agents_service', Path(__file__).with_name('install-agents-service.py'))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class AgentsServiceTests(unittest.TestCase):
    def test_terminal_symlinks_are_resolved_and_secrets_are_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stable = root / 'node/bin'
            stable.mkdir(parents=True)
            ephemeral = root / 'terminal/bin'
            ephemeral.parent.mkdir()
            ephemeral.symlink_to(stable, target_is_directory=True)
            values, text = service.environment({
                'PATH': f'{ephemeral}:/usr/bin:{stable}:.:',
                'MYCUT_PYTHON': sys.executable,
                'CODEX_HOME': '/tmp/profile with spaces/$value',
                'OPENAI_API_KEY': 'do-not-copy',
                'ANTHROPIC_API_KEY': 'do-not-copy',
                'WSL_INTEROP': '/run/WSL/old-session_interop',
                'UNRELATED_VARIABLE': 'do-not-copy',
            }, root)
            self.assertEqual(values['PATH'], f'{stable}:/usr/bin')
            self.assertEqual(values['MYCUT_DATA_DIR'], str(root / '.data'))
            self.assertEqual(values['CODEX_HOME'], '/tmp/profile with spaces/$value')
            self.assertNotIn('do-not-copy', text)
            self.assertNotIn('old-session', text)

    def test_preview_does_not_install_and_handles_special_paths(self):
        with tempfile.TemporaryDirectory(prefix='mycut service ') as directory:
            root = Path(directory) / 'repo $NAME %h'
            root.mkdir()
            config = Path(directory) / 'user config'
            output = Path(directory) / 'preview'
            with patch.object(service.subprocess, 'run', side_effect=AssertionError('service mutation')):
                service.install(root, config, {'PATH': '/usr/bin', 'MYCUT_PYTHON': sys.executable}, output)
            self.assertFalse(config.exists())
            unit = (output / service.SERVICE).read_text()
            self.assertIn('repo $$NAME %%h/scripts/agents.sh"', unit)
            self.assertIn('Restart=always', unit)
            self.assertEqual((output / 'agents.env').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                service.quote('invalid\npath')

    def test_live_manual_runner_is_not_interrupted_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / '.data/agent-bridge/runner.lock'
            lock.parent.mkdir(parents=True)
            code = ('import fcntl,sys,time; f=open(sys.argv[1],"w"); '
                    'fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); time.sleep(30)')
            child = subprocess.Popen([sys.executable, '-c', code, str(lock)], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                self.assertTrue(service.runner_is_active(root / '.data'))
                calls = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 3)]
                with patch.object(service.os, 'getuid', return_value=1000), patch.object(service.subprocess, 'run', side_effect=calls):
                    with self.assertRaisesRegex(ValueError, 'executor ativo'):
                        service.install(root, root / 'config', {'PATH':'/usr/bin', 'MYCUT_PYTHON':sys.executable})
                self.assertIsNone(child.poll())
                self.assertFalse((root / 'config').exists())
            finally:
                child.terminate()
                child.wait()
                child.stdout.close()
            self.assertFalse(service.runner_is_active(root / '.data'))

    def test_launcher_preserves_profile_data_and_arguments_without_a_terminal(self):
        with tempfile.TemporaryDirectory(prefix='mycut launcher ') as directory:
            python = Path(directory) / 'fake python'
            python.write_text('#!/bin/bash\nprintf "%s\\n" "$@" "$CODEX_HOME" "$MYCUT_DATA_DIR" "$PYTHONPATH"\n')
            python.chmod(0o700)
            env = {'PATH':'/usr/bin:/bin', 'MYCUT_PYTHON':str(python),
                   'CODEX_HOME':'/tmp/profile with spaces', 'MYCUT_DATA_DIR':directory}
            result = subprocess.check_output(['/usr/bin/bash', str(service.ROOT / 'scripts/agents.sh')], env=env, text=True)
            self.assertEqual(result.splitlines(), ['-u', '-m', 'mycut.agent_runner',
                                                 env['CODEX_HOME'], directory, str(service.ROOT / 'backend')])


if __name__ == '__main__':
    unittest.main()
