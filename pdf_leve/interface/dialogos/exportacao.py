"""Diálogo “Salvar páginas em PDF”: escolha de todas, da atual ou de um intervalo (como no Chrome)."""

import re
import tkinter as tk

from pdf_leve.configuracao.tema import (
    COR_ATIVO, COR_BARRA, COR_CAMPO, COR_DESTAQUE, COR_LINHA, COR_PERIGO, COR_TEXTO, COR_TEXTO_SUAVE, fontes,
)
from pdf_leve.interface.componentes import BotaoPlano
from pdf_leve.interface.utilidades import centralizar, plural
from pdf_leve.servicos.intervalos import interpretar_intervalos
from pdf_leve.sistema.windows import barra_titulo_escura

DICA_INTERVALO = "Por exemplo: 1-5, 8, 11-13"
TAMANHO_MAXIMO_ROTULO = 60


class DialogoExportacao(tk.Toplevel):
    """Modal. Ao confirmar, `resultado` = (índices das páginas, rótulo para o nome do arquivo);
    o rótulo é None quando todas as páginas foram escolhidas."""

    def __init__(self, mestre, total, pagina_atual):
        super().__init__(mestre, bg=COR_BARRA)
        self.withdraw()
        self.title("Salvar páginas")
        self.transient(mestre)
        self.resizable(False, False)
        self.total, self.pagina_atual = total, pagina_atual
        self.resultado, self.modo = None, "todas"

        corpo = tk.Frame(self, bg=COR_BARRA, padx=22, pady=18)
        corpo.pack(fill="both", expand=True)
        cabecalho = tk.Frame(corpo, bg=COR_BARRA)
        cabecalho.pack(fill="x")
        tk.Label(cabecalho, text="Salvar páginas em PDF", font=(fontes.interface[0], 14), bg=COR_BARRA,
                 fg=COR_TEXTO).pack(side="left")
        self.rotulo_contagem = tk.Label(cabecalho, text="", font=(fontes.interface[0], 10, "bold"),
                                        bg=COR_BARRA, fg=COR_TEXTO)
        self.rotulo_contagem.pack(side="right", padx=(24, 0))

        tk.Label(corpo, text="Páginas", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE).pack(
            anchor="w", pady=(18, 6))
        opcoes = tk.Frame(corpo, bg=COR_CAMPO, highlightthickness=1, highlightbackground=COR_LINHA)
        opcoes.pack(fill="x")
        self.opcoes = {}
        for modo, rotulo in (("todas", "Todas"), ("atual", f"Atual ({pagina_atual + 1})"),
                             ("personalizado", "Personalizado")):
            opcao = tk.Label(opcoes, text=rotulo, font=fontes.interface, bg=COR_CAMPO, fg=COR_TEXTO,
                             padx=14, pady=6, cursor="hand2")
            opcao.pack(side="left", expand=True, fill="x")
            opcao.bind("<Button-1>", lambda e, modo=modo: self.definir_modo(modo))
            self.opcoes[modo] = opcao

        self.var_intervalo = tk.StringVar()
        self.campo = tk.Entry(corpo, textvariable=self.var_intervalo, font=fontes.interface, bg=COR_CAMPO,
                              fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat", highlightthickness=1,
                              highlightbackground=COR_LINHA, highlightcolor=COR_DESTAQUE, width=40)
        self.campo.pack(fill="x", pady=(10, 0), ipady=6)
        self.campo.bind("<FocusIn>", lambda e: self.definir_modo("personalizado", focar=False))
        self.rotulo_dica = tk.Label(corpo, text=DICA_INTERVALO, font=fontes.pequena, bg=COR_BARRA,
                                    fg=COR_TEXTO_SUAVE)
        self.rotulo_dica.pack(anchor="w", pady=(4, 0))
        self.var_intervalo.trace_add("write", lambda *a: self.atualizar_contagem())

        botoes = tk.Frame(corpo, bg=COR_BARRA)
        botoes.pack(fill="x", pady=(20, 0))
        BotaoPlano(botoes, "Salvar", self.confirmar, principal=True).pack(side="right")
        BotaoPlano(botoes, "Cancelar", self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda e: self.confirmar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.definir_modo("todas")
        centralizar(self, mestre)
        barra_titulo_escura(self)
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window()

    def definir_modo(self, modo, focar=True):
        self.modo = modo
        for chave, opcao in self.opcoes.items():
            opcao.config(bg=COR_ATIVO if chave == modo else COR_CAMPO,
                         fg=COR_DESTAQUE if chave == modo else COR_TEXTO)
        if modo == "personalizado" and focar:
            self.campo.focus_set()
        elif modo != "personalizado":
            self.focus_set()
        self.atualizar_contagem()

    def paginas(self):
        if self.modo == "todas":
            return list(range(self.total)), None
        if self.modo == "atual":
            return [self.pagina_atual], None
        return interpretar_intervalos(self.var_intervalo.get(), self.total)

    def atualizar_contagem(self):
        paginas, erro = self.paginas()
        if self.modo == "personalizado" and not self.var_intervalo.get().strip():
            paginas, erro = [], None
        self.rotulo_contagem.config(text=plural(len(paginas), "página", "páginas") if paginas else "")
        self.rotulo_dica.config(text=erro or DICA_INTERVALO, fg=COR_PERIGO if erro else COR_TEXTO_SUAVE)

    def confirmar(self):
        paginas, erro = self.paginas()
        if erro or not paginas:
            self.rotulo_dica.config(text=erro or "Informe as páginas", fg=COR_PERIGO)
            self.definir_modo("personalizado")
            return
        rotulos = {
            "todas": None,
            "atual": str(self.pagina_atual + 1),
            "personalizado": re.sub(r"\s*,\s*", ", ", self.var_intervalo.get().strip())[:TAMANHO_MAXIMO_ROTULO],
        }
        self.resultado = (paginas, rotulos[self.modo])
        self.destroy()
