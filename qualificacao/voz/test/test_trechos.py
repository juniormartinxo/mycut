import unittest

from texto import trechos

ROTEIRO = (
    'Montar é escolher o que entra. Um corte seco muda de imagem sem aviso.\n\n'
    'Nos primeiros filmes, a câmera ficava parada. Com o tempo, os montadores descobriram o corte. '
    'Um rosto seguido de um prato parecia fome. O mesmo rosto seguido de uma criança parecia ternura.'
)


class Trechos(unittest.TestCase):
    def test_paragrafo_que_cabe_no_limite_e_um_trecho_inteiro(self):
        self.assertEqual(trechos(ROTEIRO, 400), [
            {'paragrafo': 0, 'texto': 'Montar é escolher o que entra. Um corte seco muda de imagem sem aviso.'},
            {'paragrafo': 1, 'texto': ROTEIRO.split('\n\n')[1]},
        ])

    def test_paragrafo_longo_e_dividido_entre_frases_sem_passar_do_limite(self):
        partes = [t['texto'] for t in trechos(ROTEIRO, 100) if t['paragrafo'] == 1]
        self.assertEqual(partes, [
            'Nos primeiros filmes, a câmera ficava parada. Com o tempo, os montadores descobriram o corte.',
            'Um rosto seguido de um prato parecia fome. O mesmo rosto seguido de uma criança parecia ternura.',
        ])

    def test_frase_maior_que_o_limite_fica_inteira(self):
        frase = 'Uma frase longa, com vírgulas, que não pode ser cortada no meio por nenhum motivo.'
        self.assertEqual(trechos(frase, 30), [{'paragrafo': 0, 'texto': frase}])


if __name__ == '__main__':
    unittest.main()
