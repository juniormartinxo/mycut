import unittest

import ponte_windows


class AvaliarTest(unittest.TestCase):
    def test_notificacoes_liberadas_para_o_mycut(self):
        self.assertEqual(ponte_windows.avaliar({'setting': 'Enabled', 'toastsGlobais': 1}), 'liberada')

    def test_bloqueios_informados_pelo_windows(self):
        casos = {
            'DisabledForApplication': 'bloqueada_no_app',
            'DisabledForUser': 'bloqueada_pelo_usuario',
            'DisabledByGroupPolicy': 'bloqueada_por_politica',
            'DisabledByManifest': 'bloqueada_pelo_manifesto',
        }
        for setting, condicao in casos.items():
            with self.subTest(setting=setting):
                self.assertEqual(ponte_windows.avaliar({'setting': setting, 'toastsGlobais': 1}), condicao)

    def test_app_sem_toast_anterior_ainda_nao_tem_estado(self):
        # O Windows só conhece o AUMID depois do primeiro toast (0x80070490).
        self.assertEqual(ponte_windows.avaliar({'setting': None, 'toastsGlobais': 1}), 'desconhecida')

    def test_notificacoes_desligadas_para_todos_os_apps_prevalecem(self):
        self.assertEqual(ponte_windows.avaliar({'setting': 'Enabled', 'toastsGlobais': 0}), 'desligada_para_todos')


class PowerShellFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.pedidos = []

    def __call__(self, acao, pedido):
        self.pedidos.append((acao, pedido))
        return self.resposta


class NotificarTest(unittest.TestCase):
    def test_toast_entregue_na_central_com_texto_escapado(self):
        powershell = PowerShellFalso({'setting': 'Enabled', 'toastsGlobais': 1, 'historico': ['pend-7']})
        resultado = ponte_windows.notificar('Produção <A & B>', 'Teto "Grok" atingido', 'pend-7',
                                            executar=powershell)

        self.assertEqual(resultado, {'entregue': True, 'condicao': 'liberada'})
        acao, pedido = powershell.pedidos[0]
        self.assertEqual(acao, 'enviar')
        self.assertEqual(pedido['aumid'], 'MyCut')
        self.assertEqual(pedido['tag'], 'pend-7')
        self.assertIn('<text>Produção &lt;A &amp; B&gt;</text>', pedido['xml'])
        self.assertIn('<text>Teto "Grok" atingido</text>', pedido['xml'])

    def test_toast_bloqueado_nao_chega_a_central(self):
        # Show() não falha quando o app está bloqueado: o toast só não aparece no histórico.
        powershell = PowerShellFalso({'setting': 'DisabledForApplication', 'toastsGlobais': 1, 'historico': []})
        resultado = ponte_windows.notificar('MyCut', 'Pendência nova', 'pend-8', executar=powershell)

        self.assertEqual(resultado, {'entregue': False, 'condicao': 'bloqueada_no_app'})


if __name__ == '__main__':
    unittest.main()
