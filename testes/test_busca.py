import unittest

import pymupdf

from pdf_leve.servicos.busca import buscar_termos_na_pagina, combinar_resultados, separar_termos


class TestesBusca(unittest.TestCase):

    def test_separar_termos(self):
        self.assertEqual(separar_termos("multa;  prazo   de entrega ;; Multa; "), ["multa", "prazo de entrega"])
        self.assertEqual(separar_termos(" ; "), [])
        self.assertEqual(separar_termos("rescisão"), ["rescisão"])

    def test_combinar_em_ordem_de_leitura(self):
        # Termo 0 na 2ª linha; termo 1 na 1ª linha, um pouco mais alto (outra fonte), e na 2ª à esquerda.
        termo0 = [pymupdf.Rect(100, 30, 140, 40)]
        termo1 = [pymupdf.Rect(80, 9, 120, 21), pymupdf.Rect(10, 30, 50, 40), pymupdf.Rect(10, 10, 50, 20)]
        combinados = combinar_resultados([termo0, termo1])
        self.assertEqual([(tuple(r), termo) for r, termo in combinados], [
            ((10, 10, 50, 20), 1), ((80, 9, 120, 21), 1), ((10, 30, 50, 40), 1), ((100, 30, 140, 40), 0),
        ])

    def test_trecho_achado_por_dois_termos_fica_so_com_o_maior(self):
        multa = [pymupdf.Rect(10, 10, 50, 20)]
        multas = [pymupdf.Rect(10, 10, 58, 20)]
        self.assertEqual(combinar_resultados([multa, multas]), [(multas[0], 1)])

    def test_buscar_termos_na_pagina(self):
        documento = pymupdf.open()
        pagina = documento.new_page()
        pagina.insert_text((72, 72), "A multa vence no prazo de entrega.")
        pagina.insert_text((72, 100), "Sem multa em caso de rescisão.")
        ocorrencias = buscar_termos_na_pagina(pagina, ["multa", "prazo de entrega", "inexistente"])
        self.assertEqual([termo for _, termo in ocorrencias], [0, 1, 0])
        documento.close()


if __name__ == "__main__":
    unittest.main()
