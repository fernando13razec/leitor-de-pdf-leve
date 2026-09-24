import unittest

import pymupdf

from pdf_leve.servicos.texto import linha_da_palavra, linhas_visuais, palavra_mais_proxima, texto_das_palavras


def palavra(x0, y0, x1, y1, texto, linha):
    return (x0, y0, x1, y1, texto, 0, linha, 0)


# Texto justificado de OCR: cada palavra da 1ª linha vem numa “linha” própria do PDF.
PALAVRAS = [
    palavra(10, 10, 50, 20, "Conforme", 0),
    palavra(60, 10, 80, 20, "já", 1),
    palavra(90, 10, 140, 20, "aduzido", 2),
    palavra(10, 30, 70, 40, "Embargada", 3),
    palavra(80, 30, 110, 40, "haver", 3),
]


class TestesTexto(unittest.TestCase):

    def test_agrupa_pela_posicao_visual_e_nao_pela_linha_do_pdf(self):
        linhas = linhas_visuais(PALAVRAS)
        self.assertEqual([[p[4] for p in linha] for linha in linhas],
                         [["Conforme", "já", "aduzido"], ["Embargada", "haver"]])

    def test_texto_das_palavras(self):
        self.assertEqual(texto_das_palavras(PALAVRAS), "Conforme já aduzido\nEmbargada haver")

    def test_palavra_sob_o_ponto_e_mais_proxima(self):
        self.assertEqual(palavra_mais_proxima(PALAVRAS, pymupdf.Point(65, 15), exata=True), 1)
        self.assertIsNone(palavra_mais_proxima(PALAVRAS, pymupdf.Point(55, 15), exata=True))
        self.assertEqual(palavra_mais_proxima(PALAVRAS, pymupdf.Point(200, 35)), 4)

    def test_linha_da_palavra(self):
        self.assertEqual(linha_da_palavra(PALAVRAS, 1), (0, 2))
        self.assertEqual(linha_da_palavra(PALAVRAS, 4), (3, 4))


if __name__ == "__main__":
    unittest.main()
