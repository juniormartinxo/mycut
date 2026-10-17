import unittest

from texto import palavras_da_api


def alinhamento(texto, inicio=0.0, passo=0.1):
    """Um caractere a cada `passo` segundos, como a ElevenLabs devolve."""
    return {'characters': list(texto),
            'character_start_times_seconds': [round(inicio + i * passo, 3) for i in range(len(texto))],
            'character_end_times_seconds': [round(inicio + (i + 1) * passo, 3) for i in range(len(texto))]}


class PalavrasDaApi(unittest.TestCase):
    def test_alinhamento_do_texto_original_da_os_tempos_de_cada_palavra(self):
        palavras = palavras_da_api('Custa 25 reais.', alinhamento('Custa 25 reais.'), None)
        self.assertEqual([(p['palavra'], p['inicio'], p['fim'], p['mapeamento']) for p in palavras], [
            ('Custa', 0.0, 0.5, 'exato'), ('25', 0.6, 0.8, 'exato'), ('reais.', 0.9, 1.5, 'exato')])

    def test_sem_o_original_numero_expandido_recebe_o_intervalo_das_palavras_faladas(self):
        normalizado = alinhamento('Custa vinte e cinco reais.')
        palavras = palavras_da_api('Custa 25 reais.', None, normalizado)
        self.assertEqual([(p['palavra'], p['inicio'], p['fim'], p['mapeamento']) for p in palavras], [
            ('Custa', 0.0, 0.5, 'exato'), ('25', 0.6, 1.9, 'aproximado'), ('reais.', 2.0, 2.6, 'exato')])

    def test_original_que_nao_corresponde_ao_texto_enviado_cede_lugar_ao_normalizado(self):
        palavras = palavras_da_api('Custa 25 reais.', alinhamento('Custa 25 reais'), alinhamento('Custa vinte e cinco reais.'))
        self.assertEqual(palavras[1]['mapeamento'], 'aproximado')

    def test_sem_nenhum_alinhamento_a_ausencia_e_informada(self):
        with self.assertRaisesRegex(ValueError, 'alinhamento'):
            palavras_da_api('Custa 25 reais.', None, None)


if __name__ == '__main__':
    unittest.main()
