"""Rota e modelo da ElevenLabs na prática: consultas sem custo (modelos, assinatura, histórico) e o lote pago de
teste, que só roda com --autorizado e para antes de passar do teto de caracteres informado.

Uso (no ambiente do backend, que tem httpx):
  python elevenlabs.py conta <integrations.json> .saida/elevenlabs
  python elevenlabs.py historico <integrations.json> .saida/elevenlabs <history_item_id>...
  python elevenlabs.py lote <integrations.json> .saida/elevenlabs roteiro.txt --rota tts|dialogo --autorizado --teto 1500
  python elevenlabs.py recuperar <integrations.json> .saida/elevenlabs --rota tts|dialogo

A chave fica no integrations.json local do MyCut e nunca é gravada nas saídas.
"""
import argparse
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx

BASE = 'https://api.elevenlabs.io'


def cliente(integracoes):
    config = json.loads(Path(integracoes).read_text(encoding='utf-8'))['elevenlabs']
    http = httpx.Client(base_url=BASE, timeout=180, headers={'xi-api-key': config['api_key']})
    return http, {k: v for k, v in config.items() if k != 'api_key'}


def gravar(pasta, nome, dados):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')


def resumo_alinhamento(valor):
    if not isinstance(valor, dict):
        return None
    return {'caracteres': len(valor.get('characters') or []), 'texto': ''.join(valor.get('characters') or [])[:120]}


def consultar(http, caminho, **kwargs):
    """Uma consulta que pode ser recusada pelas permissões da chave: guarda o status e o motivo, não o corpo todo."""
    resposta = http.get(caminho, **kwargs)
    if resposta.is_error:
        try:
            motivo = resposta.json().get('detail')
        except ValueError:
            motivo = None
        return None, {'status': resposta.status_code, 'motivo': motivo}
    return resposta.json(), {'status': resposta.status_code}


def conta(http, config, pasta):
    """Sem custo: modelos e capacidades, uso da assinatura e as últimas gerações com ou sem alinhamento."""
    modelos, st_modelos = consultar(http, '/v1/models')
    assinatura, st_assinatura = consultar(http, '/v1/user/subscription')
    historico, st_historico = consultar(http, '/v1/history', params={'page_size': 100})
    modelos, assinatura, historico = modelos or [], assinatura or {}, historico or {}
    itens = []
    for item in historico.get('history', []):
        itens.append({k: item.get(k) for k in ('history_item_id', 'request_id', 'date_unix', 'model_id', 'voice_id',
                                                'voice_name', 'character_count_change_from',
                                                'character_count_change_to', 'source', 'state', 'content_type')}
                     | {'caracteres_texto': len(item.get('text') or ''),
                        'tem_alinhamentos_na_lista': bool(item.get('alignments'))})
    gravar(pasta, 'conta.json', {
        'config_local': config,
        'modelos': [{k: m.get(k) for k in ('model_id', 'name', 'can_do_text_to_speech', 'maximum_text_length_per_request',
                                          'token_cost_factor', 'model_rates', 'serves_pro_voices')}
                    | {'portugues': any(l.get('language_id') == 'pt' for l in m.get('languages') or [])}
                    for m in modelos],
        'assinatura': {k: assinatura.get(k) for k in ('tier', 'character_count', 'character_limit',
                                                     'next_character_count_reset_unix', 'status', 'currency')},
        'historico': itens,
        'status': {'modelos': st_modelos, 'assinatura': st_assinatura, 'historico': st_historico}})
    print(st_modelos, st_assinatura, st_historico)
    print(f'{len(modelos)} modelos, {len(itens)} itens no histórico; uso {assinatura.get("character_count")}'
          f'/{assinatura.get("character_limit")}')


def historico(http, pasta, ids):
    """Sem custo: um item do histórico com seus alinhamentos, e o áudio guardado (recuperação sem nova síntese)."""
    for item_id in ids:
        item = http.get(f'/v1/history/{item_id}').raise_for_status().json()
        audio = http.get(f'/v1/history/{item_id}/audio')
        alinhamentos = item.get('alignments') or {}
        destino = pasta / 'historico' / item_id
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'audio.mp3').write_bytes(audio.content)
        gravar(destino, 'item.json', item)
        print(item_id, item.get('model_id'), 'áudio', audio.status_code, len(audio.content), 'bytes',
              'alinhamento', resumo_alinhamento(alinhamentos.get('alignment')) is not None,
              'normalizado', resumo_alinhamento(alinhamentos.get('normalized_alignment')) is not None)


