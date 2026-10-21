"""Impressão: diálogo padrão do Windows e acompanhamento do processo que envia as páginas."""

import multiprocessing
import os

import pymupdf

from pdf_leve.configuracao.constantes import INTERVALO_VERIFICACAO_IMPRESSAO_MS
from pdf_leve.servicos.impressao import paginas_selecionadas, processo_impressor
from pdf_leve.sistema.impressora import escolher_impressora


class MixinImpressao:

    def imprimir(self):
        """Imprime o documento como está na tela, inclusive com anotações e rotações não salvas."""
        if not self.documento:
            return
        if self.impressao:
            cancelar = self.perguntar("Imprimir", "Uma impressão deste documento ainda está em andamento.",
                                      [("Cancelar a impressão", True, False), ("Continuar", False, True)], False)
            if cancelar and self.impressao:
                try:
                    self.impressao[0].send("cancelar")
                except (EOFError, OSError):
                    pass
            return
        if not self.documento.permissions & pymupdf.PDF_PERM_PRINT:
            self.mostrar_erro("O autor deste PDF não permite que ele seja impresso.")
            return
        total, atual = len(self.documento), self.pagina_atual()
        try:
            escolha = escolher_impressora(self, total, atual)
        except OSError as erro:
            self.mostrar_erro(f"Não foi possível abrir o diálogo de impressão:\n{erro}")
            return
        finally:
            self.tela.focus_set()
        if not escolha:
            return
        paginas = paginas_selecionadas(escolha.intervalos, escolha.apenas_atual, total, atual)
        if not paginas:
            return
        try:
            origem = self.documento.tobytes() if self.modificado else self.caminho
            contexto = multiprocessing.get_context("spawn")
            local, remota = contexto.Pipe()
            processo = contexto.Process(target=processo_impressor, args=(
                remota, origem, self.senha, escolha.impressora, escolha.devmode, paginas,
                os.path.basename(self.caminho)))
            processo.start()
            remota.close()
        except Exception as erro:
            self.mostrar_erro(f"Erro ao imprimir:\n{erro}")
            return
        self.impressao = (local, processo)
        self.avisar("Preparando a impressão…")
        self.after(INTERVALO_VERIFICACAO_IMPRESSAO_MS, self._acompanhar_impressao)

    def _acompanhar_impressao(self):
        if not self.impressao:
            return
        conexao = self.impressao[0]
        try:
            while conexao.poll():
                mensagem = conexao.recv()
                if mensagem[0] == "progresso":
                    self.avisar(f"Imprimindo página {mensagem[1]} de {mensagem[2]}…")
                else:
                    self._encerrar_impressao(mensagem)
                    return
        except (EOFError, OSError):
            self._encerrar_impressao(("erro", "O processo de impressão terminou inesperadamente."))
            return
        self.after(INTERVALO_VERIFICACAO_IMPRESSAO_MS, self._acompanhar_impressao)

    def _encerrar_impressao(self, mensagem):
        self.abandonar_impressao()
        if mensagem[0] == "concluido":
            self.avisar("Enviado para a impressora")
        elif mensagem[0] == "cancelado":
            self.avisar("Impressão cancelada")
        else:
            self.mostrar_erro(f"Erro ao imprimir:\n{mensagem[1]}")

    def abandonar_impressao(self):
        """Deixa de acompanhar a impressão; se ela não terminou, continua sem informar o progresso."""
        if self.impressao:
            self.impressao[0].close()
            self.impressao = None
