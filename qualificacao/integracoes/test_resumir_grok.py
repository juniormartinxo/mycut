import json
import unittest

import resumir_grok

# Eventos reduzidos das rodadas gravadas em 17/10/2026 (caminhos trocados por neutros).
CHAMADA = {'type': 'tool_call', 'toolCallId': 'call-1', 'toolName': 'reference_to_video', 'status': 'pending',
           'rawInput': {'prompt': 'A small paper boat sails', 'aspect_ratio': '16:9',
                        'first_frame': '/tmp/base.png', 'duration': 6, 'resolution_name': '480p'}}
FIM = {'type': 'end', 'stopReason': 'end_turn', 'sessionId': 'sessao-1', 'requestId': 'turno-1',
       'num_turns': 2, 'total_cost_usd': 0.01636284}


def ndjson(*eventos):
    return [json.dumps(evento) for evento in eventos]


class ResumirGrokTest(unittest.TestCase):
    def test_rodada_com_um_clipe_gerado(self):
        linhas = ndjson(
            {'type': 'available_commands', 'tools': ['reference_to_video']},
            CHAMADA,
            {'type': 'tool_call_update', 'toolCallId': 'call-1', 'status': None, 'rawOutput': None},
            {'type': 'tool_call_update', 'toolCallId': 'call-1', 'status': 'completed',
             'rawOutput': {'type': 'ReferenceToVideo', 'path': '/home/autor/.grok/sessions/x/sessao-1/videos/1.mp4',
                           'filename': '1.mp4', 'session_folder': 'videos'}},
            {'type': 'text', 'data': 'Saved file: videos/1.mp4'},
            FIM,
        )

        self.assertEqual(resumir_grok.resumir(linhas), {
            'sessao': 'sessao-1',
            'turno': 'turno-1',
            'custo_texto_usd': 0.01636284,
            'chamadas': [{'id': 'call-1', 'ferramenta': 'reference_to_video', 'argumentos': CHAMADA['rawInput'],
                          'status': 'completed',
                          'arquivo': '/home/autor/.grok/sessions/x/sessao-1/videos/1.mp4', 'erro': None}],
        })

    def test_chamada_recusada_pelo_provedor_guarda_o_motivo(self):
        motivo = 'Video generation tools are unavailable under zero data retention (ZDR).'
        linhas = ndjson(
            CHAMADA,
            {'type': 'tool_call_update', 'toolCallId': 'call-1', 'status': 'failed',
             'rawOutput': {'error': 'tool_execution_failed', 'message': motivo}},
            FIM,
        )

        chamada, = resumir_grok.resumir(linhas)['chamadas']
        self.assertEqual((chamada['status'], chamada['arquivo'], chamada['erro']), ('failed', None, motivo))


if __name__ == '__main__':
    unittest.main()
