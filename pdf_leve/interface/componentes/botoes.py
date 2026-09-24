"""Botões planos no estilo do tema escuro."""

import tkinter as tk

from pdf_leve.configuracao.tema import (
    COR_ATIVO, COR_BARRA, COR_BOTAO_SECUNDARIO_ATIVO, COR_DESTAQUE, COR_DESTAQUE_CLARO,
    COR_PASSAR_MOUSE, COR_TEXTO, COR_TEXTO_SOBRE_DESTAQUE, fontes, glifo,
)
from pdf_leve.interface.componentes.dica import Dica


class BotaoIcone(tk.Label):
    """Botão com um ícone da fonte de ícones do Windows. Pode ficar “ativo” (ligado)."""

    def __init__(self, mestre, nome_glifo, comando, dica=None, fundo=COR_BARRA):
        super().__init__(mestre, text=glifo(nome_glifo), font=fontes.icone if fontes.tem_icones else fontes.interface,
                         fg=COR_TEXTO, bg=fundo, padx=9, pady=7, cursor="hand2")
        self.comando, self.fundo, self.ativo, self.cor_texto = comando, fundo, False, COR_TEXTO
        self.bind("<Enter>", lambda e: self.config(bg=COR_ATIVO if self.ativo else COR_PASSAR_MOUSE))
        self.bind("<Leave>", lambda e: self._pintar())
        self.bind("<Button-1>", lambda e: self.comando())
        if dica:
            Dica(self, dica)

    def definir_ativo(self, ativo):
        self.ativo = ativo
        self._pintar()

    def definir_cor_texto(self, cor):
        self.cor_texto = cor
        self._pintar()

    def _pintar(self):
        self.config(bg=COR_ATIVO if self.ativo else self.fundo,
                    fg=COR_DESTAQUE if self.ativo else self.cor_texto)


class BotaoPlano(tk.Label):
    """Botão de texto dos diálogos. O principal usa a cor de destaque."""

    def __init__(self, mestre, texto, comando, principal=False):
        if principal:
            self.cor_normal, self.cor_mouse = COR_DESTAQUE, COR_DESTAQUE_CLARO
        else:
            self.cor_normal, self.cor_mouse = COR_PASSAR_MOUSE, COR_BOTAO_SECUNDARIO_ATIVO
        super().__init__(mestre, text=texto, font=fontes.interface, bg=self.cor_normal,
                         fg=COR_TEXTO_SOBRE_DESTAQUE if principal else COR_TEXTO,
                         padx=16, pady=6, cursor="hand2")
        self.bind("<Enter>", lambda e: self.config(bg=self.cor_mouse))
        self.bind("<Leave>", lambda e: self.config(bg=self.cor_normal))
        self.bind("<Button-1>", lambda e: comando())
