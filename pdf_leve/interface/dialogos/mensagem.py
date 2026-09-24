"""Caixa de mensagem no tema escuro (substitui o messagebox nativo, que é claro)."""

import tkinter as tk

from pdf_leve.configuracao.tema import COR_BARRA, COR_TEXTO, fontes
from pdf_leve.interface.componentes import BotaoPlano
from pdf_leve.interface.utilidades import centralizar
from pdf_leve.sistema.windows import barra_titulo_escura


class DialogoMensagem(tk.Toplevel):
    """Mensagem com botões. `botoes` é uma lista de (rótulo, valor, principal?).

    Modal: o construtor só retorna depois que o usuário responde; a resposta fica em
    `resultado` (None se a janela for fechada ou Esc for pressionado).
    """

    def __init__(self, mestre, titulo, mensagem, botoes, padrao=None):
        super().__init__(mestre, bg=COR_BARRA)
        self.withdraw()
        self.title(titulo)
        self.transient(mestre)
        self.resizable(False, False)
        self.resultado = None
        tk.Label(self, text=mensagem, bg=COR_BARRA, fg=COR_TEXTO, font=fontes.interface, justify="left",
                 wraplength=420, padx=22, pady=20).pack(anchor="w")
        linha = tk.Frame(self, bg=COR_BARRA)
        linha.pack(fill="x", padx=18, pady=(0, 16))
        for rotulo, valor, principal in reversed(botoes):
            BotaoPlano(linha, rotulo, lambda v=valor: self.concluir(v), principal).pack(side="right", padx=(8, 0))
        self.bind("<Escape>", lambda e: self.concluir(None))
        self.bind("<Return>", lambda e: self.concluir(padrao))
        self.protocol("WM_DELETE_WINDOW", lambda: self.concluir(None))
        centralizar(self, mestre)
        barra_titulo_escura(self)
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()

    def concluir(self, valor):
        self.resultado = valor
        self.destroy()