CABECALHOS = ('request-id', 'character-cost', 'x-trace-id', 'history-item-id', 'x-character-count')


def corpo(rota, config, trechos, n, ids):
    """O pedido do trecho n com o contexto que a rota aceita: no TTS, os últimos três request ids anteriores (que
    tomam o lugar do previous_text) e o texto seguinte; no diálogo, até 100 caracteres de cada lado."""
    texto, anterior = trechos[n], ids[-3:]
    seguinte = trechos[n + 1] if n + 1 < len(trechos) else None
    if rota == 'tts':
        dados = {'text': texto, 'model_id': config['model_id'],
                 'voice_settings': {k: config[k] for k in ('stability', 'similarity_boost', 'speed')}}
        if anterior:
            dados['previous_request_ids'] = anterior
        elif n:
            dados['previous_text'] = trechos[n - 1]
        if seguinte:
            dados['next_text'] = seguinte
        return f'/v1/text-to-speech/{config["voice_id"]}/with-timestamps', dados
    # O diálogo só aceita estabilidade nas configurações da voz.
    dados = {'inputs': [{'text': texto, 'voice_id': config['voice_id']}], 'model_id': config['model_id'],
             'settings': {'stability': config['stability']}}
    if anterior:
        dados['previous_request_ids'] = anterior
    elif n:
        dados['previous_text'] = trechos[n - 1][-100:]
    if seguinte:
        dados['future_text'] = seguinte[:100]
    return '/v1/text-to-dialogue/with-timestamps', dados


def lote(http, config, pasta, roteiro, rota, teto, simular):
    """O lote pago: cada trecho registrado antes do envio (Q31), parando antes de passar do teto de caracteres;
    guarda áudio, alinhamentos, cabeçalhos de custo e identificação. Sem nova tentativa automática."""
    trechos = [p.strip() for p in Path(roteiro).read_text(encoding='utf-8').split('\n\n') if p.strip()]
    # A simulação grava à parte, para não sobrescrever o registro de um lote pago já enviado.
    destino = pasta / (f'lote-{rota}-simulado' if simular else f'lote-{rota}')
    ids, enviados, creditos = [], 0, 0.0
    destino.mkdir(parents=True, exist_ok=True)
    for n, texto in enumerate(trechos):
        if enviados + len(texto) > teto:
            print(f'parado antes do trecho {n + 1}: passaria do teto de {teto} caracteres')
            break
        caminho, dados = corpo(rota, config, trechos, n, ids)
        if simular:
            print(caminho, json.dumps(dados, ensure_ascii=False)[:400])
            ids.append(f'simulado-{n}')
            enviados += len(texto)
            continue
        pedido = {'trecho': n + 1, 'rota': caminho.split('/{')[0], 'corpo': dados, 'estado': 'enviando',
                  'enviado_em': time.time()}
        gravar(destino, f'pedido-{n + 1}.json', pedido)
        enviados += len(texto)
        resposta = http.post(caminho, params={'output_format': 'mp3_44100_128'}, json=dados)
        pedido['status'] = resposta.status_code
        pedido['cabecalhos'] = {k: resposta.headers.get(k) for k in CABECALHOS}
        pedido['nomes_dos_cabecalhos'] = sorted(resposta.headers.keys())
        if resposta.is_error:
            pedido['estado'], pedido['erro'] = 'recusado', resposta.text[:600]
            gravar(destino, f'pedido-{n + 1}.json', pedido)
            print(f'trecho {n + 1}: HTTP {resposta.status_code}; lote parado')
            break
        corpo_resposta = resposta.json()
        (destino / f'trecho-{n + 1}.mp3').write_bytes(base64.b64decode(corpo_resposta.pop('audio_base64')))
        pedido['estado'], pedido['resposta'] = 'concluido', corpo_resposta
        gravar(destino, f'pedido-{n + 1}.json', pedido)
        custo = pedido['cabecalhos']['character-cost']
        creditos += float(custo) if custo else 0.0
        if pedido['cabecalhos']['request-id']:
            ids.append(pedido['cabecalhos']['request-id'])
        alinhamento = corpo_resposta.get('alignment')
        print(f'trecho {n + 1}: {len(texto)} caracteres, custo {custo}, request-id {pedido["cabecalhos"]["request-id"]}, '
              f'alinhamento {"sim" if alinhamento else "não"}, '
              f'normalizado {"sim" if corpo_resposta.get("normalized_alignment") else "não"}, '
              f'original igual ao texto {bool(alinhamento) and "".join(alinhamento["characters"]) == texto}')
    gravar(destino, 'lote.json', {'rota': rota, 'modelo': config['model_id'], 'teto': teto,
                                  'caracteres_enviados': enviados, 'creditos_cobrados': creditos,
                                  'request_ids': ids, 'simulado': simular})
    print(f'{enviados} caracteres enviados, {creditos} créditos cobrados pelos cabeçalhos')


