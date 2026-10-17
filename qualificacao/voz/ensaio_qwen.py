"""Áudio de ensaio Qwen de um texto longo, gerado por trechos de fala (ou por frase, para comparar) e emendado
com pausas fixas. Roda no ambiente da narração local (torch + qwen-tts), sem rede e sem ElevenLabs.

Uso: python ensaio_qwen.py roteiro.txt .saida/qwen-trecho --perfil <perfil.json> --raiz <checkout com .cache>
     [--modo trecho|frase] [--limite 500] [--juntar 1] [--lote 4]

O perfil é o JSON local da voz (referência, transcrição, modelo, revisão e configuração de geração); áudio de
referência e pesos ficam fora do Git. Grava ensaio.wav (bruto, sem normalização por trecho) e trechos.json com
o texto, o início e o fim de cada trecho no arquivo emendado.
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from texto import trechos

PAUSA_TRECHO, PAUSA_PARAGRAFO = 0.35, 0.9


def unidades(roteiro, modo, limite, juntar):
    paragrafos = [p.strip() for p in roteiro.split('\n\n') if p.strip()]
    # --juntar N une N parágrafos num trecho só, para testar trechos mais longos que um parágrafo.
    paragrafos = [' '.join(paragrafos[i:i + juntar]) for i in range(0, len(paragrafos), juntar)]
    if modo == 'trecho':
        return trechos('\n\n'.join(paragrafos), limite)
    return [{'paragrafo': p, 'texto': f} for p, paragrafo in enumerate(paragrafos)
            for f in re.split(r'(?<=[.!?…])\s+', paragrafo) if f.strip()]


def carregar(perfil, raiz):
    os.environ.update(HF_HOME=str(raiz / '.cache/huggingface'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    import torch
    from qwen_tts import Qwen3TTSModel
    modelo = perfil['model']
    snapshot = (raiz / '.cache/huggingface/hub' / ('models--' + modelo['id'].replace('/', '--')) / 'snapshots'
                / modelo['revision'])
    tts = Qwen3TTSModel.from_pretrained(str(snapshot), device_map='cuda:0', dtype=torch.bfloat16,
                                        attn_implementation=perfil['generation']['attention'], local_files_only=True)
    with torch.inference_mode():
        prompt = tts.create_voice_clone_prompt(ref_audio=str(raiz / perfil['reference']['audio']),
                                               ref_text=perfil['reference']['text'], x_vector_only_mode=False)
    return tts, prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roteiro', type=Path)
    ap.add_argument('saida', type=Path)
    ap.add_argument('--perfil', type=Path, required=True)
    ap.add_argument('--raiz', type=Path, required=True)
    ap.add_argument('--modo', choices=['trecho', 'frase'], default='trecho')
    ap.add_argument('--limite', type=int, default=500)
    ap.add_argument('--juntar', type=int, default=1)
    ap.add_argument('--lote', type=int, default=4)
    args = ap.parse_args()
    perfil = json.loads(args.perfil.read_text(encoding='utf-8'))
    geracao = perfil['generation']
    itens = unidades(args.roteiro.read_text(encoding='utf-8'), args.modo, args.limite, args.juntar)
    tts, prompt = carregar(perfil, args.raiz)
    import torch
    sinais, sr, inicio = [], None, time.monotonic()
    for k in range(0, len(itens), args.lote):
        lote = itens[k:k + args.lote]
        torch.manual_seed(geracao['seed'] + k)
        with torch.inference_mode():
            waves, sr = tts.generate_voice_clone(
                text=[t['texto'] for t in lote], language=[geracao['language']] * len(lote),
                voice_clone_prompt=prompt * len(lote) if isinstance(prompt, list) else [prompt] * len(lote),
                max_new_tokens=geracao['max_new_tokens'])
        sinais += [np.asarray(w, dtype=np.float32) for w in waves]
        print(f'{len(sinais)}/{len(itens)} · {sum(s.size for s in sinais) / sr:.0f} s de áudio em '
              f'{time.monotonic() - inicio:.0f} s', flush=True)
    gerado_em = time.monotonic() - inicio
    partes, manifesto, cursor = [], [], 0.0
    for i, (item, sinal) in enumerate(zip(itens, sinais)):
        if i:
            pausa = PAUSA_PARAGRAFO if item['paragrafo'] != itens[i - 1]['paragrafo'] else PAUSA_TRECHO
            partes.append(np.zeros(round(pausa * sr), np.float32))
            cursor += pausa
        manifesto.append({**item, 'inicio': round(cursor, 3), 'fim': round(cursor + sinal.size / sr, 3),
                          'atingiu_limite_de_tokens': sinal.size / sr >= geracao['max_new_tokens'] / 12 - 0.5})
        partes.append(sinal)
        cursor += sinal.size / sr
    args.saida.mkdir(parents=True, exist_ok=True)
    sf.write(args.saida / 'ensaio.wav', np.concatenate(partes), sr, subtype='PCM_16')
    (args.saida / 'trechos.json').write_text(json.dumps({
        'origem': 'Qwen3-TTS local (ensaio, sem ElevenLabs)', 'modelo': perfil['model'], 'modo': args.modo,
        'limite': args.limite, 'juntar': args.juntar, 'lote': args.lote, 'sample_rate': sr,
        'duracao': round(cursor, 3), 'tempo_de_geracao_s': round(gerado_em, 1),
        'gpu': torch.cuda.get_device_name(0), 'trechos': manifesto}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'pronto: {cursor:.1f} s de áudio em {gerado_em:.0f} s', flush=True)


if __name__ == '__main__':
    main()
