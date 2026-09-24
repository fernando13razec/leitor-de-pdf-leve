"""Dica (tooltip) que aparece ao parar o mouse sobre um elemento."""

import tkinter as tk

from pdf_leve.configuracao.tema import COR_AVISO, COR_TEXTO, fontes

ATRASO_MS = 500


class Dica:
    def __init__(self, elemento, texto):
        """`texto` pode ser uma string ou uma função que devolve a string na hora de exibir."""
        self.elemento, self.texto = elemento, texto
        self.janela_dica = self.tarefa = None
        elemento.bind("<Enter>", self._agendar, add="+")
        elemento.bind("<Leave>", self._esconder, add="+")
        elemento.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _evento):
        self._esconder()
        self.tarefa = self.elemento.after(ATRASO_MS, self._mostrar)

    def _mostrar(self):
        texto = self.texto() if callable(self.texto) else self.texto
        self.janela_dica = tk.Toplevel(self.elemento)
        self.janela_dica.overrideredirect(True)
        self.janela_dica.attributes("-topmost", True)
        tk.Label(self.janela_dica, text=texto, bg=COR_AVISO, fg=COR_TEXTO, font=fontes.pequena,
                 padx=8, pady=4).pack()
        self.janela_dica.update_idletasks()
        largura = self.janela_dica.winfo_width()
        x = self.elemento.winfo_rootx() + self.elemento.winfo_width() // 2 - largura // 2
        x = max(0, min(x, self.elemento.winfo_screenwidth() - largura))
        y = self.elemento.winfo_rooty() + self.elemento.winfo_height() + 6
        self.janela_dica.geometry(f"+{x}+{y}")

    def _esconder(self, _evento=None):
        if self.tarefa:
            self.elemento.after_cancel(self.tarefa)
            self.tarefa = None
        if self.janela_dica:
            self.janela_dica.destroy()
            self.janela_dica = None
