"""Eventos do mouse, menu de contexto, tecla Esc e modo texto.

Botão esquerdo: sobre uma anotação, seleciona/move; no modo texto, cria anotação; sobre página com
texto, seleciona texto; em página escaneada (sem texto), arrasta a página.
Botão do meio: sempre arrasta a página.
"""

import tkinter as tk

import fitz  # PyMuPDF

from pdf_leve.configuracao.constantes import CORES_ANOTACAO, MARGEM_ROLAGEM_AUTOMATICA
from pdf_leve.configuracao.tema import COR_BARRA, COR_PASSAR_MOUSE, COR_TEXTO, fontes
from pdf_leve.servicos.anotacoes import ler_propriedades, retangulo_exibido

DISTANCIA_MINIMA_ARRASTE = 3  # px antes de considerar que o mouse está arrastando


class MixinMouse:

    def _posicao_na_tela(self, evento):
        return self.tela.canvasx(evento.x), self.tela.canvasy(evento.y)

    def _ao_pressionar(self, evento):
        self.tela.focus_set()
        if not self.documento:
            self.abrir_arquivo()
            return
        x, y = self._posicao_na_tela(evento)
        anotacao = self.anotacao_no_ponto(x, y)
        if anotacao:
            self.anotacao_selecionada = anotacao
            pagina_pdf, anotacao_pdf = self.obter_anotacao(*anotacao)
            self.arraste = {"inicio": (x, y), "retangulo": retangulo_exibido(pagina_pdf, anotacao_pdf),
                            "moveu": False}
            self.desenhar_sobreposicoes()
            return
        havia_anotacao_selecionada = self.anotacao_selecionada is not None
        self.anotacao_selecionada = None
        self.selecao_texto = None
        self.desenhar_sobreposicoes()
        local = self.ponto_na_pagina(x, y)
        if self.modo_texto and not havia_anotacao_selecionada:
            if local:
                self.nova_anotacao(*local)
            return
        if local and self.palavras_da_pagina(local[0]):
            self.selecionando = {"ancora": (local[0], self.palavra_no_ponto(*local)),
                                 "inicio": (evento.x, evento.y), "moveu": False}
            return
        self._iniciar_movimento_pagina(evento)

    def _ao_arrastar(self, evento):
        if self.arraste:
            self._arrastar_anotacao(evento)
        elif self.selecionando:
            self._arrastar_selecao(evento)
        else:
            self._mover_pagina(evento)

    def _arrastar_anotacao(self, evento):
        x, y = self._posicao_na_tela(evento)
        x0, y0 = self.arraste["inicio"]
        if abs(x - x0) + abs(y - y0) > DISTANCIA_MINIMA_ARRASTE or self.arraste["moveu"]:
            self.arraste["moveu"] = True
            self.tela.delete("sobreposicao")
            escala = self.zoom * self.escala_base
            deslocamento = ((x - x0) / escala, (y - y0) / escala) * 2
            self.desenhar_contorno_anotacao(self.anotacao_selecionada[0], self.arraste["retangulo"] + deslocamento)

    def _arrastar_selecao(self, evento):
        x0, y0 = self.selecionando["inicio"]
        if abs(evento.x - x0) + abs(evento.y - y0) <= DISTANCIA_MINIMA_ARRASTE and not self.selecionando["moveu"]:
            return
        self.selecionando["moveu"] = True
        altura = self.tela.winfo_height()
        if evento.y < MARGEM_ROLAGEM_AUTOMATICA or evento.y > altura - MARGEM_ROLAGEM_AUTOMATICA:
            self._rolar_vertical("scroll", -1 if evento.y < MARGEM_ROLAGEM_AUTOMATICA else 1, "units")
        pagina, ponto = self.pagina_sob_cursor(*self._posicao_na_tela(evento))
        indice = self.palavra_no_ponto(pagina, ponto)
        if indice is not None:
            self.selecao_texto = (self.selecionando["ancora"], (pagina, indice))
            self.desenhar_sobreposicoes()

    def _ao_soltar_botao(self, evento):
        if self.arraste and self.arraste["moveu"] and self.anotacao_selecionada:
            self._concluir_movimento_anotacao(evento)
        self.arraste = None
        self.selecionando = None
        self._encerrar_movimento_pagina(evento)
        self.desenhar_sobreposicoes()

    def _concluir_movimento_anotacao(self, evento):
        x, y = self._posicao_na_tela(evento)
        x0, y0 = self.arraste["inicio"]
        escala = self.zoom * self.escala_base
        pagina, xref = self.anotacao_selecionada
        pagina_pdf, anotacao = self.obter_anotacao(pagina, xref)
        retangulo = fitz.Rect(self.arraste["retangulo"])
        limites = pagina_pdf.rect
        dx = min(max((x - x0) / escala, limites.x0 - retangulo.x0), limites.x1 - retangulo.x1)
        dy = min(max((y - y0) / escala, limites.y0 - retangulo.y0), limites.y1 - retangulo.y1)
        texto, cor, tamanho = ler_propriedades(self.documento, anotacao)
        self.aplicar_na_anotacao(pagina, xref, texto, cor, tamanho, retangulo + (dx, dy, dx, dy))

    def _ao_clicar_duas_vezes(self, evento):
        """Duplo clique: edita a anotação ou seleciona a palavra."""
        if not self.documento:
            return
        x, y = self._posicao_na_tela(evento)
        anotacao = self.anotacao_no_ponto(x, y)
        if anotacao:
            self.arraste = None
            self.editar_anotacao(*anotacao)
            return
        local = self.ponto_na_pagina(x, y)
        if local and not self.modo_texto:
            self.selecionar_palavra(*local)

    def _ao_clicar_tres_vezes(self, evento):
        """Triplo clique: seleciona a linha."""
        if not self.documento or self.modo_texto:
            return
        local = self.ponto_na_pagina(*self._posicao_na_tela(evento))
        if local:
            self.selecionar_linha(*local)

    def _ao_mover_mouse(self, evento):
        """Troca o cursor: mover (anotação), texto (palavra ou modo texto) ou seta."""
        if not self.documento:
            cursor = "hand2"
        elif self.movendo_pagina:
            return
        else:
            x, y = self._posicao_na_tela(evento)
            local = self.ponto_na_pagina(x, y)
            if self.anotacao_no_ponto(x, y):
                cursor = "fleur"
            elif local and (self.modo_texto or self.palavra_no_ponto(*local, exata=True) is not None):
                cursor = "xterm"
            else:
                cursor = ""
        if str(self.tela.cget("cursor")) != cursor:
            self.tela.config(cursor=cursor)

    # ------------------------------------------------------------------ arrastar a página
    def _iniciar_movimento_pagina(self, evento):
        self.tela.scan_mark(evento.x, evento.y)
        self.movendo_pagina = True
        self.tela.config(cursor="fleur")

    def _mover_pagina(self, evento):
        if self.movendo_pagina:
            self.tela.scan_dragto(evento.x, evento.y, gain=1)
            self.agendar_renderizacao()

    def _encerrar_movimento_pagina(self, evento):
        if self.movendo_pagina:
            self.movendo_pagina = False
            self._ao_mover_mouse(evento)

    # ------------------------------------------------------------------ menu de contexto
    def _criar_menu(self):
        return tk.Menu(self, tearoff=0, bg=COR_BARRA, fg=COR_TEXTO, activebackground=COR_PASSAR_MOUSE,
                       activeforeground=COR_TEXTO, bd=0, relief="flat", font=fontes.interface)

    def _ao_clicar_direito(self, evento):
        if not self.documento:
            return
        x, y = self._posicao_na_tela(evento)
        menu = self._criar_menu()
        anotacao = self.anotacao_no_ponto(x, y)
        if self.selecao_texto and not anotacao:
            menu.add_command(label="Copiar", accelerator="Ctrl+C", command=self.copiar_selecao)
            menu.add_separator()
        if anotacao:
            self.anotacao_selecionada = anotacao
            self.desenhar_sobreposicoes()
            menu.add_command(label="Editar texto…", command=lambda: self.editar_anotacao(*anotacao))
            menu_cores = self._criar_menu()
            for nome, cor in CORES_ANOTACAO.items():
                menu_cores.add_command(label=f"●  {nome}", foreground=cor if cor != "#000000" else COR_TEXTO,
                                       command=lambda cor=cor: self.alterar_anotacao_selecionada(cor=cor))
            menu_cores.add_separator()
            menu_cores.add_command(label="Outra cor…", command=lambda: self.escolher_outra_cor(so_na_selecionada=True))
            menu.add_cascade(label="Cor", menu=menu_cores)
            menu.add_separator()
            menu.add_command(label="Excluir", command=self.excluir_anotacao_selecionada)
        else:
            local = self.ponto_na_pagina(x, y)
            if local:
                menu.add_command(label="Adicionar anotação de texto aqui", command=lambda: self.nova_anotacao(*local))
            elif not self.selecao_texto:
                return
        menu.tk_popup(evento.x_root, evento.y_root)

    # ------------------------------------------------------------------ teclado
    def _ao_pressionar_esc(self):
        """Esc desfaz, em ordem: seleção → modo texto → tela cheia → busca."""
        if self.anotacao_selecionada or self.selecao_texto:
            self.anotacao_selecionada = self.selecao_texto = None
            self.desenhar_sobreposicoes()
        elif self.modo_texto:
            self.alternar_modo_texto()
        elif self.tela_cheia:
            self.alternar_tela_cheia(False)
        elif self.termo_busca:
            self.limpar_busca()

    def alternar_modo_texto(self):
        self.modo_texto = not self.modo_texto
        self.atualizar_botoes()
        if self.modo_texto:
            self.avisar("Modo texto: clique na página para escrever · Esc para sair")
        self.tela.focus_set()
