"""Alinhador local da fala em PT-BR, por trecho: Whisper large-v3 (o do MyCut) ou alinhamento forçado MMS
(torchaudio). Nenhum áudio sai da máquina.

Uso: PYTHONPATH=../../backend python alinhar.py <áudio> <trechos.json | roteiro.txt> <saída.json>
     --alinhador whisper|mms [--cpu]

Com trechos.json (saída do ensaio_qwen.py) cada trecho é alinhado no seu intervalo; com um roteiro em texto, o
áudio inteiro é um trecho. Grava as palavras do roteiro com início, fim, confiança e mapeamento.
"""
import argparse
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path

import numpy as np

from texto import casar_roteiro

TAXA = 16000


def sinal(audio):
    bruto = subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(audio), '-ac', '1', '-ar',
                                     str(TAXA), '-f', 'f32le', '-'])
    return np.frombuffer(bruto, dtype=np.float32).copy()


def segmentos(origem, duracao):
    if origem.suffix == '.json':
        return [{'texto': t['texto'], 'inicio': t['inicio'], 'fim': t['fim']}
                for t in json.loads(origem.read_text(encoding='utf-8'))['trechos']]
    return [{'texto': origem.read_text(encoding='utf-8'), 'inicio': 0.0, 'fim': duracao}]


class Whisper:
    def __init__(self, cuda):
        from mycut import alignment
        from mycut.config import MODEL, MODEL_DIR
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        self.modelo = alignment.use_cached_whisper()(
            MODEL_DIR or MODEL, device='cuda' if cuda else 'cpu', compute_type='float16' if cuda else 'int8',
            cpu_threads=6, local_files_only=True)

    def palavras(self, trecho, texto):
        resultado, _ = self.modelo.transcribe(trecho, language='pt', beam_size=5, vad_filter=False,
                                              word_timestamps=True, condition_on_previous_text=False)
        reconhecidas = [{'palavra': w.word.strip(), 'inicio': w.start, 'fim': w.end, 'confianca': round(w.probability, 3)}
                        for s in resultado for w in (s.words or []) if w.word.strip()]
        return casar_roteiro(texto, reconhecidas, duracao=trecho.size / TAXA)


def romanizar(palavra):
    """Letras sem acento para o dicionário do MMS; palavras com números ou símbolos (25, R$, @) viram o coringa,
    que absorve qualquer fala ('vinte e cinco') sem exigir normalização do texto."""
    nucleo = re.sub(r'^\W+|\W+$', '', palavra)
    if not nucleo or re.search(r'[^\w\'-]|\d', nucleo):
        return None
    letras = unicodedata.normalize('NFKD', nucleo.lower())
    letras = ''.join(c for c in letras if c in "abcdefghijklmnopqrstuvwxyz'")
    return letras or None


class Mms:
    def __init__(self, cuda):
        import torch
        import torchaudio
        self.torch, self.F = torch, torchaudio.functional
        self.dispositivo = 'cuda' if cuda else 'cpu'
        pacote = torchaudio.pipelines.MMS_FA
        self.modelo = pacote.get_model(with_star=True).to(self.dispositivo)
        self.dicionario = pacote.get_dict(star='*')

    def palavras(self, trecho, texto):
        torch = self.torch
        escritas = texto.split()
        formas = [romanizar(p) for p in escritas]
        alvos = [self.dicionario[c] for f in formas for c in (f or '*')]
        with torch.inference_mode():
            emissao, _ = self.modelo(torch.from_numpy(trecho).unsqueeze(0).to(self.dispositivo))
            alinhado, pontos = self.F.forced_align(emissao, torch.tensor([alvos], device=self.dispositivo), blank=0)
        spans = self.F.merge_tokens(alinhado[0], pontos[0].exp())
        segundos_por_quadro = trecho.size / TAXA / emissao.size(1)
        resultado, k = [], 0
        for escrita, forma in zip(escritas, formas, strict=True):
            n = len(forma or '*')
            grupo, k = spans[k:k + n], k + n
            resultado.append({'palavra': escrita, 'inicio': round(grupo[0].start * segundos_por_quadro, 3),
                              'fim': round(grupo[-1].end * segundos_por_quadro, 3),
                              'confianca': round(sum(s.score * len(s) for s in grupo) / sum(len(s) for s in grupo), 3),
                              'mapeamento': 'exato' if forma else 'aproximado'})
        return resultado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio', type=Path)
    ap.add_argument('roteiro', type=Path)
    ap.add_argument('saida', type=Path)
    ap.add_argument('--alinhador', choices=['whisper', 'mms'], required=True)
    ap.add_argument('--cpu', action='store_true')
    args = ap.parse_args()
    audio = sinal(args.audio)
    alinhador = (Whisper if args.alinhador == 'whisper' else Mms)(cuda=not args.cpu)
    inicio, palavras = time.monotonic(), []
    for s in segmentos(args.roteiro, audio.size / TAXA):
        trecho = audio[round(s['inicio'] * TAXA):round(s['fim'] * TAXA)]
        palavras += [{**p, 'inicio': round(p['inicio'] + s['inicio'], 3), 'fim': round(p['fim'] + s['inicio'], 3)}
                     for p in alinhador.palavras(trecho, s['texto'])]
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps({'alinhador': args.alinhador, 'origem': 'local', 'audio': args.audio.name,
                                      'tempo_s': round(time.monotonic() - inicio, 1), 'palavras': palavras},
                                     ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(palavras)} palavras em {time.monotonic() - inicio:.0f} s')


if __name__ == '__main__':
    main()
