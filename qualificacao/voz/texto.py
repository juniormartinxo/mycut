"""Texto da narração: trechos de fala e correspondência entre roteiro, fala e tempos."""
import difflib
import re
import unicodedata


def trechos(roteiro, limite):
    """Divide o roteiro em trechos de fala (Q28): cada parágrafo é um trecho; um parágrafo maior que o limite de
    caracteres é dividido entre frases, juntando frases vizinhas enquanto couberem. Uma frase nunca é cortada,
    mesmo que sozinha passe do limite."""
    resultado = []
    for p, paragrafo in enumerate(t.strip() for t in roteiro.split('\n\n') if t.strip()):
        atual = ''
        for frase in re.split(r'(?<=[.!?…])\s+', paragrafo):
            if atual and len(atual) + 1 + len(frase) > limite:
                resultado.append({'paragrafo': p, 'texto': atual})
                atual = frase
            else:
                atual = f'{atual} {frase}' if atual else frase
        resultado.append({'paragrafo': p, 'texto': atual})
    return resultado


def palavras_com_tempos(alinhamento):
    """As palavras de um alinhamento por caractere, com o início do primeiro e o fim do último caractere."""
    caracteres = alinhamento['characters']
    inicios, fins = alinhamento['character_start_times_seconds'], alinhamento['character_end_times_seconds']
    palavras, atual = [], None
    for c, inicio, fim in zip(caracteres, inicios, fins, strict=True):
        if c.isspace():
            atual = None
        elif atual is None:
            atual = {'palavra': c, 'inicio': inicio, 'fim': fim}
            palavras.append(atual)
        else:
            atual['palavra'] += c
            atual['fim'] = fim
    return palavras


def palavras_da_api(texto, alinhamento, normalizado):
    """Tempos de cada palavra do texto enviado à ElevenLabs, a partir dos alinhamentos devolvidos para o texto
    original e para o normalizado. Os índices dos dois não são equivalentes ('25' vira 'vinte e cinco')."""
    if alinhamento and ''.join(alinhamento['characters']) == texto:
        return [{**p, 'mapeamento': 'exato'} for p in palavras_com_tempos(alinhamento)]
    if normalizado:
        return corresponder(texto.split(), palavras_com_tempos(normalizado))
    raise ValueError('A resposta não trouxe alinhamento utilizável.')


def chave(palavra):
    palavra = unicodedata.normalize('NFKD', palavra.casefold())
    return ''.join(c for c in palavra if c.isalnum() and not unicodedata.combining(c))


def corresponder(palavras, faladas, duracao=None):
    """Dá a cada palavra do texto os tempos das palavras faladas correspondentes. Iguais (sem caixa, acento e
    pontuação) são 'exato'; um grupo do texto escrito de outro jeito na fala ('25' e 'vinte e cinco') divide o
    intervalo do grupo falado pelo tamanho das palavras e é 'aproximado'; palavras sem correspondente dividem o vão
    entre as vizinhas e são 'interpoladas', sem confiança. Palavras faladas a mais são ignoradas."""
    resultado = [{'palavra': p} for p in palavras]
    opcoes = difflib.SequenceMatcher(a=[chave(p) for p in palavras], b=[chave(f['palavra']) for f in faladas],
                                     autojunk=False).get_opcodes()
    for operacao, i1, i2, j1, j2 in opcoes:
        if operacao == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2), strict=True):
                resultado[i].update(inicio=faladas[j]['inicio'], fim=faladas[j]['fim'], mapeamento='exato')
                if 'confianca' in faladas[j]:
                    resultado[i]['confianca'] = faladas[j]['confianca']
        elif operacao == 'replace':
            dividir(resultado, i1, i2, faladas[j1]['inicio'], faladas[j2 - 1]['fim'], 'aproximado')
            confiancas = [f['confianca'] for f in faladas[j1:j2] if 'confianca' in f]
            for i in range(i1, i2) if confiancas else ():
                resultado[i]['confianca'] = min(confiancas)
    fim_da_fala = faladas[-1]['fim'] if duracao is None and faladas else duracao or 0.0
    i = 0
    while i < len(resultado):
        if 'inicio' in resultado[i]:
            i += 1
            continue
        j = i
        while j < len(resultado) and 'inicio' not in resultado[j]:
            j += 1
        inicio = resultado[i - 1]['fim'] if i else 0.0
        dividir(resultado, i, j, inicio, resultado[j]['inicio'] if j < len(resultado) else fim_da_fala, 'interpolado')
        for k in range(i, j):
            resultado[k]['confianca'] = 0.0
        i = j
    return resultado


def dividir(resultado, i1, i2, inicio, fim, mapeamento):
    """Reparte [inicio, fim] entre as palavras i1..i2-1 na proporção do tamanho de cada uma."""
    pesos = [len(resultado[i]['palavra']) for i in range(i1, i2)]
    cursor = inicio
    for i, peso in zip(range(i1, i2), pesos, strict=True):
        proximo = cursor + max(0.0, fim - inicio) * peso / sum(pesos)
        resultado[i].update(inicio=round(cursor, 3), fim=round(proximo, 3), mapeamento=mapeamento)
        cursor = proximo


def casar_roteiro(roteiro, reconhecidas, duracao):
    """Palavras do roteiro com os tempos e a confiança de um alinhador local, que reconhece a fala com outra
    grafia (números por extenso, nomes trocados) e às vezes perde ou acrescenta palavras."""
    return corresponder(roteiro.split(), reconhecidas, duracao)
