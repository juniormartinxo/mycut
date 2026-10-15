#!/usr/bin/env python3
"""Start MyCut on the first available Windows/Linux loopback port."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from ports import host_matches, reserve_port, windows_available

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('MYCUT_DATA_DIR', ROOT / '.data')).expanduser().resolve()
COMPOSE = ['docker', 'compose', '--project-directory', str(ROOT), '-f', str(ROOT / 'compose.yaml')]
PORT_ERRORS = ('port is already allocated', 'address already in use', 'ports are not available',
               'bind: permission denied', 'forbidden by its access permissions')


def compose(*args, port=None):
    environment = {**os.environ, 'MYCUT_DATA_DIR': str(DATA)}
    if port is not None:
        environment['MYCUT_PORT'] = str(port)
    return subprocess.run([*COMPOSE, *args], env=environment, capture_output=True, text=True)


def require_success(result):
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f'Comando falhou: {result.args}').strip())


def containers():
    result = compose('ps', '--all', '--format', 'json')
    require_success(result)
    text = result.stdout.strip()
    rows = json.loads(text) if text.startswith('[') else [json.loads(line) for line in text.splitlines()]
    return {row['Service']: row for row in rows}


def published_port(container):
    return next((item['PublishedPort'] for item in container.get('Publishers', []) or []
                 if item['TargetPort'] == 8321 and item['PublishedPort']), None)


def wait_for_idle():
    database = DATA / 'studio.sqlite3'
    announced = False
    while database.exists():
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            busy = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued', 'running')").fetchone()[0]
        if not busy:
            return
        if not announced:
            print('Aguardando a fila terminar antes de atualizar os containers.', flush=True)
            announced = True
        time.sleep(2)


def announce(port):
    state = {'port': port, 'url': f'http://127.0.0.1:{port}'}
    target = DATA / 'http.json'
    content = json.dumps(state) + '\n'
    if not target.exists() or target.read_text() != content:
        temporary = target.with_suffix('.tmp')
        temporary.write_text(content)
        temporary.replace(target)
        print(f'MyCut: {state["url"]}', flush=True)
    return state['url']


def start_docker(start, build=False):
    current = containers()
    api = current.get('api', {})
    port = published_port(api)
    reusable = bool(port and api.get('State') == 'running' and host_matches(port, api['ID'][:12]))
    if reusable and not build and current.get('worker', {}).get('State') == 'running':
        return announce(port)
    if build:
        result = subprocess.run([*COMPOSE, 'build', 'api'])
        require_success(result)
    # Let an existing worker finish before Compose recreates it for a new image.
    if current.get('worker', {}).get('State') == 'running':
        wait_for_idle()
    candidate = start
    while candidate <= 65535:
        if reusable:
            candidate = port
            reusable = False
        else:
            with reserve_port(candidate) as reservation:
                candidate = reservation.getsockname()[1]
        # Docker needs to bind itself. Retry genuine bind races, not unrelated errors.
        result = compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '90', port=candidate)
        if result.returncode:
            detail = (result.stderr + result.stdout).lower()
            if not any(message in detail for message in PORT_ERRORS):
                require_success(result)
            print(f'Porta {candidate} ocupada durante a inicialização; tentando a próxima.', flush=True)
            candidate += 1
            continue
        api = containers()['api']
        if host_matches(candidate, api['ID'][:12]):
            return announce(candidate)
        if not windows_available(candidate):
            print(f'Porta {candidate} não chega ao MyCut no Windows; tentando a próxima.', flush=True)
            candidate += 1
            continue
        raise RuntimeError('A API iniciou, mas não está acessível pelo Windows. Confira o encaminhamento localhost do WSL.')
    raise RuntimeError('Nenhuma porta disponível até 65535.')


def start_local(start):
    if not (ROOT / 'web/dist/index.html').is_file():
        raise ValueError('Compile a interface: cd web && pnpm install && npm run build')
    processes = []
    instance = uuid.uuid4().hex
    try:
        with reserve_port(start) as reservation:
            port = reservation.getsockname()[1]
            environment = {**os.environ, 'MYCUT_PORT': str(port), 'MYCUT_INSTANCE': instance,
                           'MYCUT_DATA_DIR': str(DATA), 'PYTHONPATH': str(ROOT / 'backend') +
                           os.pathsep + os.environ.get('PYTHONPATH', '')}
            # Keep the bound socket through exec: another Linux process cannot steal it.
            api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'mycut.api:app', '--fd', str(reservation.fileno())],
                                   cwd=ROOT, env=environment, pass_fds=(reservation.fileno(),))
            processes.append(api)
        deadline = time.monotonic() + 45
        while not host_matches(port, instance):
            if api.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('A API local não ficou acessível. Confira os logs acima e a rede do WSL.')
            time.sleep(.5)
        processes.append(subprocess.Popen([sys.executable, '-m', 'mycut.worker'], cwd=ROOT, env=environment))
        announce(port)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
        raise RuntimeError('API ou worker encerraram inesperadamente. Confira os logs acima.')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def install_service():
    if os.getuid() == 0:
        raise ValueError('Instale como seu usuário, sem sudo.')
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    unit = config / 'systemd/user/mycut-app.service'
    if unit.exists() and '# Managed by MyCut: scripts/launch.py' not in unit.read_text():
        raise ValueError(f'O serviço {unit} já existe e não foi criado pelo MyCut.')
    # No credentials or shell environment in the unit. ports.py restores WSL interop.
    def quote(value):
        value = str(value)
        if any(ord(char) < 32 for char in value):
            raise ValueError('Caminhos não podem conter caracteres de controle.')
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
    executable = shutil.which('python3')
    # Persist only the launcher's non-secret settings, including custom data roots.
    environment = '\n'.join('Environment=' + quote(f'{key}={value}').replace('$$', '$')
                            for key, value in {'MYCUT_DATA_DIR': DATA,
                                               'MYCUT_PORT': os.environ.get('MYCUT_PORT', '8321'),
                                               'PATH': '/usr/local/bin:/usr/bin:/bin'}.items())
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(f'''# Managed by MyCut: scripts/launch.py
[Unit]
Description=MyCut - containers com porta local automatica
StartLimitIntervalSec=0

[Service]
Type=exec
{environment}
ExecStart={quote(executable)} {quote(ROOT / 'scripts/launch.py')} docker --watch
Restart=always
RestartSec=10
TimeoutStopSec=15
UMask=0077

[Install]
WantedBy=default.target
''')
    os.chmod(unit, 0o600)
    username = pwd.getpwuid(os.getuid()).pw_name
    for command in (['systemd-analyze', '--user', 'verify', str(unit)],
                    ['loginctl', 'enable-linger', username], ['systemctl', '--user', 'daemon-reload'],
                    ['systemctl', '--user', 'enable', '--now', unit.name]):
        subprocess.run(command, check=True)
    print('mycut-app.service instalado. Endereço atual: ' + str(DATA / 'http.json'), flush=True)


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('docker', 'local', 'install'))
    parser.add_argument('--build', action='store_true', help='Reconstrói a imagem antes de iniciar.')
    parser.add_argument('--watch', action='store_true', help='Revalida a porta e os containers a cada 30 segundos.')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        if args.mode == 'install':
            install_service()
            return 0
        start = int(os.environ.get('MYCUT_PORT', '8321'))
        if not 1024 <= start <= 65535:
            raise ValueError('MYCUT_PORT deve estar entre 1024 e 65535.')
        while True:
            try:
                # Avoid concurrent starters fighting over the same published port.
                with (DATA / 'http.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    if args.mode == 'local':
                        start_local(start)
                    else:
                        url = start_docker(start, args.build)
                        if not args.watch:
                            print(f'MyCut: {url}', flush=True)
                args.build = False
            except (OSError, ValueError, RuntimeError) as exc:
                if not args.watch:
                    raise
                print(f'MyCut: {exc}. Nova tentativa em 30 segundos.', file=sys.stderr, flush=True)
            if not args.watch or args.mode == 'local':
                return 0
            time.sleep(30)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'Não foi possível iniciar o MyCut: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
