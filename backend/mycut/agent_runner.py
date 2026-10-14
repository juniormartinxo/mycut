"""Host-only runner. Standard library only; no credentials are copied to Docker."""
import fcntl
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from .bridge import BRIDGE, PROVIDERS, atomic_json
from . import agent_models, browser, commands, costs


def command(provider, model, folder, schema, web, navigator=None):
    if provider not in PROVIDERS:
        raise ValueError('Provedor de agente desconhecido.')
    launch = commands.launcher(provider)
    if not launch:
        raise ValueError(f'O comando do {provider} não foi encontrado no PATH do executor. Confira o comando em Conexões.')
    schema_text = json.dumps(schema, ensure_ascii=False)
    (folder / 'schema.json').write_text(schema_text)
    if provider == 'codex':
        args = [*launch, 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
                '-c', 'approval_policy="never"', '-c', 'features.shell_tool=false',
                '-c', 'features.apps=false',
                # Per-tool approval: the server-wide default hides the tools under approval_policy=never.
                '-c', 'mcp_servers=' + browser.toml({browser.SERVER: {
                    **navigator, 'enabled_tools': browser.TOOLS, 'startup_timeout_sec': 60,
                    'tools': {t: {'approval_mode': 'approve'} for t in browser.TOOLS}}} if navigator else {}),
                '-c', f'web_search="{"live" if web else "disabled"}"',
                '--output-schema', str(folder / 'schema.json'), '--output-last-message', str(folder / 'result.json'),
                '--color', 'never', '--json']
        if model:
            args += ['--model', model]
        return args+['-']
    if provider == 'claude':
        args = [*launch, '-p', '--output-format', 'json', '--json-schema', schema_text,
                '--no-session-persistence', '--restricted', '--strict-mcp-config',
                '--mcp-config', json.dumps({'mcpServers': {browser.SERVER: navigator} if navigator else {}}),
                '--permission-mode', 'dontAsk', '--tools', 'WebSearch,WebFetch' if web else '']
        if web:
            args += ['--allowedTools', ','.join(['WebSearch', 'WebFetch', *(f'mcp__{browser.SERVER}__{t}' for t in browser.TOOLS)]
                                                if navigator else ['WebSearch', 'WebFetch'])]
    else:
        args = [*launch, '--prompt-file', str(folder / 'prompt.txt'), '--output-format', 'json',
                '--json-schema', schema_text, '--no-subagents', '--no-plan', '--max-turns', '40' if navigator else '12',
                '--permission-mode', 'dontAsk', '--tools', 'WebSearch,WebFetch' if web else '']
        if navigator:
            # Grok reads MCP servers from the working directory; only the browser tools are allowed.
            # --trust lets Grok load MCP servers from this throwaway working directory.
            args.append('--trust')
            (folder / '.grok').mkdir(exist_ok=True)
            (folder / '.grok' / 'config.toml').write_text(
                f'[mcp_servers.{browser.SERVER}]\ncommand = {browser.toml(navigator["command"])}\n'
                f'args = {browser.toml(navigator["args"])}\n')
            for tool in browser.TOOLS:
                args += ['--allow', f'MCPTool({browser.SERVER}__{tool})']
            # A global MCP deny would also override these allows, so hide imported servers instead.
            # Calling a server that is not allowed cancels the whole run under dontAsk.
            args[:0] = ['env', 'GROK_CLAUDE_MCPS_ENABLED=false', 'GROK_CURSOR_MCPS_ENABLED=false']
        else:
            args += ['--deny', 'MCPTool']
        if web:
            args += ['--allow', 'WebSearch', '--allow', 'WebFetch']
        else:
            args += ['--disable-web-search']
    if model:
        args += ['--model', model]
    return args


def last_object(text):
    """Grok may stream an interim object before the final one: keep the last complete object."""
    decoder, index, found = json.JSONDecoder(), 0, None
    while index < len(text):
        value, index = decoder.raw_decode(text, index)
        found = value
        while index < len(text) and text[index].isspace():
            index += 1
    if found is None:
        raise ValueError('Saída vazia.')
    return found


def parse_result(provider, folder, stdout):
    text = (folder / 'result.json').read_text() if provider == 'codex' and (folder / 'result.json').is_file() else stdout
    try:
        value = json.loads(text.strip())
        if isinstance(value, dict) and (value.get('is_error') or value.get('type') == 'error'):
            raise ValueError('O CLI reportou erro.')
        for key in ('structured_output', 'structuredOutput', 'result', 'text'):
            if isinstance(value, dict) and value.get(key) is not None:
                value = value[key]
                break
        if isinstance(value, str):
            value = last_object(value.strip().removeprefix('```json').removesuffix('```').strip())
        if not isinstance(value, dict):
            raise ValueError('A saída precisa ser um objeto.')
        return value
    except (ValueError, TypeError):
        raise ValueError(f'O {provider} não entregou JSON válido. Confira autenticação, modelo e limites do CLI.') from None


def heartbeat():
    atomic_json(BRIDGE / 'heartbeat.json', {'time': time.time(), 'protocol': 3,
                                         'providers': {p: bool(commands.launcher(p)) for p in PROVIDERS},
                                         'browser': browser.status()})


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
    spent = []
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
            navigator, unavailable = browser.prepare() if request['web'] else (None, '')
            note = browser.GUIDANCE if navigator else (
                f'\nNAVEGADOR INDISPONÍVEL: {unavailable} Use WebSearch/WebFetch e registre em limitations '
                'que o navegador real não estava disponível.\n' if unavailable else '')
            (folder / 'prompt.txt').write_text(request['prompt']+note)
            args = command(request['provider'], request.get('model', ''), folder, request['schema'], request['web'], navigator)
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
                    # A failed call may still have consumed tokens; the envelope says how many.
                    spent = costs.extract(request['provider'], request.get('model', ''), stdout)
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
        payload = {'result': result, 'usage': spent}
        if request.get('kind') == 'probe':
            from .agent_tests import validate_response
            validate_response(request, result)
            payload.update(elapsed=round(time.monotonic()-started, 2),
                           reported_models=agent_models.reported_models(request['provider'], stdout))
        atomic_json(response, payload)
    except (ValueError, KeyError, OSError) as exc:
        atomic_json(response, {'error': str(exc)[:500], 'elapsed': round(time.monotonic()-started, 2), 'usage': spent})


def test_browser():
    """Requested from Conexões; runs while idle, like model discovery."""
    marker = BRIDGE / 'browser-test'
    try:
        requested = json.loads(marker.read_text())
    except (OSError, ValueError):
        return
    marker.unlink(missing_ok=True)
    result = {'id': requested.get('id', ''), 'checked_at': time.time(), 'version': '', 'error': ''}
    try:
        result['version'] = browser.probe()
    except ValueError as exc:
        result['error'] = str(exc)[:500]
    atomic_json(BRIDGE / 'browser-test.json', result)


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
                test_browser()
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
