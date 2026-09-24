"""Aplicativo: raiz invisível do Tk que gerencia as janelas (uma por PDF), os processos de
renderização compartilhados e os arquivos recebidos de novas execuções do programa."""

import os
import tkinter as tk

from pdf_leve.configuracao.constantes import ICONE_ICO, ICONE_PNG, PROCESSOS_RENDERIZACAO
from pdf_leve.configuracao.preferencias import carregar_preferencias
from pdf_leve.configuracao.tema import iniciar_fontes
from pdf_leve.interface.janela import JanelaPdf
from pdf_leve.interface.utilidades import trazer_para_frente
from pdf_leve.servicos.instancia_unica import ouvir_novas_instancias
from pdf_leve.servicos.renderizacao import ConjuntoRenderizadores


class Aplicativo(tk.Tk):

    def __init__(self):
        super().__init__()
        self.withdraw()
        iniciar_fontes(self)
        self._definir_icone()
        self.preferencias = carregar_preferencias()
        self.janelas = []
        self._ultimo_id_documento = 0
        self.renderizadores = ConjuntoRenderizadores(self, PROCESSOS_RENDERIZACAO)
        self.servidor = ouvir_novas_instancias(self)

    def _definir_icone(self):
        """Ícone de todas as janelas (o .ico tem várias resoluções; o PNG é a alternativa)."""
        try:
            self.iconbitmap(default=str(ICONE_ICO))
        except tk.TclError:
            try:
                self._icone = tk.PhotoImage(file=str(ICONE_PNG))
                self.iconphoto(True, self._icone)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ documentos e janelas
    def proximo_id_documento(self):
        self._ultimo_id_documento += 1
        return self._ultimo_id_documento

    def janela_do_documento(self, id_documento):
        return next((janela for janela in self.janelas if janela.id_documento == id_documento), None)

    def janelas_por_prioridade(self):
        """A janela em foco primeiro: a página que o usuário está lendo é renderizada antes."""
        foco = self.focus_get()
        janela_em_foco = foco.winfo_toplevel() if foco else None
        return sorted(self.janelas, key=lambda janela: janela is not janela_em_foco)

    def nova_janela(self, caminho=None, perto_de=None):
        janela = JanelaPdf(self, caminho, perto_de)
        self.janelas.append(janela)
        return janela

    def abrir_arquivos(self, caminhos, origem=None):
        """Abre cada PDF numa janela nova (ou na janela de origem, se ela estiver vazia).
        Um arquivo que já está aberto apenas traz a janela dele para a frente.
        Sem caminhos, abre uma janela vazia."""
        if not caminhos:
            trazer_para_frente(self.nova_janela(perto_de=origem))
            return
        for caminho in caminhos:
            caminho = os.path.abspath(caminho)
            janela = self._janela_do_arquivo(caminho)
            if janela:
                trazer_para_frente(janela)
                continue
            if origem is not None and not origem.fechada and origem.documento is None:
                origem.carregar(caminho)
                janela, origem = origem, None
            else:
                vizinha = origem or (self.janelas[-1] if self.janelas else None)
                janela = self.nova_janela(caminho, perto_de=vizinha)
            trazer_para_frente(janela)

    def _janela_do_arquivo(self, caminho):
        normalizado = os.path.normcase(caminho)
        return next((janela for janela in self.janelas
                     if janela.caminho and os.path.normcase(janela.caminho) == normalizado), None)

    def janela_fechada(self, janela):
        if janela in self.janelas:
            self.janelas.remove(janela)
        if not self.janelas:
            self.renderizadores.encerrar()
            if self.servidor:
                self.servidor.close()
            self.destroy()
