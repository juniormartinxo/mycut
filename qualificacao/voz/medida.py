"""Qualidade de um alinhamento local medida contra uma referência (os tempos da API para o mesmo áudio)."""
import math
import statistics

from texto import chave

TOLERANCIA_MS = 100


def ordem(valores, fracao):
    """Percentil pelo posto mais próximo: um valor que de fato ocorreu."""
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(fracao * len(ordenados)) - 1)]


def resumo(desvios):
    return {'mediana': round(statistics.median(desvios)), 'p90': ordem(desvios, .9), 'p95': ordem(desvios, .95),
            'max': max(desvios)}


def dentro(desvios):
    return round(sum(d <= TOLERANCIA_MS for d in desvios) / len(desvios), 4) if desvios else None


def comparar(referencia, medido, limiar=0.5):
    """Desvio absoluto por palavra, em ms, do início e do fim; fração de inícios dentro da tolerância (±100 ms no
    piloto, Q48) e essa fração separada pela confiança do alinhador, para saber se a confiança baixa avisa o erro."""
    if [chave(p['palavra']) for p in referencia] != [chave(p['palavra']) for p in medido]:
        raise ValueError('Os alinhamentos não são do mesmo texto.')
    inicio = [round(abs(m['inicio'] - r['inicio']) * 1000) for r, m in zip(referencia, medido)]
    fim = [round(abs(m['fim'] - r['fim']) * 1000) for r, m in zip(referencia, medido)]
    grupos = {'alta': [], 'baixa': []}
    for desvio, m in zip(inicio, medido):
        if 'confianca' in m:
            grupos['alta' if m['confianca'] >= limiar else 'baixa'].append(desvio)
    return {'palavras': len(inicio), 'inicio_ms': resumo(inicio), 'fim_ms': resumo(fim),
            'dentro_100ms': dentro(inicio),
            'por_confianca': {k: {'palavras': len(v), 'dentro_100ms': dentro(v)} for k, v in grupos.items()}}
