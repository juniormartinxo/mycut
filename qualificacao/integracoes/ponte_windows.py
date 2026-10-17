"""Ponte de notificações do Windows para o serviço no WSL (qualificação MYC-13).

O serviço chama o powershell.exe do Windows pela interoperabilidade do WSL. O
script ponte_windows.ps1 registra o AUMID do MyCut no HKCU, mostra o toast e
devolve o estado do notificador e as tags presentes na Central de Notificações.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

AUMID = 'MyCut'
NOME = 'MyCut'
GRUPO = 'mycut'
SCRIPT = Path(__file__).with_name('ponte_windows.ps1')
# Mesmo alias de scripts/agents.sh: serviços de usuário não herdam o socket do terminal.
INTEROP = '/run/WSL/1_interop'
# Unidades systemd não recebem as pastas do Windows que o WSL acrescenta ao PATH do terminal.
POWERSHELL = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

# Valores de Windows.UI.Notifications.NotificationSetting.
CONDICOES = {
    'Enabled': 'liberada',
    'DisabledForApplication': 'bloqueada_no_app',
    'DisabledForUser': 'bloqueada_pelo_usuario',
    'DisabledByGroupPolicy': 'bloqueada_por_politica',
    'DisabledByManifest': 'bloqueada_pelo_manifesto',
}


def avaliar(resposta):
    # A chave global (todas as notificações desligadas) vale acima da do app.
    if resposta.get('toastsGlobais') == 0:
        return 'desligada_para_todos'
    return CONDICOES.get(resposta['setting'], 'desconhecida')


def executar_powershell(acao, pedido):
    env = dict(os.environ)
    if not Path(env.get('WSL_INTEROP', '/')).is_socket() and Path(INTEROP).is_socket():
        env['WSL_INTEROP'] = INTEROP
    codificado = base64.b64encode(json.dumps(pedido).encode()).decode()
    script = subprocess.check_output(['wslpath', '-w', str(SCRIPT)], text=True).strip()
    resultado = subprocess.run(
        [shutil.which('powershell.exe') or POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
         '-File', script, '-Acao', acao, '-Pedido', codificado],
        env=env, capture_output=True, text=True, timeout=60,
    )
    if resultado.returncode:
        raise RuntimeError(f'PowerShell falhou ({resultado.returncode}): {resultado.stderr.strip()}')
    return json.loads(resultado.stdout.lstrip('\ufeff'))


def condicao_atual(executar=executar_powershell):
    return avaliar(executar('estado', {'aumid': AUMID}))


def notificar(titulo, texto, tag, executar=executar_powershell):
    xml = ('<toast><visual><binding template="ToastGeneric">'
           f'<text>{escape(titulo)}</text><text>{escape(texto)}</text>'
           '</binding></visual></toast>')
    resposta = executar('enviar', {'aumid': AUMID, 'nome': NOME, 'grupo': GRUPO, 'tag': tag, 'xml': xml})
    return {'entregue': tag in resposta.get('historico', []), 'condicao': avaliar(resposta)}


def main(argv):
    if argv[:1] == ['estado']:
        print(json.dumps({'condicao': condicao_atual()}))
    elif argv[:1] == ['notificar'] and len(argv) == 4:
        print(json.dumps(notificar(*argv[1:]), ensure_ascii=False))
    else:
        print('uso: ponte_windows.py estado | notificar <título> <texto> <tag>', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
