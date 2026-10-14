"""One durable worker; each render runs in a cancellable process group."""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from . import store
from .config import DATA, configure


def run_once():
    job = store.claim()
    if not job:
        return False
    folder = DATA / 'projects' / job['project_id'] / 'renders' / job['id']
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'worker.log').open('wb') as log:
        module = 'mycut.production' if job['kind'] == 'render' else 'mycut.pipeline'
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
            message = {'plan': 'Roteiro, cenas e capa prontos', 'voice': 'Narração gerada pela ElevenLabs'}.get(job['kind'], 'Pronto para revisar')
            store.finish(job['id'], 'succeeded', message, output)
        else:
            message = (folder / 'worker.log').read_text(errors='replace').strip().splitlines()
            store.finish(job['id'], 'failed', message[-1][:600] if message else 'Falha na produção. Tente novamente.')
    return True


def main():
    configure()
    store.initialize()
    with (DATA / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Já existe um worker ativo neste diretório de dados.')
        store.recover()
        print('MyCut worker pronto.', flush=True)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        while True:
            store.heartbeat()
            if not run_once():
                time.sleep(1)


if __name__ == '__main__':
    main()
