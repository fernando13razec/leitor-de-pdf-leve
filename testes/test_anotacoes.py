import unittest

import fitz

from pdf_leve.servicos.anotacoes import (
    aplicar_anotacao, criar_anotacao, encaixar_caixa_texto, hex_para_rgb, ler_propriedades,
    medir_caixa_texto, retangulo_exibido, rgb_para_hex,
)


class TestesAnotacoes(unittest.TestCase):

    def setUp(self):
        self.documento = fitz.open()
        self.documento.new_page(width=595, height=842)
        girada = self.documento.new_page(width=595, height=842)
        girada.set_rotation(90)

    def tearDown(self):
        self.documento.close()

    def test_conversao_de_cores(self):
        self.assertEqual(rgb_para_hex(hex_para_rgb("#1565c0")), "#1565c0")

    def test_caixa_cresce_com_texto_e_linhas(self):
        largura_1, altura_1 = medir_caixa_texto("ação", 12)
        largura_2, altura_2 = medir_caixa_texto("ação, coração e não\nsegunda linha", 12)
        self.assertGreater(largura_2, largura_1)
        self.assertGreater(altura_2, altura_1)

    def test_caixa_fica_dentro_da_pagina(self):
        pagina = self.documento[0]
        retangulo = encaixar_caixa_texto(pagina, 590, 840, "texto longo demais para a borda", 14)
        self.assertTrue(pagina.rect.contains(retangulo))

    def test_criar_ler_e_alterar_inclusive_em_pagina_girada(self):
        for indice in (0, 1):
            pagina = self.documento[indice]
            retangulo = encaixar_caixa_texto(pagina, 50, 50, "Prazo: sexta-feira", 14)
            anotacao = criar_anotacao(pagina, retangulo, "Prazo: sexta-feira", "#d32f2f", 14)
            self.assertTrue(retangulo_exibido(pagina, anotacao).contains(fitz.Point(60, 60)))
            self.assertEqual(ler_propriedades(self.documento, anotacao), ("Prazo: sexta-feira", "#d32f2f", 14))

            novo = encaixar_caixa_texto(pagina, 100, 100, "Editado", 20)
            aplicar_anotacao(pagina, anotacao, "Editado", "#2e7d32", 20, novo)
            anotacao = pagina.load_annot(anotacao.xref)
            self.assertEqual(ler_propriedades(self.documento, anotacao), ("Editado", "#2e7d32", 20))
            self.assertAlmostEqual(retangulo_exibido(pagina, anotacao).x0, 100, places=2)


if __name__ == "__main__":
    unittest.main()
