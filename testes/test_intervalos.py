import unittest

from pdf_leve.servicos.intervalos import agrupar_sequencias, interpretar_intervalos


class TestesInterpretarIntervalos(unittest.TestCase):

    def test_intervalos_e_paginas_soltas(self):
        paginas, erro = interpretar_intervalos("1-5, 8, 11-13", 20)
        self.assertIsNone(erro)
        self.assertEqual(paginas, [0, 1, 2, 3, 4, 7, 10, 11, 12])

    def test_intervalos_abertos(self):
        self.assertEqual(interpretar_intervalos("18-", 20)[0], [17, 18, 19])
        self.assertEqual(interpretar_intervalos("-3", 20)[0], [0, 1, 2])

    def test_mantem_ordem_digitada_sem_repetir(self):
        self.assertEqual(interpretar_intervalos("3–5; 2; 4", 20)[0], [2, 3, 4, 1])

    def test_erros(self):
        self.assertIn("invertido", interpretar_intervalos("5-3", 20)[1])
        self.assertIn("1 a 20", interpretar_intervalos("0", 20)[1])
        self.assertIn("1 a 20", interpretar_intervalos("1-50", 20)[1])
        self.assertIn("inválido", interpretar_intervalos("abc", 20)[1])
        self.assertEqual(interpretar_intervalos("  ", 20), ([], "Informe as páginas"))


class TestesAgruparSequencias(unittest.TestCase):

    def test_agrupa_paginas_consecutivas(self):
        self.assertEqual(agrupar_sequencias([0, 1, 2, 7, 10, 11]), [(0, 2), (7, 7), (10, 11)])

    def test_preserva_ordem_fora_de_sequencia(self):
        self.assertEqual(agrupar_sequencias([3, 1, 2]), [(3, 3), (1, 2)])


if __name__ == "__main__":
    unittest.main()
