import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path

import pymupdf

from pdf_leve.servicos.renderizacao import ConjuntoRenderizadores, processo_renderizador


class TestesProcessoRenderizador(unittest.TestCase):
    """Roda o laço do processo auxiliar numa thread, conversando por um Pipe como no programa."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = str(Path(self.pasta.name) / "teste.pdf")
        documento = pymupdf.open()
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


class DocumentoFalso:

    def __init__(self, id_documento, janelas):
        self.id_documento = id_documento
        self.em_renderizacao = set()
        self.janelas = janelas
        self.recebidas = []

    def receber_imagem(self, chave, largura, altura, amostras):
        self.recebidas.append(chave)
        return self.janelas


class AplicativoFalso:

    def __init__(self, documentos):
        self.documentos = {documento.id_documento: documento for documento in documentos}

    def documento_do_id(self, id_documento):
        return self.documentos.get(id_documento)


class TestesEntregaDasImagens(unittest.TestCase):
    """O resultado de um processo vai ao documento certo, que pode estar em várias janelas."""

    def test_imagem_vai_ao_documento_e_as_janelas_dele(self):
        documento = DocumentoFalso(1, ["janela 1", "janela 2"])
        outro = DocumentoFalso(2, ["janela 3"])
        conjunto = ConjuntoRenderizadores(AplicativoFalso([documento, outro]), 0)
        chave = (1, 0, 1000, 0)
        documento.em_renderizacao.add(chave)
        processo = [None, None, chave]
        atualizadas = set()
        conjunto._tratar_mensagem(processo, ("imagem", chave, 2, 1, b""), atualizadas)
        self.assertEqual(documento.recebidas, [chave])
        self.assertEqual(outro.recebidas, [])
        self.assertEqual(documento.em_renderizacao, set())
        self.assertEqual(atualizadas, {"janela 1", "janela 2"})
        self.assertIsNone(processo[2])

    def test_erro_ou_documento_fechado_so_libera_o_processo(self):
        documento = DocumentoFalso(1, ["janela 1"])
        conjunto = ConjuntoRenderizadores(AplicativoFalso([documento]), 0)
        documento.em_renderizacao.add((1, 0, 1000, 0))
        atualizadas = set()
        conjunto._tratar_mensagem([None, None, 1], ("erro", (1, 0, 1000, 0), "falhou"), atualizadas)
        conjunto._tratar_mensagem([None, None, 1], ("imagem", (7, 0, 1000, 0), 2, 1, b""), atualizadas)
        self.assertEqual(documento.em_renderizacao, set())
        self.assertEqual((documento.recebidas, atualizadas), ([], set()))


if __name__ == "__main__":
    unittest.main()
