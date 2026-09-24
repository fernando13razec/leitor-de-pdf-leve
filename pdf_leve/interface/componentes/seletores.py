"""Seletores de cor e de tamanho do texto das anotações."""

import tkinter as tk

from pdf_leve.configuracao.constantes import CORES_ANOTACAO, TAMANHO_FONTE_MAXIMO, TAMANHO_FONTE_MINIMO
from pdf_leve.configuracao.tema import COR_BARRA, COR_BORDA_CIRCULO, COR_PASSAR_MOUSE, COR_TEXTO, fontes


class SeletorCores(tk.Frame):
    """Linha de círculos de cor clicáveis; a cor escolhida ganha um anel."""

    def __init__(self, mestre, cor_atual, ao_escolher, fundo=COR_BARRA):
        super().__init__(mestre, bg=fundo)
        self.ao_escolher, self.circulos = ao_escolher, {}
        for cor in CORES_ANOTACAO.values():
            circulo = tk.Canvas(self, width=26, height=26, bg=fundo, highlightthickness=0, cursor="hand2")
            circulo.pack(side="left", padx=1)
            circulo.bind("<Button-1>", lambda e, cor=cor: self.ao_escolher(cor))
            self.circulos[cor] = circulo
        self.selecionar(cor_atual)

    def selecionar(self, cor_escolhida):
        for cor, circulo in self.circulos.items():
            circulo.delete("all")
            if cor.lower() == cor_escolhida.lower():
                circulo.create_oval(2, 2, 24, 24, outline=COR_TEXTO, width=2)
                circulo.create_oval(6, 6, 20, 20, fill=cor, outline="")
            else:
                circulo.create_oval(5, 5, 21, 21, fill=cor, outline=COR_BORDA_CIRCULO)


class SeletorTamanho(tk.Frame):
    """Controle “− 12 pt +”."""

    def __init__(self, mestre, valor, ao_mudar, fundo=COR_BARRA):
        super().__init__(mestre, bg=fundo)
        self.valor, self.ao_mudar = valor, ao_mudar
        self._botao("−", -1).pack(side="left")
        self.rotulo = tk.Label(self, text="", font=fontes.interface, bg=fundo, fg=COR_TEXTO, width=5)
        self.rotulo.pack(side="left")
        self._botao("+", 1).pack(side="left")
        self._mostrar()

    def _botao(self, texto, passo):
        botao = tk.Label(self, text=texto, font=(fontes.interface[0], 12), bg=COR_PASSAR_MOUSE,
                         fg=COR_TEXTO, width=2, cursor="hand2")
        botao.bind("<Button-1>", lambda e: self.passo(passo))
        return botao

    def passo(self, variacao):
        self.valor = min(max(self.valor + variacao, TAMANHO_FONTE_MINIMO), TAMANHO_FONTE_MAXIMO)
        self._mostrar()
        self.ao_mudar(self.valor)

    def _mostrar(self):
        self.rotulo.config(text=f"{self.valor} pt")
