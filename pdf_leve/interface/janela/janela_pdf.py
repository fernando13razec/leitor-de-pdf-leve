"""JanelaPdf: uma janela com um PDF. Todas as janelas pertencem ao mesmo Aplicativo (um só processo)."""

import re
import tkinter as tk

from pdf_leve.configuracao.constantes import (
    COR_ANOTACAO_PADRAO, NOME_APLICATIVO, TAMANHO_FONTE_PADRAO,
)
from pdf_leve.configuracao.tema import COR_FUNDO
from pdf_leve.interface.janela.anotacoes import MixinAnotacoes
from pdf_leve.interface.janela.arquivo import MixinArquivo
from pdf_leve.interface.janela.barra_ferramentas import MixinBarraFerramentas
from pdf_leve.interface.janela.busca import MixinBusca
from pdf_leve.interface.janela.impressao import MixinImpressao
from pdf_leve.interface.janela.mouse import MixinMouse
from pdf_leve.interface.janela.selecao_texto import MixinSelecaoTexto
from pdf_leve.interface.janela.visualizacao import MixinVisualizacao
from pdf_leve.sistema.windows import aceitar_arquivos_arrastados, barra_titulo_escura

DESLOCAMENTO_CASCATA = 32  # px entre janelas abertas em sequência


class JanelaPdf(MixinBarraFerramentas, MixinArquivo, MixinVisualizacao, MixinMouse,
                MixinSelecaoTexto, MixinAnotacoes, MixinBusca, MixinImpressao, tk.Toplevel):

    def __init__(self, aplicativo, caminho=None, perto_de=None, aberto=None, ancora=None):
        """Abre `caminho` ou, com `aberto`, mais uma vista de um documento já aberto (em `ancora`)."""
        super().__init__(aplicativo)
        self.withdraw()
        self.aplicativo = aplicativo
        self.preferencias = aplicativo.preferencias
        self.fechada = False
        self.title(NOME_APLICATIVO)
        self.configure(bg=COR_FUNDO)
        self._definir_geometria(perto_de)

        # documento (compartilhado com as outras janelas que exibem o mesmo arquivo)
        self.aberto = None                # DocumentoAberto
        self.impressao = None             # (conexão, processo) da impressão em andamento nesta janela

        # visualização e renderização
        self.zoom = self.preferencias.get("zoom", 1.0)
        self.modo_ajuste = self.preferencias.get("ajuste", "largura")  # "largura", "pagina" ou None
        self.escala_base = self.winfo_fpixels("1i") / 72  # pixels por ponto PDF a 100%
        self.disposicao = []              # (x, y, largura, altura) de cada página na tela
        self.largura_total = self.altura_total = 1
        self.itens_na_tela = {}           # página -> (chave, item do canvas, PhotoImage)
        self.fila_pedidos = []            # (chave, página) por prioridade
        self._ultima_primeira_visivel = 0
        self._navegacao = None            # (página, posição) do último salto de página
        self._tarefa_renderizar = self._tarefa_redimensionar = self._tarefa_aviso = None
        self._ultimo_tamanho = (0, 0)
        self.tela_cheia = False

        # interação
        self.modo_texto = False
        self.cor = self.preferencias.get("cor", COR_ANOTACAO_PADRAO)
        self.tamanho_fonte = int(self.preferencias.get("tamanho_fonte", TAMANHO_FONTE_PADRAO))
        self.anotacao_selecionada = None  # (página, xref)
        self.arraste = None               # anotação sendo movida
        self.movendo_pagina = False
        self.painel_estilo = None
        self.selecao_texto = None         # ((página, palavra), (página, palavra))
        self.selecionando = None
        self._imagens_selecao = {}
        self.geracao_busca = 0
        self._zerar_busca()

        self._montar_interface()
        self._ligar_atalhos()
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        barra_titulo_escura(self)
        self.deiconify()
        aceitar_arquivos_arrastados(self, self.ao_soltar_arquivos)
        if aberto:
            self.after(60, lambda: self.exibir(aberto, ancora))
        elif caminho:
            self.after(60, lambda: self.carregar(caminho))

    def _definir_geometria(self, perto_de):
        largura_tela, altura_tela = self.winfo_screenwidth(), self.winfo_screenheight()
        padrao = f"{min(1100, largura_tela - 80)}x{min(950, altura_tela - 140)}+40+20"
        geometria = self.preferencias.get("geometria", padrao)
        if perto_de is not None and not perto_de.fechada:  # novas janelas em cascata
            partes = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", perto_de.geometry())
            if partes and perto_de.state() != "zoomed":
                largura, altura, x, y = map(int, partes.groups())
                cabe = x + largura + DESLOCAMENTO_CASCATA < largura_tela and y + altura + DESLOCAMENTO_CASCATA < altura_tela
                x, y = (x + DESLOCAMENTO_CASCATA, y + DESLOCAMENTO_CASCATA) if cabe else (40, 20)
                geometria = f"{largura}x{altura}+{x}+{y}"
        self.geometry(geometria)  # tamanho usado ao sair do modo maximizado
        self.state("zoomed")  # toda janela abre maximizada
        self.minsize(560, 400)

    @property
    def renderizadores(self):
        return self.aplicativo.renderizadores

    # Estado do documento, lido do DocumentoAberto (é o mesmo em todas as vistas do arquivo).
    def _do_documento(nome, vazio):
        def ler(self):
            return getattr(self.aberto, nome) if self.aberto else vazio()
        return property(ler)

    documento = _do_documento("documento", lambda: None)
    caminho = _do_documento("caminho", lambda: None)
    senha = _do_documento("senha", lambda: None)
    modificado = _do_documento("modificado", lambda: False)
    id_documento = _do_documento("id_documento", lambda: 0)
    versao_pagina = _do_documento("versao_pagina", list)
    retangulos_paginas = _do_documento("retangulos_paginas", list)
    paginas_locais = _do_documento("paginas_locais", set)
    cache_palavras = _do_documento("cache_palavras", dict)
    cache_imagens = _do_documento("cache_imagens", dict)
    em_renderizacao = _do_documento("em_renderizacao", set)
    del _do_documento

    # Os temporizadores ficam no Aplicativo: um temporizador pendente de uma janela já fechada
    # simplesmente não roda (em vez de gerar erro do Tk). Os nomes seguem a API do tkinter.
    def after(self, ms, func=None, *args):
        if func is None:
            return self.aplicativo.after(ms)

        def executar(*argumentos):
            if not self.fechada:
                func(*argumentos)
        return self.aplicativo.after(ms, executar, *args)

    def after_cancel(self, tarefa):
        self.aplicativo.after_cancel(tarefa)
