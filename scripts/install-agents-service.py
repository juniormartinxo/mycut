#!/usr/bin/env python3
"""Install the existing host runner as a systemd user service; no credentials copied."""
import argparse
import fcntl
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SERVICE = 'mycut-agents.service'
# Only locations and profile selection. Never serialize the complete shell environment.
PROFILE_VARIABLES = ('CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'GROK_HOME', 'XDG_CONFIG_HOME',
                     'WSL_DISTRO_NAME')


def quote(value):
    value = str(value)
    if any(ord(char) < 32 for char in value):
        raise ValueError('Caminhos e variáveis não podem conter caracteres de controle.')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def unit_quote(value, command=False):
    value = str(value).replace('%', '%%')
    return quote(value.replace('$', '$$') if command else value)


def environment(environ, root):
    # Resolve directory symlinks, including fnm_multishells, without pinning CLI
    # executables themselves: ~/.local/bin can still be updated normally.
    paths = []
    for entry in environ.get('PATH', os.defpath).split(os.pathsep):
        if not entry or not Path(entry).is_absolute():
            continue
        path = str(Path(entry).resolve())
        if Path(path).is_dir() and path not in paths:
            paths.append(path)
    search = os.pathsep.join(paths)
    python = shutil.which(environ.get('MYCUT_PYTHON', 'python3'), path=search)
    if not python:
        raise ValueError('Python não encontrado. Informe MYCUT_PYTHON com um executável válido.')
    values = {
        'PATH': search,
        'MYCUT_PYTHON': python,
        'MYCUT_DATA_DIR': str(Path(environ.get('MYCUT_DATA_DIR', root / '.data')).expanduser().resolve()),
        'PYTHONUNBUFFERED': '1',
        **{key: environ[key] for key in PROFILE_VARIABLES if environ.get(key)},
    }
    return values, ''.join(f'{key}={quote(value)}\n' for key, value in values.items())


def unit(root, env_file):
    return f'''# Managed by MyCut: scripts/install-agents-service.py
[Unit]
Description=MyCut - executor dos agentes no WSL
StartLimitIntervalSec=0

[Service]
Type=exec
WorkingDirectory={str(root).replace('%', '%%')}
EnvironmentFile={str(env_file).replace('%', '%%')}
ExecStart=/usr/bin/bash {unit_quote(root / 'scripts/agents.sh', command=True)}
Restart=always
RestartSec=5
TimeoutStopSec=30
KillMode=control-group
UMask=0077
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
'''


def runner_is_active(data):
    lock = data / 'agent-bridge/runner.lock'
    if not lock.exists():
        return False
    with lock.open('r') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        os.chmod(temporary, 0o600)
        handle.write(text)
    temporary.replace(path)


def install(root, config, environ, output=None):
    env_file = config / 'mycut/agents.env'
    unit_file = config / 'systemd/user' / SERVICE
    values, env_text = environment(environ, root)
    unit_text = unit(root, env_file)
    if output:
        write(output / 'agents.env', env_text)
        write(output / SERVICE, unit_text)
        print(f'Arquivos preparados em {output}; nenhum serviço alterado.')
        return

    if os.getuid() == 0:
        raise ValueError('Execute como o usuário dos CLIs, sem sudo.')
    subprocess.run(['systemctl', '--user', 'show-environment'], check=True, stdout=subprocess.DEVNULL)
    active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', SERVICE]).returncode == 0
    # Installation never interrupts an existing runner, including a manual one.
    if active or runner_is_active(Path(values['MYCUT_DATA_DIR'])):
        raise ValueError('Já existe um executor ativo. Aguarde as produções e testes terminarem e pare-o antes de reinstalar.')
    if unit_file.exists() and 'Managed by MyCut:' not in unit_file.read_text():
        raise ValueError(f'O serviço {unit_file} já existe e não foi criado por este instalador.')
    write(env_file, env_text)
    write(unit_file, unit_text)
    subprocess.run(['systemd-analyze', '--user', 'verify', str(unit_file)], check=True)
    username = pwd.getpwuid(os.getuid()).pw_name
    linger = subprocess.check_output(['loginctl', 'show-user', username, '-p', 'Linger', '--value'], text=True).strip()
    if linger != 'yes':
        subprocess.run(['loginctl', 'enable-linger', username], check=True)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', SERVICE], check=True)
    subprocess.run(['systemctl', '--user', 'is-active', '--quiet', SERVICE], check=True)
    print(f'{SERVICE} instalado e iniciado. Confira: systemctl --user status {SERVICE}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, help='Só prepara os arquivos, sem instalar ou iniciar serviços.')
    args = parser.parse_args()
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')).expanduser().resolve()
    try:
        install(ROOT, config, os.environ, args.output_dir)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Não foi possível configurar o serviço: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
