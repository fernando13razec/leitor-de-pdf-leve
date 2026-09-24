"""Anotações na janela: criar, editar, mover, recolorir e excluir; cor e tamanho atuais."""

from tkinter import colorchooser

from pdf_leve.interface.dialogos import DialogoAnotacao, PainelEstilo
from pdf_leve.servicos.anotacoes import (
    anotacoes_de_texto, aplicar_anotacao, criar_anotacao, encaixar_caixa_texto, ler_propriedades,
    retangulo_exibido,
)

TOLERANCIA_CLIQUE = 2  # pontos PDF ao redor da anotação que ainda contam como clique nela


class MixinAnotacoes:

    def obter_anotacao(self, pagina, xref):
        """(página do PyMuPDF, anotação) ou None se ela não existir mais."""
        try:
            pagina_pdf = self.documento[pagina]
            anotacao = pagina_pdf.load_annot(xref)
        except Exception:
            return None
        return (pagina_pdf, anotacao) if anotacao else None

    def anotacao_no_ponto(self, x_tela, y_tela):
        """(página, xref) da anotação de texto sob o ponto do canvas, ou None."""
        local = self.ponto_na_pagina(x_tela, y_tela)
        if not local:
            return None
        pagina, ponto = local
        pagina_pdf = self.documento[pagina]
        encontrada = None
        margem = (-TOLERANCIA_CLIQUE, -TOLERANCIA_CLIQUE, TOLERANCIA_CLIQUE, TOLERANCIA_CLIQUE)
        for anotacao in anotacoes_de_texto(pagina_pdf):
            if ponto in retangulo_exibido(pagina_pdf, anotacao) + margem:
                encontrada = (pagina, anotacao.xref)  # a última da lista é a que fica por cima
        return encontrada

    def _anotacao_alterada(self, pagina, xref):
        self.anotacao_selecionada = (pagina, xref)
        self.marcar_modificado()
        self.invalidar(pagina)

    def nova_anotacao(self, pagina, ponto):
        dialogo = DialogoAnotacao(self, "Nova anotação", cor=self.cor, tamanho=self.tamanho_fonte)
        self.tela.focus_set()
        if not dialogo.resultado:
            return
        texto, cor, tamanho = dialogo.resultado
        self.cor, self.tamanho_fonte = cor, tamanho
        self.atualizar_botao_cor()
        pagina_pdf = self.documento[pagina]
        # o texto começa um pouco acima e à esquerda do clique, como num editor
        retangulo = encaixar_caixa_texto(pagina_pdf, ponto.x - 3, ponto.y - tamanho * 0.6, texto, tamanho)
        anotacao = criar_anotacao(pagina_pdf, retangulo, texto, cor, tamanho)
        self._anotacao_alterada(pagina, anotacao.xref)

    def editar_anotacao(self, pagina, xref):
        encontrada = self.obter_anotacao(pagina, xref)
        if not encontrada:
            return
        texto, cor, tamanho = ler_propriedades(self.documento, encontrada[1])
        dialogo = DialogoAnotacao(self, "Editar anotação", texto, cor, tamanho)
        self.tela.focus_set()
        if dialogo.resultado:
            self.aplicar_na_anotacao(pagina, xref, *dialogo.resultado)

    def aplicar_na_anotacao(self, pagina, xref, texto, cor, tamanho, retangulo=None):
        """Altera a anotação; sem `retangulo`, mantém o canto superior esquerdo e reajusta o tamanho."""
        encontrada = self.obter_anotacao(pagina, xref)
        if not encontrada:
            return
        pagina_pdf, anotacao = encontrada
        if retangulo is None:
            atual = retangulo_exibido(pagina_pdf, anotacao)
            retangulo = encaixar_caixa_texto(pagina_pdf, atual.x0, atual.y0, texto, tamanho)
        aplicar_anotacao(pagina_pdf, anotacao, texto, cor, tamanho, retangulo)
        self._anotacao_alterada(pagina, xref)

    def alterar_anotacao_selecionada(self, cor=None, tamanho=None):
        if not self.anotacao_selecionada:
            return
        encontrada = self.obter_anotacao(*self.anotacao_selecionada)
        if not encontrada:
            return
        texto, cor_atual, tamanho_atual = ler_propriedades(self.documento, encontrada[1])
        self.aplicar_na_anotacao(*self.anotacao_selecionada, texto, cor or cor_atual, tamanho or tamanho_atual)

    def excluir_anotacao_selecionada(self):
        if not self.anotacao_selecionada:
            return
        encontrada = self.obter_anotacao(*self.anotacao_selecionada)
        if encontrada:
            pagina_pdf, anotacao = encontrada
            pagina_pdf.delete_annot(anotacao)
            self.marcar_modificado()
            self.invalidar(self.anotacao_selecionada[0])
        self.anotacao_selecionada = None
        self.desenhar_sobreposicoes()

    # ------------------------------------------------------------------ cor e tamanho
    def alternar_painel_estilo(self):
        if self.painel_estilo:
            self.painel_estilo.fechar()
        else:
            self.painel_estilo = PainelEstilo(self, self.botao_cor)

    def escolher_cor(self, cor):
        """Define a cor das próximas anotações (e da selecionada, se houver)."""
        self.cor = cor
        self.atualizar_botao_cor()
        if self.anotacao_selecionada:
            self.alterar_anotacao_selecionada(cor=cor)

    def definir_tamanho(self, tamanho):
        self.tamanho_fonte = tamanho
        if self.anotacao_selecionada:
            self.alterar_anotacao_selecionada(tamanho=tamanho)

    def escolher_outra_cor(self, so_na_selecionada=False):
        cor = colorchooser.askcolor(self.cor, parent=self, title="Cor do texto")[1]
        if not cor:
            return
        if so_na_selecionada:
            self.alterar_anotacao_selecionada(cor=cor)
        else:
            self.escolher_cor(cor)
