"""Loopback port allocation shared by the Docker and native launchers (stdlib only)."""
import base64
import errno
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import urllib.request


def is_wsl():
    return 'microsoft' in os.uname().release.lower()


def powershell(script):
    executable = shutil.which('powershell.exe') or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    environment = dict(os.environ)
    if not Path(environment.get('WSL_INTEROP', '/nonexistent')).is_socket():
        environment['WSL_INTEROP'] = '/run/WSL/1_interop'
    encoded = base64.b64encode(('$ErrorActionPreference="Stop"; $ProgressPreference="SilentlyContinue"; '
                                + script).encode('utf-16-le')).decode('ascii')
    try:
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                cwd='/mnt/c', env=environment, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('Não foi possível verificar o Windows via WSL interop/PowerShell.') from exc
    if result.returncode:
        raise RuntimeError('A verificação de portas no Windows falhou; confira o WSL interop/PowerShell.')
    return result.stdout.strip().lstrip('\ufeff')


def windows_available(port):
    if not is_wsl():
        return True
    # A bind also detects excluded/reserved ports, which a listener list misses.
    result = powershell(f'''
$listeners = @()
try {{
  foreach ($address in @('127.0.0.1', '::1')) {{
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse($address), {int(port)})
    $listener.ExclusiveAddressUse = $true
    $listeners += $listener
    $listener.Start()
  }}
  'free'
}} catch [Net.Sockets.SocketException] {{ 'busy' }}
finally {{ foreach ($listener in $listeners) {{ $listener.Stop() }} }}
''')
    if result not in ('free', 'busy'):
        raise RuntimeError('Resposta inesperada ao verificar a porta no Windows.')
    return result == 'free'


def reserve_port(start):
    if not 1024 <= start <= 65535:
        raise ValueError('MYCUT_PORT deve estar entre 1024 e 65535.')
    for port in range(start, 65536):
        # In mirrored WSL networking our Linux reservation also occupies the Windows
        # port. Probe Windows first so we do not mistake our own socket for a conflict.
        if not windows_available(port):
            print(f'Porta {port} indisponível no Windows; tentando a próxima.', flush=True)
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            # localhost can resolve to IPv6 first: avoid reaching an unrelated service.
            if socket.has_ipv6:
                with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as ipv6:
                    ipv6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    ipv6.bind(('::1', port))
            return sock
        except OSError as exc:
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES):
                sock.close()
                raise
        except BaseException:
            sock.close()
            raise
        sock.close()
        print(f'Porta {port} indisponível; tentando a próxima.', flush=True)
    raise RuntimeError(f'Nenhuma porta disponível entre {start} e 65535.')


def host_matches(port, instance):
    url = f'http://127.0.0.1:{int(port)}/api/health'
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=3) as response:
            health = json.load(response)
        if not isinstance(health, dict) or health.get('instance') != instance or health.get('status') != 'ok':
            return False
        if is_wsl():
            # Check from Windows too. No proxy or redirects to an unrelated service.
            health = json.loads(powershell(f'''
try {{
  $request = [Net.HttpWebRequest]::Create('{url}')
  $request.Proxy = $null; $request.Timeout = 3000; $request.AllowAutoRedirect = $false
  $response = $request.GetResponse()
  try {{ $reader = [IO.StreamReader]::new($response.GetResponseStream()); $reader.ReadToEnd() }}
  finally {{ $response.Close() }}
}} catch {{ '{{}}' }}
'''))
            return isinstance(health, dict) and health.get('instance') == instance and health.get('status') == 'ok'
        return True
    except (OSError, ValueError):
        return False
