"""Referência do motor atual (Python/Pillow → FFmpeg libx264) para a qualificação do MYC-11.

Repete uma produção já concluída do MyCut, com o mesmo `production.make_video` do app, numa
cópia isolada dos dados: nada é gerado de novo em serviços pagos (a narração já existe no disco)
e o banco original não é tocado. Mede o tempo total, o laço de quadros e a memória, e produz
também a prévia do app (modo `preview`, 540×960 a 24 qps) para comparar com o arquivo final.

Uso: PYTHONPATH=backend python qualificacao/render/referencia-python/render.py <pasta .data> <id do job final> <saída>
"""
import json
import os
import resource
import shutil
import sqlite3
import sys
import time
from pathlib import Path


def copiar_dados(origem, destino, projeto):
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ('google-fonts', 'endings', 'flow_icons'):
        if (origem / nome).is_dir() and not (destino / nome).exists():
            shutil.copytree(origem / nome, destino / nome)
    if not (destino / 'projects' / projeto).exists():
        shutil.copytree(origem / 'projects' / projeto, destino / 'projects' / projeto,
                        ignore=lambda pasta, nomes: [n for n in nomes if n.endswith('.mp4') and 'renders' in pasta and 'voice' not in pasta])


def main():
    origem, job_original, saida = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
    with sqlite3.connect(origem / 'studio.sqlite3') as db:
        db.row_factory = sqlite3.Row
        job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (job_original,)).fetchone())
        projeto = dict(db.execute('SELECT * FROM projects WHERE id=?', (job['project_id'],)).fetchone())
    dados = saida / 'data'
    copiar_dados(origem, dados, job['project_id'])
    os.environ['MYCUT_DATA_DIR'] = str(dados)
    from mycut import production, store  # depois de apontar MYCUT_DATA_DIR para a cópia

    store.initialize()
    marcas = []
    progresso_original = store.progress
    store.progress = lambda job_id, pct, msg: (marcas.append((time.monotonic(), msg)), progresso_original(job_id, pct, msg))
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO projects VALUES (?,?,?,?)',
                   (projeto['id'], projeto['document'], projeto['created_at'], projeto['updated_at']))
    relatorio = {'motor': 'python-ffmpeg (atual)', 'job_original': job_original, 'cargaAntes': os.getloadavg()}
    for modo in ('final', 'preview'):
        novo = f'ref{modo}{int(time.time())}'
        with store.connect() as db:
            db.execute("UPDATE jobs SET state='succeeded' WHERE state IN ('queued','running')")  # sobras de uma rodada interrompida
            db.execute('INSERT INTO jobs (id,project_id,mode,state,progress,message,snapshot,output,created_at,updated_at) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (novo, job['project_id'], modo, 'running', 0, '', job['snapshot'], None, time.time(), time.time()))
        marcas.clear()
        inicio = time.monotonic()
        resultado = production.make_video(store.get_job(novo, private=True))
        fim = time.monotonic()
        with store.connect() as db:
            db.execute("UPDATE jobs SET state='succeeded' WHERE id=?", (novo,))
        laco = [t for t, m in marcas if m.startswith('Renderizando')]
        pasta = dados / resultado['directory']
        destino = saida / f'python-{modo}.mp4'
        shutil.copy2(pasta / 'short.mp4', destino)
        relatorio[modo] = {
            'arquivo': destino.name, 'duracaoVideo': resultado['duration'], 'tempoTotal': round(fim - inicio, 2),
            'laco_de_quadros': round((next((t for t, m in marcas if m.startswith('Finalizando')), fim) - laco[0]) if laco else 0, 2),
            'velocidade': round(resultado['duration'] / (fim - inicio), 3),
            'etapas': [[round(t - inicio, 2), m] for t, m in marcas if not m.startswith('Renderizando')],
        }
    relatorio['cargaDepois'] = os.getloadavg()
    relatorio['memoriaPicoMB'] = {'python': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
                                  'filhos_maior': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024}
    (saida / 'python.relatorio.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=1))
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
