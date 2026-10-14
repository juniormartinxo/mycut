"""Host-only runner. Standard library only; no credentials are copied to Docker."""
import fcntl
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from .bridge import BRIDGE, PROVIDERS, atomic_json
from . import agent_models


def command(provider, model, folder, schema, web):
    if provider not in PROVIDERS:
        raise ValueError('Provedor de agente desconhecido.')
    executable = shutil.which(provider)
    if not executable:
        raise ValueError(f'O CLI {provider} não está instalado no PATH do executor.')
    schema_text = json.dumps(schema, ensure_ascii=False)
    (folder / 'schema.json').write_text(schema_text)
    if provider == 'codex':
        args = [executable, 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
                '-c', 'approval_policy="never"', '-c', 'features.shell_tool=false',
                '-c', 'features.apps=false', '-c', 'mcp_servers={}',
                '-c', f'web_search="{"live" if web else "disabled"}"',
                '--output-schema', str(folder / 'schema.json'), '--output-last-message', str(folder / 'result.json'),
                '--color', 'never']
        if model:
            args += ['--model', model]
        return args+['-']
    if provider == 'claude':
        args = [executable, '-p', '--output-format', 'json', '--json-schema', schema_text,
                '--no-session-persistence', '--restricted', '--strict-mcp-config',
                '--mcp-config', '{"mcpServers":{}}', '--permission-mode', 'dontAsk',
                '--tools', 'WebSearch,WebFetch' if web else '']
        if web:
            args += ['--allowedTools', 'WebSearch,WebFetch']
    else:
        args = [executable, '--prompt-file', str(folder / 'prompt.txt'), '--output-format', 'json',
                '--json-schema', schema_text, '--no-subagents', '--no-plan', '--max-turns', '12',
                '--permission-mode', 'dontAsk', '--tools', 'WebSearch,WebFetch' if web else '',
                '--deny', 'MCPTool']
        if web:
            args += ['--allow', 'WebSearch', '--allow', 'WebFetch']
        else:
            args += ['--disable-web-search']
    if model:
        args += ['--model', model]
    return args


def parse_result(provider, folder, stdout):
    text = (folder / 'result.json').read_text() if provider == 'codex' and (folder / 'result.json').is_file() else stdout
    try:
        value = json.loads(text.strip())
        if isinstance(value, dict) and (value.get('is_error') or value.get('type') == 'error'):
            raise ValueError('O CLI reportou erro.')
        for key in ('structured_output', 'result', 'text'):
            if isinstance(value, dict) and key in value:
                value = value[key]
                break
        if isinstance(value, str):
            value = json.loads(value.strip().removeprefix('```json').removesuffix('```').strip())
        if not isinstance(value, dict):
            raise ValueError('A saída precisa ser um objeto.')
        return value
    except (ValueError, TypeError):
        raise ValueError(f'O {provider} não entregou JSON válido. Confira autenticação, modelo e limites do CLI.') from None


def heartbeat():
    atomic_json(BRIDGE / 'heartbeat.json', {'time': time.time(), 'protocol': 2,
                                         'providers': {p: bool(shutil.which(p)) for p in PROVIDERS}})


def disconnected(location, request):
    return (location / 'cancel').exists() or (request.get('kind') != 'probe' and
             (not (location / 'lease').exists() or time.time()-(location / 'lease').stat().st_mtime > 20))


