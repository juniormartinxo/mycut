"""One durable worker; each render runs in a cancellable process group.
Cover chat generations use their own lane, so a long production never delays them."""
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from . import store
from .config import DATA, configure


MODULES = {'render': 'mycut.production', 'cover': 'mycut.covers', 'scene_edit': 'mycut.scene_chat'}
MESSAGES = {'plan': 'Roteiro e cenas prontos', 'scenes': 'Cenas recriadas pelos agentes',
            'voice': 'Narração gerada pela ElevenLabs', 'cover': 'Imagem pronta', 'art': 'Imagens da Arte prontas', 'scene_edit': 'Proposta pronta para revisar'}


def run_once(covers=False):
    job = store.claim(covers)
    if not job:
        return False
    folder = DATA / 'projects' / job['project_id'] / 'renders' / job['id']
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'worker.log').open('wb') as log:
        module = MODULES.get(job['kind'], 'mycut.pipeline')
        process = subprocess.Popen([sys.executable, '-m', module, job['id']],
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            while process.poll() is None:
                store.heartbeat()
                if store.get_job(job['id'])['state'] == 'cancelled':
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(.5)
            code = process.wait()
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            store.finish(job['id'], 'failed', 'Produção interrompida. Tente gerar uma nova versão.')
            raise
    if store.get_job(job['id'])['state'] != 'cancelled':
        if code == 0:
            output = json.loads((folder / 'result.json').read_text())
            store.finish(job['id'], 'succeeded', final_message(job, output), output)
        else:
            message = (folder / 'worker.log').read_text(errors='replace').strip().splitlines()
            store.finish(job['id'], 'failed', message[-1][:600] if message else 'Falha na produção. Tente novamente.')
    return True


def final_message(job, output):
    """What a finished production says: one that stopped in the Arte tab says why it waits for the author, and a
    Short livre says which B-roll clips are still missing."""
    if job['kind'] not in ('pipeline', 'plan', 'art'):
        return MESSAGES.get(job['kind'], 'Pronto para revisar')
    from .materials import note
    project = store.get_project(job['project_id'])
    return outcome(job, output, project.get('art') or {}) + note(project)


def outcome(job, output, art):
    """The message of the production itself, before the clips still missing."""
    if art.get('then') == job['kind']:
        from .art import stopped
        return stopped(art['requests'])
    if job['kind'] == 'art' and output:
        return 'Imagens da Arte, narração e vídeo prontos'
    return MESSAGES.get(job['kind'], 'Pronto para revisar')


def main():
    configure()
    store.initialize()
    with (DATA / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Já existe um worker ativo neste diretório de dados.')
        store.recover()
        from . import exporting
        exporting.recover()
        print('MyCut worker pronto.', flush=True)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        def lane(covers):
            while True:
                store.heartbeat()
                if not run_once(covers):
                    time.sleep(1)
        threading.Thread(target=lane, args=(True,), daemon=True, name='covers').start()
        # Exports of horizontal projects have their own lane, beside the Shorts' productions.
        threading.Thread(target=exporting.lane, daemon=True, name='exports').start()
        lane(False)


if __name__ == '__main__':
    main()
