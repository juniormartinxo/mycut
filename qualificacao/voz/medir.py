"""Medições do alinhador local contra a referência da API.

  python medir.py referencia <pasta voice de um render do MyCut> <saída>
      Copia elevenlabs.mp3 e grava roteiro.txt e referencia.json a partir do alignment.json (tempos da API).
  python medir.py lote <pasta lote-tts|lote-dialogo> <saída>
      Junta os trechos de um lote pago num WAV, com as pausas do ensaio Qwen, e grava trechos.json e
      referencia.json (tempos da API por palavra, do alinhamento original ou do normalizado).
  python medir.py paragrafos <trechos.json do modo frase> <saída.json>
      Agrupa as frases por parágrafo, para alinhar o áudio do modo frase como se fosse por trecho.
  python medir.py frases <ensaio.wav> <trechos.json do modo frase> <alinhamento.json>...
      Referência exata para áudio Qwen: no modo frase cada frase foi gerada sozinha e emendada numa posição
      conhecida, então o começo da primeira palavra e o fim da última são medidos no próprio sinal.
  python medir.py comparar <referencia.json> <alinhamento.json>...
      Imprime, por alinhador, o desvio por palavra e a fração dentro de ±100 ms (JSON).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from emendas import TAXA as TAXA_EMENDAS, silencios, sinal
from medida import comparar
from texto import palavras_da_api

TAXA, PAUSA_PARAGRAFO = 44100, 0.9


def referencia(voz, saida):
    saida.mkdir(parents=True, exist_ok=True)
    dados = json.loads((voz / 'alignment.json').read_text(encoding='utf-8'))
    palavras = [{'palavra': w['word'], 'inicio': w['start'], 'fim': w['end']}
                for s in dados['segments'] for w in s['words']]
    shutil.copyfile(voz / 'elevenlabs.mp3', saida / 'elevenlabs.mp3')
    (saida / 'roteiro.txt').write_text(' '.join(p['palavra'] for p in palavras), encoding='utf-8')
    (saida / 'referencia.json').write_text(json.dumps({'origem': dados.get('provider'), 'palavras': palavras},
                                                      ensure_ascii=False, indent=1), encoding='utf-8')
    print(saida, len(palavras), 'palavras')


def lote(pasta, saida):
    saida.mkdir(parents=True, exist_ok=True)
    partes, trechos, palavras, cursor = [], [], [], 0.0
    for pedido in sorted(pasta.glob('pedido-*.json'), key=lambda p: int(p.stem.split('-')[1])):
        dados = json.loads(pedido.read_text(encoding='utf-8'))
        corpo, resposta = dados['corpo'], dados['resposta']
        texto = corpo.get('text') or corpo['inputs'][0]['text']
        bruto = subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(pasta / f'trecho-{dados["trecho"]}.mp3'),
                                         '-ac', '1', '-ar', str(TAXA), '-f', 'f32le', '-'])
        sinal = np.frombuffer(bruto, dtype=np.float32)
        if partes:
            partes.append(np.zeros(round(PAUSA_PARAGRAFO * TAXA), np.float32))
            cursor += PAUSA_PARAGRAFO
        fim = cursor + sinal.size / TAXA
        trechos.append({'paragrafo': len(trechos), 'texto': texto, 'inicio': round(cursor, 3), 'fim': round(fim, 3)})
        palavras += [{**p, 'inicio': round(p['inicio'] + cursor, 3), 'fim': round(p['fim'] + cursor, 3)}
                     for p in palavras_da_api(texto, resposta.get('alignment'), resposta.get('normalized_alignment'))]
        partes.append(sinal)
        cursor = fim
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'f32le', '-ar', str(TAXA), '-ac', '1', '-i', 'pipe:0',
                    str(saida / 'juntado.wav')], input=np.concatenate(partes).tobytes(), check=True)
    (saida / 'trechos.json').write_text(json.dumps({'origem': 'ElevenLabs', 'trechos': trechos}, ensure_ascii=False,
                                                   indent=1), encoding='utf-8')
    (saida / 'referencia.json').write_text(json.dumps({'origem': 'api', 'palavras': palavras}, ensure_ascii=False,
                                                      indent=1), encoding='utf-8')
    print(saida, len(trechos), 'trechos', len(palavras), 'palavras', round(cursor, 1), 's')


def paragrafos(origem, saida):
    frases = json.loads(origem.read_text(encoding='utf-8'))['trechos']
    grupos = {}
    for f in frases:
        grupos.setdefault(f['paragrafo'], []).append(f)
    trechos = [{'paragrafo': p, 'texto': ' '.join(f['texto'] for f in fs), 'inicio': fs[0]['inicio'], 'fim': fs[-1]['fim']}
               for p, fs in grupos.items()]
    saida.write_text(json.dumps({'origem': 'parágrafos do modo frase', 'trechos': trechos}, ensure_ascii=False,
                                indent=1), encoding='utf-8')
    print(saida, len(trechos), 'parágrafos')


def bordas_das_frases(audio, origem):
    """Começo e fim de fala de cada frase, medidos no sinal (silêncio abaixo de −45 dBFS em janelas de 10 ms)."""
    s = sinal(audio)
    bordas = []
    for f in json.loads(origem.read_text(encoding='utf-8'))['trechos']:
        comeco, fim = silencios(s[round(f['inicio'] * TAXA_EMENDAS):round(f['fim'] * TAXA_EMENDAS)])
        bordas.append((f['texto'].split(), f['inicio'] + comeco, f['fim'] - fim))
    return bordas


def frases(audio, origem, alinhamentos):
    bordas, relatorio = bordas_das_frases(audio, origem), {}
    for caminho in alinhamentos:
        palavras = json.loads(Path(caminho).read_text(encoding='utf-8'))['palavras']
        ref_inicio, med_inicio, ref_fim, med_fim, k = [], [], [], [], 0
        for texto, comeco, fim in bordas:
            primeira, ultima, k = palavras[k], palavras[k + len(texto) - 1], k + len(texto)
            ref_inicio.append({'palavra': texto[0], 'inicio': comeco, 'fim': comeco})
            med_inicio.append({**primeira, 'fim': primeira['inicio']})
            ref_fim.append({'palavra': texto[-1], 'inicio': fim, 'fim': fim})
            med_fim.append({**ultima, 'inicio': ultima['fim']})
        relatorio[caminho] = {'inicio_de_frase': comparar(ref_inicio, med_inicio),
                              'fim_de_frase': comparar(ref_fim, med_fim)}
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))


def main():
    acao, *resto = sys.argv[1:]
    if acao == 'referencia':
        referencia(Path(resto[0]), Path(resto[1]))
        return
    if acao == 'lote':
        lote(Path(resto[0]), Path(resto[1]))
        return
    if acao == 'paragrafos':
        paragrafos(Path(resto[0]), Path(resto[1]))
        return
    if acao == 'frases':
        frases(Path(resto[0]), Path(resto[1]), resto[2:])
        return
    ref = json.loads(Path(resto[0]).read_text(encoding='utf-8'))['palavras']
    relatorio = {}
    for caminho in resto[1:]:
        medido = json.loads(Path(caminho).read_text(encoding='utf-8'))
        relatorio[caminho] = comparar(ref, medido['palavras'])
    print(json.dumps(relatorio, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
