import unittest

from texto import casar_roteiro


def falada(palavra, inicio, fim, confianca):
    return {'palavra': palavra, 'inicio': inicio, 'fim': fim, 'confianca': confianca}


RECONHECIDAS = [falada('O', 0.0, 0.2, 0.9), falada('corte', 0.2, 0.6, 0.95), falada('muda', 1.0, 1.4, 0.9),
                falada('tudo.', 1.4, 1.8, 0.8), falada('a', 2.5, 2.6, 0.7), falada('fuzão', 2.6, 3.0, 0.4),
                falada('mistura', 3.0, 3.5, 0.9), falada('né', 3.5, 3.7, 0.3)]


class CasarRoteiro(unittest.TestCase):
    def setUp(self):
        self.palavras = casar_roteiro('O corte seco muda tudo.\n\nA fusão mistura.', RECONHECIDAS, duracao=4.0)

    def resumo(self, i):
        p = self.palavras[i]
        return p['palavra'], p['inicio'], p['fim'], p['confianca'], p['mapeamento']

    def test_cada_palavra_do_roteiro_recebe_tempos_mesmo_com_fala_extra_reconhecida(self):
        self.assertEqual([p['palavra'] for p in self.palavras],
                         ['O', 'corte', 'seco', 'muda', 'tudo.', 'A', 'fusão', 'mistura.'])

    def test_palavra_reconhecida_igual_ao_roteiro_traz_tempos_e_confianca(self):
        self.assertEqual(self.resumo(4), ('tudo.', 1.4, 1.8, 0.8, 'exato'))

    def test_palavra_nao_reconhecida_ocupa_o_vao_entre_as_vizinhas_sem_confianca(self):
        self.assertEqual(self.resumo(2), ('seco', 0.6, 1.0, 0.0, 'interpolado'))

    def test_palavra_reconhecida_com_outra_grafia_e_aproximada(self):
        self.assertEqual(self.resumo(6), ('fusão', 2.6, 3.0, 0.4, 'aproximado'))


if __name__ == '__main__':
    unittest.main()