def failure_message(provider, stdout, stderr, request_id):
    """Classify local diagnostics without forwarding tokens, account data or raw errors."""
    diagnostic = (stdout+'\n'+stderr).lower()
    if any(word in diagnostic for word in ('oauth session expired', 'failed to authenticate', 'not logged in', 'unauthorized')):
        reason = f'A sessão do {provider} não está autenticada ou expirou. Abra o CLI no WSL e entre novamente na sua conta.'
    elif any(word in diagnostic for word in ('eacces', 'eperm', 'permission denied', 'operation not permitted', 'read-only file system')):
        reason = f'O {provider} foi bloqueado por uma permissão local. Confira as permissões dos arquivos e execute o runner no seu terminal WSL.'
    elif any(word in diagnostic for word in ('rate limit', 'usage limit', 'quota exceeded', 'insufficient credits')):
        reason = f'O {provider} atingiu um limite de uso. Confira a cota no CLI antes de tentar novamente.'
    elif any(word in diagnostic for word in ('model not found', 'invalid model', 'model_not_found', 'not have access to model')):
        reason = f'O {provider} recusou o modelo. Atualize a lista e selecione um modelo liberado para sua conta.'
    else:
        reason = f'O {provider} encerrou com erro. Confira login, modelo e limite de uso no terminal.'
    return reason+f' Logs locais: agent-bridge/requests/{request_id}/cli.log e cli-error.log.'


def run_request(request_file):
    started = time.monotonic()
    location = request_file.parent
    response = location / 'response.json'
    if response.exists():
        return
    try:
        # Never silently repeat a CLI invocation abandoned by a runner restart.
        try:
            (location / 'started').touch(exist_ok=False)
        except FileExistsError:
            raise ValueError('O executor reiniciou durante esta etapa. Inicie uma nova produção para tentar novamente.') from None
        request = json.loads(request_file.read_text())
        if len(request['prompt']) > 100_000 or time.time() > request['expires']:
            raise ValueError('A solicitação do agente expirou ou excedeu o tamanho permitido.')
        if disconnected(location, request):
            raise ValueError('Solicitação cancelada ou worker desconectado.')
        with tempfile.TemporaryDirectory(prefix='mycut-agent-') as directory:
            folder = Path(directory)
            (folder / 'prompt.txt').write_text(request['prompt'])
            args = command(request['provider'], request.get('model', ''), folder, request['schema'], request['web'])
            # File output avoids pipe deadlocks for verbose CLIs. These logs stay local.
            with (location / 'cli.log').open('w+') as output, (location / 'cli-error.log').open('w+') as error, (folder / 'prompt.txt').open() as input_file:
                process = subprocess.Popen(args, cwd=folder, stdin=input_file, stdout=output, stderr=error, start_new_session=True)
                try:
                    while process.poll() is None:
                        heartbeat()
                        if disconnected(location, request) or time.time() > request['expires']:
                            raise ValueError('Agente interrompido: produção cancelada, expirada ou worker desconectado.')
                        time.sleep(1)
                    output.seek(0)
                    stdout = output.read(1_000_000)
                    if process.returncode:
                        error.seek(0)
                        raise ValueError(failure_message(request['provider'], stdout, error.read(1_000_000), location.name))
                    result = parse_result(request['provider'], folder, stdout)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
        if disconnected(location, request) or time.time() > request['expires']:
            raise ValueError('Solicitação cancelada ou expirada.')
        payload = {'result': result}
        if request.get('kind') == 'probe':
            from .agent_tests import validate_response
            validate_response(request, result)
            payload.update(elapsed=round(time.monotonic()-started, 2),
                           reported_models=agent_models.reported_models(request['provider'], stdout))
        atomic_json(response, payload)
    except (ValueError, KeyError, OSError) as exc:
        atomic_json(response, {'error': str(exc)[:500], 'elapsed': round(time.monotonic()-started, 2)})


def main():
    BRIDGE.mkdir(parents=True, exist_ok=True)
    with (BRIDGE / 'runner.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Já existe um executor de agentes conectado.')
        def stop(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        print('Executor MyCut conectado. CLIs usam o login local; Ctrl+C para encerrar.', flush=True)
        try:
            while True:
                heartbeat()
                agent_models.refresh()
                heartbeat()
                for request in sorted((BRIDGE / 'requests').glob('*/request.json')):
                    run_request(request)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            (BRIDGE / 'heartbeat.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
