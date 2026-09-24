import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path

import fitz

from pdf_leve.servicos.renderizacao import processo_renderizador


class TestesProcessoRenderizador(unittest.TestCase):
    """Roda o laço do processo auxiliar numa thread, conversando por um Pipe como no programa."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = str(Path(self.pasta.name) / "teste.pdf")
        documento = fitz.open()
        documento.new_page(width=200, height=100).insert_text((20, 50), "Olá")
        documento.save(self.caminho)
        documento.close()
        self.local, remota = multiprocessing.Pipe()
        self.laco = threading.Thread(target=processo_renderizador, args=(remota,), daemon=True)
        self.laco.start()

    def tearDown(self):
        self.local.send(None)
        self.laco.join(5)
        self.pasta.cleanup()

    def receber(self):
        self.assertTrue(self.local.poll(10), "o processo auxiliar não respondeu")
        return self.local.recv()

    def test_renderiza_gira_e_fecha(self):
        self.local.send(("abrir", 1, self.caminho, None))
        self.local.send(("renderizar", (1, 0, 1000, 0), 0, 1.0))
        tipo, chave, largura, altura, amostras = self.receber()
        self.assertEqual((tipo, chave, largura, altura), ("imagem", (1, 0, 1000, 0), 200, 100))
        self.assertEqual(len(amostras), 200 * 100 * 3)

        self.local.send(("girar", 1, 0, 90))
        self.local.send(("renderizar", (1, 0, 1000, 1), 0, 1.0))
        _, _, largura, altura, _ = self.receber()
        self.assertEqual((largura, altura), (100, 200))

        self.local.send(("fechar", 1))
        self.assertEqual(self.receber(), ("fechado", 1))

    def test_erro_em_documento_inexistente(self):
        self.local.send(("renderizar", (9, 0, 1000, 0), 0, 1.0))
        self.assertEqual(self.receber()[0], "erro")


if __name__ == "__main__":
    unittest.main()