def fins_absolutos(alinhamento):
    """No histórico, character_end_times_seconds traz a duração de cada caractere, não o instante do fim."""
    if not alinhamento:
        return alinhamento
    fins = [round(i + d, 6) for i, d in zip(alinhamento['character_start_times_seconds'],
                                            alinhamento['character_end_times_seconds'], strict=True)]
    return {**alinhamento, 'character_end_times_seconds': fins}


def mesmos_tempos(a, b):
    chaves = ('character_start_times_seconds', 'character_end_times_seconds')
    return bool(a and b) and a['characters'] == b['characters'] and all(len(a[k]) == len(b[k]) for k in chaves) and all(
        abs(x - y) < 1e-6 for k in chaves for x, y in zip(a[k], b[k], strict=True))


def pcm(conteudo):
    return subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', 'pipe:0', '-f', 's16le', '-'], input=conteudo,
                          capture_output=True, check=True).stdout


def recuperar(http, pasta, rota):
    """Sem custo: acha no histórico os itens do lote pelos request ids e compara áudio (decodificado; o contêiner
    MP3 muda) e alinhamento recuperados com os recebidos na hora."""
    destino = pasta / f'lote-{rota}'
    resumo = json.loads((destino / 'lote.json').read_text(encoding='utf-8'))
    lista, status = consultar(http, '/v1/history', params={'page_size': 100})
    if lista is None:
        print('histórico indisponível', status)
        return
    por_request = {i.get('request_id'): i for i in lista.get('history', [])}
    for n, request_id in enumerate(resumo['request_ids'], 1):
        item = por_request.get(request_id)
        if not item:
            print(f'trecho {n}: request id {request_id} não encontrado no histórico')
            continue
        completo, _ = consultar(http, f'/v1/history/{item["history_item_id"]}')
        audio = http.get(f'/v1/history/{item["history_item_id"]}/audio')
        original = json.loads((destino / f'pedido-{n}.json').read_text(encoding='utf-8'))['resposta']
        recuperado = (completo or {}).get('alignments') or {}
        (destino / f'historico-{n}.mp3').write_bytes(audio.content)
        gravar(destino, f'historico-{n}.json', completo)
        print(f'trecho {n}: item {item["history_item_id"]}, áudio decodificado igual '
              f'{pcm(audio.content) == pcm((destino / f"trecho-{n}.mp3").read_bytes())}, alinhamento '
              f'{"sim" if recuperado.get("alignment") else "não"}, igual ao recebido '
              f'{mesmos_tempos(fins_absolutos(recuperado.get("alignment")), original.get("alignment"))}, normalizado igual '
              f'{mesmos_tempos(fins_absolutos(recuperado.get("normalized_alignment")), original.get("normalized_alignment"))}, '
              f'consumo {item.get("character_count_change_from")}→{item.get("character_count_change_to")}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('acao', choices=['conta', 'historico', 'lote', 'recuperar'])
    ap.add_argument('integracoes')
    ap.add_argument('saida', type=Path)
    ap.add_argument('resto', nargs='*')
    ap.add_argument('--autorizado', action='store_true')
    ap.add_argument('--teto', type=int, default=0, help='caracteres: o lote para antes de passar disso')
    ap.add_argument('--rota', choices=['tts', 'dialogo'], default='tts')
    ap.add_argument('--simular', action='store_true', help='mostra os pedidos sem enviar')
    args = ap.parse_args()
    http, config = cliente(args.integracoes)
    if args.acao == 'conta':
        conta(http, config, args.saida)
    elif args.acao == 'historico':
        historico(http, args.saida, args.resto)
    elif args.acao == 'recuperar':
        recuperar(http, args.saida, args.rota)
    elif args.autorizado or args.simular:
        lote(http, config, args.saida, args.resto[0], args.rota, args.teto, args.simular)
    else:
        ap.error('o lote pago só roda com --autorizado (ou --simular, sem envio)')


if __name__ == '__main__':
    main()
