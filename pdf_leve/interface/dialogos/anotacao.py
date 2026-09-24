"""Diálogo para escrever ou editar o texto de uma anotação, com cor e tamanho."""

import tkinter as tk
from tkinter import colorchooser

from pdf_leve.configuracao.tema import (
    COR_BARRA, COR_DESTAQUE, COR_FUNDO_EDITOR_ANOTACAO, COR_LINHA, COR_SELECAO_EDITOR_ANOTACAO,
    COR_TEXTO_SUAVE, fontes,
)
from pdf_leve.interface.componentes import BotaoPlano, SeletorCores, SeletorTamanho
from pdf_leve.sistema.windows import barra_titulo_escura


class DialogoAnotacao(tk.Toplevel):
    """Modal. Ao confirmar, `resultado` = (texto, cor, tamanho); senão, None.

    A área de digitação é branca para mostrar a cor real que o texto terá na página.
    """

    def __init__(self, mestre, titulo, texto="", cor="#d32f2f", tamanho=12):
        super().__init__(mestre, bg=COR_BARRA)
        self.withdraw()
        self.title(titulo)
        self.transient(mestre)
        self.resultado = None
        self.cor = cor

        corpo = tk.Frame(self, bg=COR_BARRA, padx=16, pady=14)
        corpo.pack(fill="both", expand=True)
        self.caixa_texto = tk.Text(
            corpo, width=50, height=6, wrap="word", undo=True, font=(fontes.interface[0], 12),
            bg=COR_FUNDO_EDITOR_ANOTACAO, fg=cor, insertbackground=cor, relief="flat", padx=10, pady=8,
            highlightthickness=1, highlightbackground=COR_LINHA, highlightcolor=COR_DESTAQUE,
            selectbackground=COR_SELECAO_EDITOR_ANOTACAO)
        self.caixa_texto.pack(fill="both", expand=True)
        self.caixa_texto.insert("1.0", texto)

        linha = tk.Frame(corpo, bg=COR_BARRA)
        linha.pack(fill="x", pady=(12, 0))
        self.seletor_cores = SeletorCores(linha, cor, self.definir_cor)
        self.seletor_cores.pack(side="left")
        outra_cor = tk.Label(linha, text="Outra…", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE,
                             cursor="hand2", padx=6)
        outra_cor.pack(side="left")
        outra_cor.bind("<Button-1>", lambda e: self.escolher_outra_cor())
        self.seletor_tamanho = SeletorTamanho(linha, tamanho, lambda valor: None)
        self.seletor_tamanho.pack(side="right")

        botoes = tk.Frame(corpo, bg=COR_BARRA)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Label(botoes, text="Ctrl+Enter confirma · Esc cancela", font=fontes.pequena, bg=COR_BARRA,
                 fg=COR_TEXTO_SUAVE).pack(side="left")
        BotaoPlano(botoes, "OK", self.confirmar, principal=True).pack(side="right")
        BotaoPlano(botoes, "Cancelar", self.destroy).pack(side="right", padx=8)

        self.caixa_texto.bind("<Control-Return>", lambda e: (self.confirmar(), "break")[1])
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._posicionar_perto_do_mouse(mestre)
        barra_titulo_escura(self)
        self.deiconify()
        self.caixa_texto.focus_set()
        self.grab_set()
        self.wait_window()

    def _posicionar_perto_do_mouse(self, mestre):
        self.update_idletasks()
        x = min(max(0, mestre.winfo_pointerx() - 60), self.winfo_screenwidth() - self.winfo_reqwidth() - 10)
        y = min(max(0, mestre.winfo_pointery() - 40), self.winfo_screenheight() - self.winfo_reqheight() - 60)
        self.geometry(f"+{x}+{y}")

    def definir_cor(self, cor):
        self.cor = cor
        self.caixa_texto.config(fg=cor, insertbackground=cor)
        self.seletor_cores.selecionar(cor)

    def escolher_outra_cor(self):
        cor = colorchooser.askcolor(self.cor, parent=self, title="Cor do texto")[1]
        if cor:
            self.definir_cor(cor)

    def confirmar(self):
        texto = self.caixa_texto.get("1.0", "end-1c").rstrip()
        if texto.strip():
            self.resultado = (texto, self.cor, self.seletor_tamanho.valor)
        self.destroy()
