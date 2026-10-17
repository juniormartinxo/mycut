import unittest

from medida import comparar


def palavra(texto, inicio, fim, confianca=None):
    return {'palavra': texto, 'inicio': inicio, 'fim': fim, **({} if confianca is None else {'confianca': confianca})}


REFERENCIA = [palavra('a', 0.0, 0.2), palavra('b', 0.3, 0.6), palavra('c', 0.7, 1.0), palavra('d', 1.1, 1.5)]
MEDIDO = [palavra('a', 0.0, 0.25, 0.9), palavra('b', 0.35, 0.6, 0.9), palavra('c', 0.82, 1.0, 0.3),
          palavra('d', 1.4, 1.5, 0.2)]


class Comparar(unittest.TestCase):
    def test_desvio_de_inicio_por_palavra_em_ms(self):
        resultado = comparar(REFERENCIA, MEDIDO)
        self.assertEqual(resultado['inicio_ms'], {'mediana': 85, 'p90': 300, 'p95': 300, 'max': 300})
        self.assertEqual(resultado['fim_ms']['max'], 50)

    def test_fracao_de_palavras_dentro_de_100_ms_no_inicio(self):
        self.assertEqual(comparar(REFERENCIA, MEDIDO)['dentro_100ms'], 0.5)

    def test_confianca_baixa_separa_as_palavras_com_mais_erro(self):
        self.assertEqual(comparar(REFERENCIA, MEDIDO, limiar=0.5)['por_confianca'], {
            'alta': {'palavras': 2, 'dentro_100ms': 1.0}, 'baixa': {'palavras': 2, 'dentro_100ms': 0.0}})

    def test_alinhamentos_de_textos_diferentes_nao_sao_comparados(self):
        with self.assertRaises(ValueError):
            comparar(REFERENCIA, MEDIDO[:3])


if __name__ == '__main__':
    unittest.main()
