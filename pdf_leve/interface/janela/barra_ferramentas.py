"""Montagem da interface da janela: barra de ferramentas, área das páginas, atalhos e avisos."""

import os
import tkinter as tk
from tkinter import ttk

from pdf_leve.configuracao.constantes import (
    DURACAO_AVISO_MS, LINHAS_POR_SETA, NOME_APLICATIVO, PASSO_ZOOM, PIXELS_POR_UNIDADE_ROLAGEM,
)
from pdf_leve.configuracao.tema import (
    COR_AVISO, COR_BARRA, COR_BARRA_ROLAGEM, COR_BARRA_ROLAGEM_ATIVA, COR_BORDA_BOTAO_COR, COR_CAMPO,
    COR_DESTAQUE, COR_FUNDO, COR_ICONE_TELA_VAZIA, COR_LINHA, COR_PASSAR_MOUSE, COR_TEXTO,
    COR_TEXTO_APAGADO, COR_TEXTO_SUAVE, fonte_icone, fontes, glifo,
)
from pdf_leve.interface.componentes import BotaoIcone, Dica
from pdf_leve.interface.dialogos import DialogoMensagem


class MixinBarraFerramentas:

    def _configurar_estilos(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        for orientacao in ("Vertical", "Horizontal"):
            nome = f"Escura.{orientacao}.TScrollbar"
            # só a trilha e o polegar: sem setas, como nas barras de rolagem modernas
            estilo.layout(nome, [(f"{orientacao}.Scrollbar.trough", {"sticky": "nswe", "children": [
                (f"{orientacao}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            estilo.configure(nome, background=COR_BARRA_ROLAGEM, troughcolor=COR_FUNDO, bordercolor=COR_FUNDO,
                             lightcolor=COR_BARRA_ROLAGEM, darkcolor=COR_BARRA_ROLAGEM, arrowsize=11,
                             relief="flat", gripcount=0)
            ativa = [("active", COR_BARRA_ROLAGEM_ATIVA)]
            estilo.map(nome, background=ativa, lightcolor=ativa, darkcolor=ativa)

    def _montar_interface(self):
        self._configurar_estilos()
        self.barra = barra = tk.Frame(self, bg=COR_BARRA, padx=6, pady=3)
        barra.pack(side="top", fill="x")
        self.linha_barra = tk.Frame(self, bg=COR_LINHA, height=1)
        self.linha_barra.pack(side="top", fill="x")

        def divisoria():
            tk.Frame(barra, bg=COR_LINHA, width=1, height=20).pack(side="left", padx=8)

        # arquivo
        BotaoIcone(barra, "abrir", self.abrir_arquivo, "Abrir PDF (Ctrl+O) · nova janela: Ctrl+N").pack(side="left")
        self.botao_salvar = BotaoIcone(barra, "salvar", self.salvar, "Salvar (Ctrl+S)")
        self.botao_salvar.pack(side="left")
        BotaoIcone(barra, "imprimir", self.exportar_paginas, "Salvar páginas em PDF (Ctrl+P)").pack(side="left")
        divisoria()

        # navegação
        BotaoIcone(barra, "anterior", lambda: self.avancar_pagina(-1), "Página anterior (←)").pack(side="left")
        self.var_pagina = tk.StringVar()
        self.campo_pagina = tk.Entry(barra, width=5, textvariable=self.var_pagina, justify="center",
                                     font=fontes.interface, bg=COR_CAMPO, fg=COR_TEXTO, insertbackground=COR_TEXTO,
                                     relief="flat", highlightthickness=1, highlightbackground=COR_LINHA,
                                     highlightcolor=COR_DESTAQUE)
        self.campo_pagina.pack(side="left", ipady=3, padx=(2, 4))
        self.campo_pagina.bind("<Return>", self._ao_digitar_pagina)
        self.campo_pagina.bind("<Escape>", lambda e: self.tela.focus_set())
        self.campo_pagina.bind("<FocusIn>", lambda e: self.campo_pagina.select_range(0, "end"))
        self.rotulo_total = tk.Label(barra, text="", font=fontes.interface, bg=COR_BARRA, fg=COR_TEXTO_SUAVE)
        self.rotulo_total.pack(side="left")
        BotaoIcone(barra, "proxima", lambda: self.avancar_pagina(1), "Próxima página (→)").pack(
            side="left", padx=(2, 0))
        divisoria()

        # zoom e rotação
        BotaoIcone(barra, "diminuir_zoom", lambda: self.definir_zoom(self.zoom / PASSO_ZOOM),
                   "Diminuir zoom (Ctrl −)").pack(side="left")
        self.rotulo_zoom = tk.Label(barra, text="", font=fontes.interface, bg=COR_BARRA, fg=COR_TEXTO_SUAVE,
                                    width=5, cursor="hand2")
        self.rotulo_zoom.pack(side="left")
        self.rotulo_zoom.bind("<Button-1>", lambda e: self.definir_zoom(1.0))
        Dica(self.rotulo_zoom, "Clique para 100% (Ctrl+0)")
        BotaoIcone(barra, "aumentar_zoom", lambda: self.definir_zoom(self.zoom * PASSO_ZOOM),
                   "Aumentar zoom (Ctrl +)").pack(side="left")
        self.botao_ajuste_largura = BotaoIcone(barra, "ajustar_largura", lambda: self.definir_ajuste("largura"),
                                               "Ajustar à largura (Ctrl+1)")
        self.botao_ajuste_largura.pack(side="left")
        self.botao_ajuste_pagina = BotaoIcone(barra, "ajustar_pagina", lambda: self.definir_ajuste("pagina"),
                                              "Página inteira (Ctrl+2)")
        self.botao_ajuste_pagina.pack(side="left")
        BotaoIcone(barra, "girar", lambda: self.girar(90),
                   "Girar página (Ctrl+→ horário · Ctrl+← anti-horário · com Shift: todas)").pack(side="left")
        divisoria()

        # anotações
        self.botao_texto = BotaoIcone(barra, "texto", self.alternar_modo_texto, "Anotar com texto (T)")
        self.botao_texto.pack(side="left")
        self.botao_cor = tk.Canvas(barra, width=30, height=30, bg=COR_BARRA, highlightthickness=0, cursor="hand2")
        self.botao_cor.pack(side="left", padx=2)
        self.botao_cor.bind("<Button-1>", lambda e: self.alternar_painel_estilo())
        self.botao_cor.bind("<Enter>", lambda e: self.botao_cor.config(bg=COR_PASSAR_MOUSE))
        self.botao_cor.bind("<Leave>", lambda e: self.botao_cor.config(bg=COR_BARRA))
        Dica(self.botao_cor, lambda: f"Cor e tamanho do texto ({self.tamanho_fonte} pt)")

        self._montar_busca(barra)
        self._montar_area_paginas()
        self.atualizar_botao_cor()
        self.atualizar_botoes()

    def _montar_busca(self, barra):
        caixa = tk.Frame(barra, bg=COR_CAMPO, highlightthickness=1, highlightbackground=COR_LINHA,
                         highlightcolor=COR_DESTAQUE)
        caixa.pack(side="right", padx=(0, 2))
        tk.Label(caixa, text=glifo("buscar"), font=fonte_icone(10), bg=COR_CAMPO, fg=COR_TEXTO_SUAVE,
                 padx=6).pack(side="left")
        self.var_busca = tk.StringVar()
        self.campo_busca = tk.Entry(caixa, width=22, textvariable=self.var_busca, font=fontes.interface,
                                    bg=COR_CAMPO, fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
                                    highlightthickness=0)
        self.campo_busca.pack(side="left", ipady=4)
        self.campo_busca.bind("<Return>", lambda e: self.buscar())
        self.campo_busca.bind("<Shift-Return>", lambda e: self.buscar(voltar=True))
        self.campo_busca.bind("<Escape>", lambda e: self.limpar_busca())
        self.campo_busca.bind("<FocusIn>", lambda e: caixa.config(highlightbackground=COR_DESTAQUE))
        self.campo_busca.bind("<FocusOut>", lambda e: caixa.config(highlightbackground=COR_LINHA))
        self.rotulo_contagem = tk.Label(caixa, text="", font=fontes.pequena, bg=COR_CAMPO, fg=COR_TEXTO_SUAVE,
                                        padx=4)
        self.rotulo_contagem.pack(side="left")
        for nome, voltar, dica in (("acima", True, "Anterior (Shift+Enter)"), ("abaixo", False, "Próximo (Enter / F3)")):
            botao = BotaoIcone(caixa, nome, lambda voltar=voltar: self.buscar(voltar=voltar), dica, fundo=COR_CAMPO)
            botao.config(padx=5, pady=3, font=fonte_icone(9))
            botao.pack(side="left")
        botao = BotaoIcone(caixa, "fechar", self.limpar_busca, "Limpar busca (Esc)", fundo=COR_CAMPO)
        botao.config(padx=6, pady=3, font=fonte_icone(8))
        botao.pack(side="left")

    def _montar_area_paginas(self):
        self.area = tk.Frame(self, bg=COR_FUNDO)
        self.area.pack(fill="both", expand=True)
        self.tela = tk.Canvas(self.area, bg=COR_FUNDO, highlightthickness=0,
                              xscrollincrement=PIXELS_POR_UNIDADE_ROLAGEM,
                              yscrollincrement=PIXELS_POR_UNIDADE_ROLAGEM)
        self.rolagem_vertical = ttk.Scrollbar(self.area, orient="vertical", command=self._rolar_vertical,
                                              style="Escura.Vertical.TScrollbar")
        self.rolagem_horizontal = ttk.Scrollbar(self.area, orient="horizontal", command=self._rolar_horizontal,
                                                style="Escura.Horizontal.TScrollbar")
        self.tela.config(yscrollcommand=self.rolagem_vertical.set, xscrollcommand=self._ajustar_rolagem_horizontal)
        self.tela.grid(row=0, column=0, sticky="nsew")
        self.rolagem_vertical.grid(row=0, column=1, sticky="ns")
        self.rolagem_horizontal.grid(row=1, column=0, sticky="ew")
        self.area.rowconfigure(0, weight=1)
        self.area.columnconfigure(0, weight=1)
        self.rotulo_aviso = tk.Label(self.area, bg=COR_AVISO, fg=COR_TEXTO, font=fontes.interface, padx=14, pady=7)

    def _ajustar_rolagem_horizontal(self, inicio, fim):
        """A barra horizontal só aparece quando a página é mais larga que a janela."""
        if float(inicio) <= 0 and float(fim) >= 1:
            self.rolagem_horizontal.grid_remove()
        else:
            self.rolagem_horizontal.grid()
        self.rolagem_horizontal.set(inicio, fim)

    def _ligar_atalhos(self):
        tela = self.tela
        tela.bind("<Configure>", self._ao_redimensionar)
        tela.bind("<MouseWheel>", self._ao_girar_roda)
        tela.bind("<Shift-MouseWheel>", lambda e: self._rolar("x", e.delta))
        tela.bind("<Control-MouseWheel>", self._ao_girar_roda_com_ctrl)
        tela.bind("<ButtonPress-1>", self._ao_pressionar)
        tela.bind("<B1-Motion>", self._ao_arrastar)
        tela.bind("<ButtonRelease-1>", self._ao_soltar_botao)
        tela.bind("<Double-Button-1>", self._ao_clicar_duas_vezes)
        tela.bind("<Triple-Button-1>", self._ao_clicar_tres_vezes)
        tela.bind("<ButtonPress-2>", self._iniciar_movimento_pagina)
        tela.bind("<B2-Motion>", self._mover_pagina)
        tela.bind("<ButtonRelease-2>", self._encerrar_movimento_pagina)
        tela.bind("<Button-3>", self._ao_clicar_direito)
        tela.bind("<Motion>", self._ao_mover_mouse)
        tela.bind("<Control-c>", lambda e: self.copiar_selecao())
        tela.bind("<Control-C>", lambda e: self.copiar_selecao())
        tela.bind("<Delete>", lambda e: self.excluir_anotacao_selecionada())
        tela.bind("<t>", lambda e: self.alternar_modo_texto())
        tela.bind("<T>", lambda e: self.alternar_modo_texto())
        tela.bind("<Escape>", lambda e: self._ao_pressionar_esc())
        tela.bind("<Right>", lambda e: self.avancar_pagina(1))
        tela.bind("<Left>", lambda e: self.avancar_pagina(-1))
        tela.bind("<Down>", lambda e: self._rolar_vertical("scroll", LINHAS_POR_SETA, "units"))
        tela.bind("<Up>", lambda e: self._rolar_vertical("scroll", -LINHAS_POR_SETA, "units"))
        tela.bind("<Next>", lambda e: self._rolar_vertical("scroll", 1, "pages"))
        tela.bind("<Prior>", lambda e: self._rolar_vertical("scroll", -1, "pages"))
        tela.bind("<Home>", lambda e: self.ir_para_pagina(0))
        tela.bind("<End>", lambda e: self.ir_para_pagina(len(self.disposicao) - 1))
        tela.bind("<Control-Right>", lambda e: self.girar(90))
        tela.bind("<Control-Left>", lambda e: self.girar(-90))
        tela.bind("<Control-Shift-Right>", lambda e: self.girar(90, todas=True))
        tela.bind("<Control-Shift-Left>", lambda e: self.girar(-90, todas=True))
        # Atenção: "<Control-1>" no Tk é Ctrl + botão 1 do mouse; para teclas numéricas, use "Key-".
        self.bind("<Control-o>", lambda e: self.abrir_arquivo())
        self.bind("<Control-n>", lambda e: self.aplicativo.nova_janela(perto_de=self))
        self.bind("<Control-s>", lambda e: self.salvar())
        self.bind("<Control-S>", lambda e: self.salvar_como())
        self.bind("<Control-p>", lambda e: self.exportar_paginas())
        self.bind("<Control-P>", lambda e: self.exportar_paginas())
        self.bind("<Control-f>", lambda e: self.focar_busca())
        self.bind("<Control-plus>", lambda e: self.definir_zoom(self.zoom * PASSO_ZOOM))
        self.bind("<Control-equal>", lambda e: self.definir_zoom(self.zoom * PASSO_ZOOM))
        self.bind("<Control-minus>", lambda e: self.definir_zoom(self.zoom / PASSO_ZOOM))
        self.bind("<Control-Key-0>", lambda e: self.definir_zoom(1.0))
        self.bind("<Control-Key-1>", lambda e: self.definir_ajuste("largura"))
        self.bind("<Control-Key-2>", lambda e: self.definir_ajuste("pagina"))
        self.bind("<F11>", lambda e: self.alternar_tela_cheia())
        self.bind("<F3>", lambda e: self.buscar())
        self.bind("<Shift-F3>", lambda e: self.buscar(voltar=True))
        tela.focus_set()

    # ------------------------------------------------------------------ avisos e diálogos
    def avisar(self, mensagem, duracao_ms=DURACAO_AVISO_MS):
        """Aviso discreto no rodapé, que some sozinho."""
        self.rotulo_aviso.config(text=mensagem)
        self.rotulo_aviso.place(relx=0.5, rely=1.0, y=-26, anchor="s")
        self.rotulo_aviso.lift()
        if self._tarefa_aviso:
            self.after_cancel(self._tarefa_aviso)
        self._tarefa_aviso = self.after(duracao_ms, self.rotulo_aviso.place_forget)

    def perguntar(self, titulo, mensagem, botoes, padrao=None):
        return DialogoMensagem(self, titulo, mensagem, botoes, padrao).resultado

    def mostrar_erro(self, mensagem):
        self.perguntar(NOME_APLICATIVO, mensagem, [("OK", True, True)], True)

    # ------------------------------------------------------------------ estado visual
    def atualizar_titulo(self):
        nome = os.path.basename(self.caminho) if self.caminho else ""
        marcador = "● " if self.modificado else ""
        self.title(f"{marcador}{nome} — {NOME_APLICATIVO}" if nome else NOME_APLICATIVO)
        self.botao_salvar.definir_cor_texto(COR_DESTAQUE if self.modificado else COR_TEXTO)

    def marcar_modificado(self):
        self.modificado = True
        self.atualizar_titulo()

    def atualizar_botoes(self):
        self.botao_texto.definir_ativo(self.modo_texto)
        self.botao_ajuste_largura.definir_ativo(self.modo_ajuste == "largura")
        self.botao_ajuste_pagina.definir_ativo(self.modo_ajuste == "pagina")

    def atualizar_botao_cor(self):
        self.botao_cor.delete("all")
        self.botao_cor.create_oval(7, 7, 23, 23, fill=self.cor, outline=COR_BORDA_BOTAO_COR, width=1)

    def desenhar_tela_vazia(self):
        tela = self.tela
        tela.delete("all")
        largura, altura = tela.winfo_width(), tela.winfo_height()
        tela.config(scrollregion=(0, 0, largura, altura))
        tela.create_text(largura / 2, altura / 2 - 40, text=glifo("abrir"), font=fontes.icone_grande,
                         fill=COR_ICONE_TELA_VAZIA)
        tela.create_text(largura / 2, altura / 2 + 20, text="Arraste PDFs para cá",
                         font=(fontes.interface[0], 14), fill=COR_TEXTO_SUAVE)
        tela.create_text(largura / 2, altura / 2 + 48, text="ou clique para abrir  ·  Ctrl+O",
                         font=fontes.interface, fill=COR_TEXTO_APAGADO)

    # ------------------------------------------------------------------ tela cheia
    def alternar_tela_cheia(self, ligar=None):
        ligar = not self.tela_cheia if ligar is None else ligar
        if ligar == self.tela_cheia:
            return
        self.tela_cheia = ligar
        self.attributes("-fullscreen", ligar)
        if ligar:
            self._esconder_barra()
            self.avisar("Tela cheia · F11 ou Esc para sair")
        else:
            self._mostrar_barra()
        self.tela.focus_set()

    def _mostrar_barra(self):
        if not self.barra.winfo_ismapped():
            self.barra.pack(side="top", fill="x", before=self.area)
            self.linha_barra.pack(side="top", fill="x", before=self.area)

    def _esconder_barra(self):
        self.barra.pack_forget()
        self.linha_barra.pack_forget()
