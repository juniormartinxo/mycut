"""Alinha uma narração palavra a palavra com o Whisper local do MyCut (sem enviar áudio).

Uso: PYTHONPATH=backend python qualificacao/render/midia/alinhar.py narracao.wav palavras.json [--cuda]
Grava [[palavra, início, fim], ...] em segundos, o formato que a composição consome.
"""
import argparse
import json
import os
import subprocess
import time

import numpy as np

from mycut import alignment
from mycut.config import MODEL, MODEL_DIR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio')
    ap.add_argument('saida')
    ap.add_argument('--cuda', action='store_true')
    args = ap.parse_args()
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    modelo = alignment.use_cached_whisper()(
        MODEL_DIR or MODEL, device='cuda' if args.cuda else 'cpu',
        compute_type='float16' if args.cuda else 'int8', cpu_threads=6, local_files_only=True)
    sinal = subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', '-i', args.audio,
                                     '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'])
    inicio = time.monotonic()
    segmentos, _ = modelo.transcribe(np.frombuffer(sinal, dtype=np.float32).copy(), language='pt', beam_size=5,
                                     vad_filter=True, word_timestamps=True, condition_on_previous_text=False)
    palavras = [[w.word.strip(), round(w.start, 3), round(w.end, 3)]
                for s in segmentos for w in (s.words or []) if w.word.strip()]
    with open(args.saida, 'w', encoding='utf-8') as f:
        json.dump(palavras, f, ensure_ascii=False)
    print(f'{len(palavras)} palavras alinhadas em {time.monotonic() - inicio:.0f} s')


if __name__ == '__main__':
    main()
