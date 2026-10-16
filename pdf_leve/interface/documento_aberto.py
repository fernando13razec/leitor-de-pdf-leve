"""DocumentoAberto: um PDF aberto no programa, compartilhado por todas as janelas que o exibem.

O mesmo arquivo pode estar em várias janelas (vistas). O documento do PyMuPDF, as alterações
ainda não salvas (anotações, rotações), o estado de modificado e o cache de páginas prontas são
do documento; rolagem, zoom, busca e seleções são de cada janela. Toda alteração feita numa vista
é avisada às outras.
"""

import os
from collections import OrderedDict
from tkinter import simpledialog

import pymupdf

from pdf_leve.configuracao.constantes import LIMITE_PIXELS_CACHE, NOME_APLICATIVO
from pdf_leve.interface.utilidades import imagem_ppm


class DocumentoAberto:

    def __init__(self, aplicativo, documento, caminho, senha):
        self.aplicativo = aplicativo
        self.janelas = []                 # vistas que exibem o documento, na ordem em que abriram
        self.modificado = False
        self._definir(documento, caminho, senha)

    @classmethod
    def abrir(cls, aplicativo, caminho, janela):
        """Abre o PDF (pedindo a senha, se preciso). Em caso de erro, avisa em `janela` e retorna None."""
        try:
            documento = pymupdf.open(caminho)
        except Exception as erro:
            janela.mostrar_erro(f"Não foi possível abrir o arquivo:\n{erro}")
            return None
        senha = None
        if documento.needs_pass:
            senha = simpledialog.askstring(NOME_APLICATIVO, "Este PDF é protegido. Senha:", show="*", parent=janela)
            if not senha or not documento.authenticate(senha):
                documento.close()
                janela.mostrar_erro("Senha incorreta ou não informada.")
                return None
        if documento.page_count == 0:
            documento.close()
            janela.mostrar_erro("O arquivo não tem páginas.")
            return None
        return cls(aplicativo, documento, caminho, senha)

    def _definir(self, documento, caminho, senha):
        self.documento = documento
        self.caminho = os.path.abspath(caminho)
        self.senha = senha
        self.id_documento = self.aplicativo.proximo_id_documento()  # único; descarta resultados antigos
        self.versao_pagina = [0] * len(documento)  # muda ao girar/anotar (invalida a imagem da página)
        self.retangulos_paginas = [pagina.rect for pagina in documento]
        self.paginas_locais = set()       # anotadas e ainda não salvas: renderizadas no processo da interface
        self.cache_palavras = OrderedDict()  # página -> palavras (texto selecionável)
        self.cache_imagens = OrderedDict()   # chave -> PhotoImage (LRU)
        self.pixels_em_cache = 0
        self.em_renderizacao = set()      # chaves pedidas aos processos auxiliares
        self.renderizadores.enviar_a_todos(("abrir", self.id_documento, self.caminho, self.senha))

    @property
    def renderizadores(self):
        return self.aplicativo.renderizadores

    # ------------------------------------------------------------------ vistas
    def anexar(self, janela):
        if janela not in self.janelas:
            self.janelas.append(janela)
            self._atualizar_titulos()

    def desanexar(self, janela):
        """A janela deixou de exibir o documento; com a última, o documento é fechado."""
        if janela in self.janelas:
            self.janelas.remove(janela)
        if self.janelas:
            self._atualizar_titulos()
        elif self.documento:
            self.renderizadores.enviar_a_todos(("descartar", self.id_documento))
            self.documento.close()
            self.documento = None
            self.cache_imagens.clear()

    def _atualizar_titulos(self):
        for janela in self.janelas:
            janela.atualizar_titulo()

    # ------------------------------------------------------------------ alterações
    def marcar_modificado(self, modificado=True):
        self.modificado = modificado
        self._atualizar_titulos()

    def paginas_alteradas(self, pagina):
        """A página mudou (anotação): passa a ser renderizada localmente até o arquivo ser salvo."""
        self.versao_pagina[pagina] += 1
        self.paginas_locais.add(pagina)
        for janela in self.janelas:
            janela.agendar_renderizacao()

    def disposicao_alterada(self):
        """Páginas mudaram de tamanho (rotação): cada vista refaz a disposição."""
        for janela in self.janelas:
            janela.refazer_por_rotacao()

    # ------------------------------------------------------------------ salvar
    def salvar(self):
        """Grava as alterações no próprio arquivo. Erros são repassados a quem chamou."""
        if self.documento.can_save_incrementally():
            self.documento.saveIncr()
            # os processos auxiliares relêem o arquivo, que agora contém as alterações
            self.renderizadores.enviar_a_todos(("abrir", self.id_documento, self.caminho, self.senha))
            self.paginas_locais.clear()
        else:
            ancoras = self._ancoras()
            temporario = self.caminho + ".tmp"
            self.documento.save(temporario, garbage=3, deflate=True)
            self.renderizadores.fechar_documento(self.id_documento)  # o Windows não substitui arquivos abertos
            self.documento.close()
            self.documento = None
            try:
                os.replace(temporario, self.caminho)
            finally:
                self._reabrir(self.caminho, ancoras)
        self.marcar_modificado(False)

    def salvar_como(self, destino):
        """Grava uma cópia em `destino`, que passa a ser o arquivo exibido por todas as vistas."""
        ancoras = self._ancoras()
        self.documento.save(destino, garbage=3, deflate=True)
        self.renderizadores.enviar_a_todos(("descartar", self.id_documento))
        self.documento.close()
        self.documento = None
        self._reabrir(destino, ancoras)
        self.marcar_modificado(False)

    def _ancoras(self):
        return [(janela, janela.criar_ancora(0, 0)) for janela in self.janelas]

    def _reabrir(self, caminho, ancoras):
        """Lê o arquivo de novo e o exibe em todas as vistas, cada uma na posição em que estava."""
        documento = pymupdf.open(caminho)
        if documento.needs_pass:
            documento.authenticate(self.senha or "")
        self._definir(documento, caminho, self.senha)
        for janela, ancora in ancoras:
            if not janela.fechada:
                janela.exibir(self, ancora)

    # ------------------------------------------------------------------ cache de páginas
    def guardar_no_cache(self, chave, imagem):
        self.cache_imagens[chave] = imagem
        self.pixels_em_cache += imagem.width() * imagem.height()
        while self.pixels_em_cache > LIMITE_PIXELS_CACHE and len(self.cache_imagens) > 1:
            _, antiga = self.cache_imagens.popitem(last=False)
            self.pixels_em_cache -= antiga.width() * antiga.height()

    def receber_imagem(self, chave, largura, altura, amostras):
        """Página pronta vinda de um processo auxiliar: guarda no cache uma vez e a oferece a
        todas as vistas. Retorna as janelas que a colocaram na tela."""
        if not self.documento or chave[0] != self.id_documento:
            return []
        imagem = imagem_ppm(largura, altura, amostras)
        self.guardar_no_cache(chave, imagem)
        return [janela for janela in self.janelas if janela.posicionar_se_visivel(chave, imagem)]
