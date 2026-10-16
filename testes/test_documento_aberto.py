import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import pymupdf

from pdf_leve.interface.documento_aberto import DocumentoAberto


class RenderizadoresFalsos:

    def __init__(self):
        self.mensagens = []

    def enviar_a_todos(self, mensagem):
        self.mensagens.append(mensagem)

    def fechar_documento(self, id_documento):
        self.mensagens.append(("fechar", id_documento))


class AplicativoFalso:

    def __init__(self):
        self.renderizadores = RenderizadoresFalsos()
        self._ultimo_id = 0

    def proximo_id_documento(self):
        self._ultimo_id += 1
        return self._ultimo_id


class VistaFalsa:
    """Registra o que o documento pede às janelas que o exibem."""

    def __init__(self, visivel=True):
        self.fechada = False
        self.visivel = visivel
        self.chamadas = []

    def atualizar_titulo(self):
        self.chamadas.append("titulo")

    def agendar_renderizacao(self):
        self.chamadas.append("renderizar")

    def refazer_por_rotacao(self):
        self.chamadas.append("rotacao")

    def criar_ancora(self, x, y):
        return (0, 0.5, 0.5, x, y)

    def exibir(self, aberto, ancora):
        self.chamadas.append(("exibir", aberto.caminho, ancora))

    def posicionar_se_visivel(self, chave, imagem):
        return self.visivel


class TestesDocumentoAberto(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = str(Path(self.pasta.name) / "teste.pdf")
        documento = pymupdf.open()
        documento.new_page(width=200, height=100).insert_text((20, 50), "Olá")
        documento.new_page(width=200, height=100)
        documento.save(self.caminho)
        documento.close()
        self.aplicativo = AplicativoFalso()
        self.aberto = DocumentoAberto(self.aplicativo, pymupdf.open(self.caminho), self.caminho, None)
        self.vistas = [VistaFalsa(), VistaFalsa(visivel=False)]
        for vista in self.vistas:
            self.aberto.anexar(vista)

    def tearDown(self):
        if self.aberto.documento:
            self.aberto.documento.close()
        self.pasta.cleanup()

    def test_so_a_ultima_vista_fecha_o_documento(self):
        self.aberto.desanexar(self.vistas[0])
        self.assertIsNotNone(self.aberto.documento)
        self.assertNotIn(("descartar", 1), self.aplicativo.renderizadores.mensagens)
        self.assertIn("titulo", self.vistas[1].chamadas)  # o número da vista some do título

        self.aberto.desanexar(self.vistas[1])
        self.assertIsNone(self.aberto.documento)
        self.assertIn(("descartar", 1), self.aplicativo.renderizadores.mensagens)

    def test_alteracoes_sao_avisadas_a_todas_as_vistas(self):
        for vista in self.vistas:
            vista.chamadas.clear()
        self.aberto.paginas_alteradas(1)
        self.aberto.marcar_modificado()
        self.aberto.disposicao_alterada()
        self.assertEqual(self.aberto.versao_pagina, [0, 1])
        self.assertEqual(self.aberto.paginas_locais, {1})
        self.assertTrue(self.aberto.modificado)
        for vista in self.vistas:
            self.assertEqual(vista.chamadas, ["renderizar", "titulo", "rotacao"])

    def test_salvar_como_reexibe_em_todas_as_vistas(self):
        destino = str(Path(self.pasta.name) / "copia.pdf")
        self.aberto.marcar_modificado()
        self.aberto.salvar_como(destino)
        self.assertEqual(self.aberto.caminho, destino)
        self.assertFalse(self.aberto.modificado)
        self.assertEqual(self.aberto.id_documento, 2)  # novo id: imagens antigas são descartadas
        for vista in self.vistas:
            self.assertIn(("exibir", destino, (0, 0.5, 0.5, 0, 0)), vista.chamadas)

    def test_imagem_recebida_vai_ao_cache_uma_vez_e_a_todas_as_vistas(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk indisponível")
        raiz.withdraw()
        try:
            chave = (self.aberto.id_documento, 0, 1000, 0)
            atualizadas = self.aberto.receber_imagem(chave, 2, 1, b"\xff" * 6)
            self.assertEqual(atualizadas, [self.vistas[0]])  # só a vista em que a página está visível
            self.assertEqual(list(self.aberto.cache_imagens), [chave])
            self.assertEqual(self.aberto.receber_imagem((99, 0, 1000, 0), 2, 1, b"\xff" * 6), [])
        finally:
            self.aberto.cache_imagens.clear()
            raiz.destroy()


if __name__ == "__main__":
    unittest.main()
