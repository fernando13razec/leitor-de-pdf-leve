import unittest

import pymupdf

from pdf_leve.configuracao.constantes import DPI_MAXIMO_IMPRESSAO
from pdf_leve.servicos.impressao import (
    MedidasPapel, calcular_encaixe, imprimir_documento, paginas_selecionadas, rgb_para_dib,
)

# A4 a 600 DPI, com margens não imprimíveis de 100 px à esquerda e 50 px no topo
A4_EM_PE = MedidasPapel(4960, 7016, 100, 50, 4760, 6916, 600, 600)
A4_DEITADO = MedidasPapel(7016, 4960, 50, 100, 6916, 4760, 600, 600)


class DispositivoFalso:

    def __init__(self, falhar_na_pagina=None):
        self.chamadas = []
        self.falhar_na_pagina = falhar_na_pagina

    def medidas(self):
        return (4960, 7016, 100, 50, 4760, 6916, 600, 600)

    def iniciar_pagina(self):
        self.chamadas.append("iniciar")
        if len(self.paginas_desenhadas()) == self.falhar_na_pagina:
            raise OSError("papel atolado")

    def desenhar(self, dib, largura, altura, x, y, largura_destino, altura_destino):
        self.chamadas.append(("desenhar", largura, altura, largura_destino, altura_destino))
        passo = largura * 3 + (-largura * 3) % 4
        assert len(dib) == passo * altura

    def terminar_pagina(self):
        self.chamadas.append("terminar")

    def concluir(self):
        self.chamadas.append("concluir")

    def abortar(self):
        self.chamadas.append("abortar")

    def paginas_desenhadas(self):
        return [chamada for chamada in self.chamadas if chamada[0] == "desenhar"]


class TestesImpressao(unittest.TestCase):

    def setUp(self):
        self.documento = pymupdf.open()
        self.documento.new_page(width=100, height=200)
        self.documento.new_page(width=200, height=100)  # deitada
        self.documento.new_page(width=100, height=200)

    def tearDown(self):
        self.documento.close()

    def test_paginas_selecionadas(self):
        self.assertEqual(paginas_selecionadas(None, False, 4, 2), [0, 1, 2, 3])
        self.assertEqual(paginas_selecionadas(None, True, 4, 2), [2])
        self.assertEqual(paginas_selecionadas([(3, 4), (1, 1)], False, 4, 0), [2, 3, 0])
        self.assertEqual(paginas_selecionadas([(3, 9), (7, 8)], False, 4, 0), [2, 3])

    def test_pagina_do_tamanho_do_papel_cabe_na_area_imprimivel(self):
        encaixe = calcular_encaixe(595, 842, A4_EM_PE)  # A4 em pontos
        self.assertFalse(encaixe.girar)
        self.assertEqual(encaixe.largura, A4_EM_PE.largura_imprimivel)
        self.assertAlmostEqual(encaixe.largura / encaixe.altura, 595 / 842, places=3)
        # centralizada no papel físico (descontada a margem não imprimível)
        self.assertEqual(encaixe.x, (4960 - encaixe.largura) // 2 - 100)
        self.assertEqual(encaixe.y, (7016 - encaixe.altura) // 2 - 50)
        self.assertLessEqual(encaixe.y + encaixe.altura, A4_EM_PE.altura_imprimivel)

    def test_pagina_pequena_nao_e_ampliada(self):
        encaixe = calcular_encaixe(72, 144, A4_EM_PE)  # 1 × 2 polegadas
        self.assertEqual((encaixe.largura, encaixe.altura), (600, 1200))
        self.assertEqual(encaixe.x, (4960 - 600) // 2 - 100)
        self.assertEqual(encaixe.y, (7016 - 1200) // 2 - 50)
        self.assertAlmostEqual(encaixe.escala, DPI_MAXIMO_IMPRESSAO / 72)

    def test_pagina_deitada_gira_em_papel_em_pe(self):
        encaixe = calcular_encaixe(842, 595, A4_EM_PE)
        self.assertTrue(encaixe.girar)
        self.assertGreater(encaixe.altura, encaixe.largura)
        self.assertFalse(calcular_encaixe(842, 595, A4_DEITADO).girar)
        self.assertTrue(calcular_encaixe(595, 842, A4_DEITADO).girar)

    def test_pagina_grande_e_reduzida(self):
        encaixe = calcular_encaixe(1190, 1684, A4_EM_PE)  # A2
        self.assertLessEqual(encaixe.largura, A4_EM_PE.largura_imprimivel)
        self.assertLessEqual(encaixe.altura, A4_EM_PE.altura_imprimivel)
        self.assertAlmostEqual(encaixe.largura / encaixe.altura, 1190 / 1684, places=2)

    def test_rgb_para_dib(self):
        for largura in (1, 2, 3, 4):
            amostras = bytes([10, 20, 30]) * largura * 2
            dib = rgb_para_dib(amostras, largura, 2)
            passo = largura * 3 + (-largura * 3) % 4
            self.assertEqual(len(dib), passo * 2)
            for linha in range(2):
                self.assertEqual(dib[linha * passo:linha * passo + 3], bytes([30, 20, 10]))
                self.assertEqual(dib[linha * passo + largura * 3:(linha + 1) * passo], bytes(passo - largura * 3))

    def test_imprime_paginas_na_ordem(self):
        dispositivo, progresso = DispositivoFalso(), []
        concluido = imprimir_documento(self.documento, [0, 1], dispositivo,
                                       lambda *args: progresso.append(args), lambda: False)
        self.assertTrue(concluido)
        self.assertEqual(progresso, [(1, 2), (2, 2)])
        self.assertEqual([c if isinstance(c, str) else c[0] for c in dispositivo.chamadas],
                         ["iniciar", "desenhar", "terminar"] * 2 + ["concluir"])
        # a página deitada é girada para o papel em pé: a imagem fica em pé
        _, largura, altura, _, _ = dispositivo.paginas_desenhadas()[1]
        self.assertGreater(altura, largura)

    def test_cancelamento_aborta(self):
        dispositivo = DispositivoFalso()
        respostas = iter([False, True])
        concluido = imprimir_documento(self.documento, [0, 1, 2], dispositivo, lambda *args: None,
                                       lambda: next(respostas))
        self.assertFalse(concluido)
        self.assertEqual(len(dispositivo.paginas_desenhadas()), 1)
        self.assertEqual(dispositivo.chamadas[-1], "abortar")

    def test_erro_aborta(self):
        dispositivo = DispositivoFalso(falhar_na_pagina=1)
        with self.assertRaises(OSError):
            imprimir_documento(self.documento, [0, 1, 2], dispositivo, lambda *args: None, lambda: False)
        self.assertEqual(dispositivo.chamadas[-1], "abortar")
        self.assertNotIn("concluir", dispositivo.chamadas)


if __name__ == "__main__":
    unittest.main()
