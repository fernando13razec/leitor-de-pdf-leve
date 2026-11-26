"""Testes da roda do mouse e da rolagem de alta resolução (touchpads e mouses de rolagem suave)."""

import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

from pdf_leve.interface import utilidades
from pdf_leve.interface.utilidades import ligar_roda, passos_da_roda, separar_deltas_precisos


class TesteSepararDeltasPrecisos(unittest.TestCase):
    """Valores de %D montados como o Tk 9 faz no Windows: Y nos 16 bits baixos, X nos 16 altos."""

    def test_vertical(self):
        self.assertEqual(separar_deltas_precisos(40), (0, 40))
        self.assertEqual(separar_deltas_precisos(-40 & 0xFFFF), (0, -40))
        self.assertEqual(separar_deltas_precisos(-120 & 0xFFFF), (0, -120))

    def test_horizontal(self):
        self.assertEqual(separar_deltas_precisos(-(40 << 16)), (-40, 0))
        self.assertEqual(separar_deltas_precisos(-(40 << 16) & 0xFFFFFFFF), (-40, 0))  # sem sinal
        self.assertEqual(separar_deltas_precisos(25 << 16), (25, 0))

    def test_os_dois_eixos(self):
        self.assertEqual(separar_deltas_precisos((3 << 16) | (-5 & 0xFFFF)), (3, -5))
        self.assertEqual(separar_deltas_precisos((-3 << 16) | (-5 & 0xFFFF)), (-3, -5))


class TestePassosDaRoda(unittest.TestCase):

    def test_clique_comum(self):
        self.assertEqual(passos_da_roda(120, 40), -3)  # para cima
        self.assertEqual(passos_da_roda(-120, 40), 3)  # para baixo
        self.assertEqual(passos_da_roda(-120, 120), 1)

    def test_deltas_pequenos_rolam_ao_menos_um_passo(self):
        self.assertEqual(passos_da_roda(10, 40), -1)
        self.assertEqual(passos_da_roda(-10, 40), 1)
        self.assertEqual(passos_da_roda(-40, 120), 1)

    def test_delta_zero_nao_rola(self):
        self.assertEqual(passos_da_roda(0, 40), 0)


class WidgetFalso:

    def __init__(self):
        self.ligacoes = {}

    def bind(self, sequencia, funcao):
        self.ligacoes[sequencia] = funcao


class TesteLigarRoda(unittest.TestCase):

    def ligar(self, rolagem_precisa, modificador=""):
        widget, chamadas = WidgetFalso(), []
        with mock.patch.object(utilidades, "ROLAGEM_PRECISA_DISPONIVEL", rolagem_precisa):
            ligar_roda(widget, lambda evento, delta_x, delta_y: chamadas.append((delta_x, delta_y)),
                       modificador)
        return widget, chamadas

    def test_tk_8_6_so_tem_mousewheel(self):
        widget, chamadas = self.ligar(False)
        self.assertEqual(list(widget.ligacoes), ["<MouseWheel>"])
        widget.ligacoes["<MouseWheel>"](SimpleNamespace(delta=-40))
        self.assertEqual(chamadas, [(0, -40)])

    def test_tk_9_liga_tambem_touchpadscroll(self):
        widget, chamadas = self.ligar(True, "Control")
        self.assertEqual(sorted(widget.ligacoes), ["<Control-MouseWheel>", "<Control-TouchpadScroll>"])
        widget.ligacoes["<Control-MouseWheel>"](SimpleNamespace(delta=-120))
        widget.ligacoes["<Control-TouchpadScroll>"](SimpleNamespace(delta=-40 & 0xFFFF))
        widget.ligacoes["<Control-TouchpadScroll>"](SimpleNamespace(delta=-(40 << 16)))
        self.assertEqual(chamadas, [(0, -120), (0, -40), (-40, 0)])

    def test_sequencias_existem_no_tk_em_uso(self):
        """Com o Tk de verdade (no Tk 9, o da CI): ligar não dá erro e liga os dois eventos."""
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk indisponível")
        raiz.withdraw()
        try:
            tela = tk.Canvas(raiz)
            for modificador in ("", "Shift", "Control"):
                ligar_roda(tela, lambda evento, delta_x, delta_y: None, modificador)
            ligadas = " ".join(tela.bind())
            self.assertEqual(ligadas.count("MouseWheel"), 3)
            self.assertEqual(ligadas.count("TouchpadScroll"), 3 if tk.TkVersion >= 9.0 else 0)
        finally:
            raiz.destroy()


if __name__ == "__main__":
    unittest.main()
