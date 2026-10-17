"""Emendas e consistência de um áudio montado por trechos (ensaio Qwen ou lote ElevenLabs).

Uso: python emendas.py <áudio> <trechos.json> <whisper.json> [<mms.json>] > relatorio.json

Por trecho: duração, silêncio no começo e no fim, amplitude nas bordas (estalo), loudness integrada, ritmo em
caracteres por segundo e a fração de palavras que o Whisper reconheceu iguais ao texto (omissões, trocas ou
falas inventadas aparecem aqui). Por emenda: vão real entre falas e saltos de loudness e de ritmo.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

TAXA = 48000
SILENCIO_DB = -45


def sinal(audio):
    bruto = subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(audio), '-ac', '1', '-ar', str(TAXA),
                                     '-f', 'f32le', '-'])
    return np.frombuffer(bruto, dtype=np.float32)


def loudness(trecho):
    saida = subprocess.run(['ffmpeg', '-nostdin', '-f', 'f32le', '-ar', str(TAXA), '-ac', '1', '-i', 'pipe:0',
                            '-af', 'ebur128', '-f', 'null', '-'], input=trecho.tobytes(), capture_output=True).stderr
    valores = re.findall(rb'I:\s+(-?[\d.]+) LUFS', saida)
    return float(valores[-1]) if valores else None


def silencios(trecho):
    """Segundos de silêncio no começo e no fim (janelas de 10 ms abaixo de −45 dBFS)."""
    janela = TAXA // 100
    n = trecho.size // janela
    rms = np.sqrt(np.mean(trecho[:n * janela].reshape(n, janela) ** 2, axis=1) + 1e-12)
    voz = np.flatnonzero(20 * np.log10(rms) > SILENCIO_DB)
    if not voz.size:
        return trecho.size / TAXA, 0.0
    return voz[0] / 100, (n - 1 - voz[-1]) / 100


def main():
    audio, manifesto, whisper = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    s = sinal(audio)
    trechos = json.loads(manifesto.read_text(encoding='utf-8'))['trechos']
    palavras = json.loads(whisper.read_text(encoding='utf-8'))['palavras']
    resultado, k = [], 0
    for t in trechos:
        pedaco = s[round(t['inicio'] * TAXA):round(t['fim'] * TAXA)]
        n = len(t['texto'].split())
        mapeadas, k = palavras[k:k + n], k + n
        comeco, fim = silencios(pedaco)
        fala = max(1e-3, pedaco.size / TAXA - comeco - fim)
        resultado.append({
            'texto': t['texto'][:60], 'duracao': round(pedaco.size / TAXA, 2), 'silencio_inicio': comeco,
            'silencio_fim': fim, 'borda_inicio': round(float(np.abs(pedaco[:48]).max()), 4),
            'borda_fim': round(float(np.abs(pedaco[-48:]).max()), 4), 'lufs': loudness(pedaco),
            'caracteres_por_s': round(len(t['texto']) / fala, 1),
            'reconhecidas_iguais': round(sum(p.get('mapeamento') == 'exato' for p in mapeadas) / n, 3),
            'interpoladas': [p['palavra'] for p in mapeadas if p.get('mapeamento') == 'interpolado']})
    emendas = []
    for i in range(1, len(trechos)):
        a, b = resultado[i - 1], resultado[i]
        pausa = trechos[i]['inicio'] - trechos[i - 1]['fim']
        emendas.append({'entre': [i, i + 1], 'pausa_inserida': round(pausa, 2),
                        'vao_entre_falas': round(a['silencio_fim'] + pausa + b['silencio_inicio'], 2),
                        'salto_lufs': round(b['lufs'] - a['lufs'], 1) if a['lufs'] and b['lufs'] else None,
                        'salto_ritmo': round(b['caracteres_por_s'] - a['caracteres_por_s'], 1)})
    print(json.dumps({'audio': audio.name, 'trechos': resultado, 'emendas': emendas}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
