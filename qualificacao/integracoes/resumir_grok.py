"""Resume a saída em fluxo (--output-format streaming-json) de uma rodada do Grok Build (MYC-13).

Cada chamada de ferramenta aparece como um evento tool_call com os argumentos
exatos, seguido de tool_call_update com o status final: é por ela que um pedido
de clipe pode ser contado. O evento end traz a sessão, o turno e o custo de texto.
"""
import json
import sys


def resumir(linhas):
    resumo = {'sessao': None, 'turno': None, 'custo_texto_usd': None, 'chamadas': []}
    chamadas = {}
    for linha in linhas:
        evento = json.loads(linha)
        tipo = evento.get('type')
        if tipo == 'tool_call':
            chamada = {'id': evento['toolCallId'], 'ferramenta': evento['toolName'],
                       'argumentos': evento.get('rawInput'), 'status': evento.get('status'),
                       'arquivo': None, 'erro': None}
            chamadas[chamada['id']] = chamada
            resumo['chamadas'].append(chamada)
        elif tipo == 'tool_call_update' and evento.get('status'):
            chamada = chamadas[evento['toolCallId']]
            chamada['status'] = evento['status']
            saida = evento.get('rawOutput') or {}
            chamada['arquivo'] = saida.get('path')
            chamada['erro'] = saida.get('message') if saida.get('error') else None
        elif tipo == 'end':
            resumo.update(sessao=evento.get('sessionId'), turno=evento.get('requestId'),
                          custo_texto_usd=evento.get('total_cost_usd'))
    return resumo


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('uso: resumir_grok.py <stream.ndjson>')
    with open(sys.argv[1], encoding='utf-8') as arquivo:
        print(json.dumps(resumir(arquivo), ensure_ascii=False, indent=2))
