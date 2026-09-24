"""Painel flutuante (abre pelo círculo colorido da barra) com cor e tamanho das anotações."""

import tkinter as tk

from pdf_leve.configuracao.tema import COR_BARRA, COR_DESTAQUE, COR_LINHA, COR_TEXTO_SUAVE, fontes
from pdf_leve.interface.componentes import SeletorCores, SeletorTamanho


class PainelEstilo(tk.Toplevel):
    """Fecha ao clicar fora, com Esc ou ao escolher “Outra cor…”.

    `janela` precisa oferecer: `cor`, `tamanho_fonte`, `escolher_cor(cor)`,
    `definir_tamanho(n)`, `escolher_outra_cor()` e o atributo `painel_estilo`.
    """

    def __init__(self, janela, ancora):
        super().__init__(janela, bg=COR_LINHA)
        self.janela = janela
        self.fechado = False
        self.overrideredirect(True)
        interno = tk.Frame(self, bg=COR_BARRA, padx=12, pady=10)
        interno.pack(padx=1, pady=1)  # a margem de 1 px vira a borda
        tk.Label(interno, text="Cor do texto", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE).pack(anchor="w")
        self.seletor_cores = SeletorCores(interno, janela.cor, self._escolher_cor)
        self.seletor_cores.pack(anchor="w", pady=(4, 2))
        outra_cor = tk.Label(interno, text="Outra cor…", font=fontes.pequena, bg=COR_BARRA, fg=COR_DESTAQUE,
                             cursor="hand2")
        outra_cor.pack(anchor="w", pady=(0, 8))
        outra_cor.bind("<Button-1>", lambda e: (self.fechar(), janela.escolher_outra_cor()))
        tk.Label(interno, text="Tamanho", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE).pack(anchor="w")
        SeletorTamanho(interno, janela.tamanho_fonte, janela.definir_tamanho).pack(anchor="w", pady=(4, 0))

        self.update_idletasks()
        x = ancora.winfo_rootx() + ancora.winfo_width() // 2 - self.winfo_reqwidth() // 2
        self.geometry(f"+{max(0, x)}+{ancora.winfo_rooty() + ancora.winfo_height() + 4}")
        # Liga o “clique fora” só depois: o clique que abriu o painel não deve fechá-lo.
        self.after_idle(lambda: janela.bind_all("<Button-1>", self._ao_clicar_fora, add="+"))
        self.bind("<Escape>", lambda e: self.fechar())
        self.focus_force()

    def _escolher_cor(self, cor):
        self.janela.escolher_cor(cor)
        self.seletor_cores.selecionar(cor)

    def _ao_clicar_fora(self, evento):
        try:
            if not str(evento.widget).startswith(str(self)):
                self.fechar()
        except Exception:
            self.fechar()

    def fechar(self):
        if self.fechado:
            return
        self.fechado = True
        try:
            self.janela.unbind_all("<Button-1>")
        except Exception:
            pass
        self.janela.painel_estilo = None
        self.destroy()
