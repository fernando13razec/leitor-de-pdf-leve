"""Operações com o arquivo: abrir (também numa nova janela), salvar, salvar como, exportar páginas,
girar e fechar a janela. O documento é compartilhado pelas janelas que o exibem (DocumentoAberto)."""

import os
from tkinter import filedialog

import pymupdf

from pdf_leve.configuracao.constantes import NOME_APLICATIVO
from pdf_leve.configuracao.preferencias import salvar_preferencias
from pdf_leve.interface.dialogos import DialogoExportacao
from pdf_leve.interface.documento_aberto import DocumentoAberto
from pdf_leve.interface.utilidades import plural, trazer_para_frente
from pdf_leve.servicos.intervalos import agrupar_sequencias

TIPOS_PDF = [("Arquivos PDF", "*.pdf")]


class MixinArquivo:

    # ------------------------------------------------------------------ abrir
    def ao_soltar_arquivos(self, arquivos):
        pdfs = [arquivo for arquivo in arquivos if arquivo.lower().endswith(".pdf")]
        if not pdfs:
            self.avisar("Solte um arquivo PDF")
            return
        self.aplicativo.abrir_arquivos(pdfs, origem=self)

    def abrir_arquivo(self):
        caminhos = filedialog.askopenfilenames(
            parent=self, title="Abrir PDF", initialdir=self.preferencias.get("ultima_pasta") or None,
            filetypes=TIPOS_PDF + [("Todos os arquivos", "*.*")])
        if caminhos:
            self.aplicativo.abrir_arquivos(list(caminhos), origem=self)

    def carregar(self, caminho):
        """Abre o PDF nesta janela."""
        aberto = DocumentoAberto.abrir(self.aplicativo, caminho, self)
        if aberto:
            self.preferencias["ultima_pasta"] = os.path.dirname(aberto.caminho)
            self.exibir(aberto)

    def exibir(self, aberto, ancora=None):
        """Mostra nesta janela um documento aberto (talvez já exibido em outras janelas).
        `ancora` preserva a posição (usado ao recarregar e ao abrir uma nova vista)."""
        if not aberto.documento:
            return  # o documento foi fechado antes de a janela ficar pronta
        if self.aberto is not aberto:
            if self.aberto:
                self.aberto.desanexar(self)
            self.aberto = aberto
            aberto.anexar(self)
        self.anotacao_selecionada = None
        self.selecao_texto = None
        self.fila_pedidos = []
        self.limpar_busca(focar=False)
        self.rotulo_total.config(text=f"/ {len(self.documento)}")
        self.update_idletasks()
        if self.modo_ajuste:
            self.zoom = self.zoom_de_ajuste(self.modo_ajuste, ancora[0] if ancora else 0)
        self.montar_disposicao(ancora)
        if ancora is None:
            self.tela.xview_moveto(0)
            self.ir_para_pagina(0)
        self.atualizar_titulo()
        self.tela.focus_set()

    def abrir_em_nova_janela(self):
        """Mais uma janela com este mesmo PDF, na mesma página e no mesmo zoom."""
        if not self.documento:
            return
        janela = self.aplicativo.nova_janela(perto_de=self, aberto=self.aberto, ancora=self.criar_ancora(0, 0))
        janela.zoom, janela.modo_ajuste = self.zoom, self.modo_ajuste
        janela.atualizar_botoes()
        trazer_para_frente(janela)

    # ------------------------------------------------------------------ salvar
    def salvar(self):
        """Salva o documento (vale para todas as janelas que o exibem)."""
        if not self.documento:
            return False
        try:
            self.aberto.salvar()
        except Exception as erro:
            self.mostrar_erro(f"Erro ao salvar:\n{erro}\n\nTente “Salvar como” (Ctrl+Shift+S).")
            return False
        self.avisar("Salvo")
        return True

    def salvar_como(self):
        if not self.documento:
            return False
        destino = filedialog.asksaveasfilename(
            parent=self, title="Salvar como", defaultextension=".pdf", initialdir=os.path.dirname(self.caminho),
            initialfile=os.path.basename(self.caminho), filetypes=TIPOS_PDF)
        if not destino:
            return False
        if os.path.abspath(destino) == self.caminho:
            return self.salvar()
        try:
            self.aberto.salvar_como(destino)
        except Exception as erro:
            self.mostrar_erro(f"Erro ao salvar:\n{erro}")
            return False
        self.avisar("Salvo")
        return True

    def exportar_paginas(self):
        """Salva um intervalo de páginas (com as anotações atuais, mesmo não salvas) num novo PDF."""
        if not self.documento:
            return
        dialogo = DialogoExportacao(self, len(self.documento), self.pagina_atual())
        self.tela.focus_set()
        if not dialogo.resultado:
            return
        paginas, rotulo = dialogo.resultado
        nome_base = os.path.splitext(os.path.basename(self.caminho))[0]
        sufixo = f" (p. {rotulo})" if rotulo else " (cópia)"
        destino = filedialog.asksaveasfilename(
            parent=self, title="Salvar páginas", defaultextension=".pdf", initialdir=os.path.dirname(self.caminho),
            initialfile=nome_base + sufixo + ".pdf", filetypes=TIPOS_PDF)
        if not destino:
            return
        if os.path.abspath(destino) == self.caminho:
            self.mostrar_erro("Escolha outro nome: o arquivo aberto não pode ser substituído por este recorte.")
            return
        try:
            novo = pymupdf.open()
            for inicio, fim in agrupar_sequencias(paginas):
                novo.insert_pdf(self.documento, from_page=inicio, to_page=fim)
            novo.save(destino, garbage=3, deflate=True)
            novo.close()
        except Exception as erro:
            self.mostrar_erro(f"Erro ao salvar:\n{erro}")
            return
        self.avisar(f"{plural(len(paginas), 'página salva', 'páginas salvas')} em “{os.path.basename(destino)}”",
                    3500)

    # ------------------------------------------------------------------ girar
    def girar(self, graus, todas=False):
        """Gira a página atual (ou todas) em 90°; a rotação é gravada no PDF ao salvar."""
        if not self.documento:
            return
        atual = self.pagina_atual()
        for indice in range(len(self.documento)) if todas else [atual]:
            pagina = self.documento[indice]
            pagina.set_rotation((pagina.rotation + graus) % 360)
            self.retangulos_paginas[indice] = pagina.rect
            self.versao_pagina[indice] += 1
            self.renderizadores.enviar_a_todos(("girar", self.id_documento, indice, pagina.rotation))
        self.marcar_modificado()
        self.aberto.disposicao_alterada()  # refaz a disposição em todas as janelas do documento
        self.avisar("Todas as páginas giradas" if todas else f"Página {atual + 1} girada")

    # ------------------------------------------------------------------ fechar
    def confirmar_descarte(self):
        """Pergunta se deve salvar alterações pendentes (só na última janela do documento).
        Retorna False se o usuário cancelar."""
        if not self.modificado or len(self.aberto.janelas) > 1:
            return True
        resposta = self.perguntar(
            NOME_APLICATIVO, f"Salvar as alterações em “{os.path.basename(self.caminho)}”?",
            [("Não salvar", "nao", False), ("Cancelar", None, False), ("Salvar", "sim", True)], "sim")
        if resposta is None:
            return False
        return self.salvar() if resposta == "sim" else True

    def fechar(self):
        """Fecha esta janela (o programa termina quando a última é fechada)."""
        if not self.confirmar_descarte():
            return
        if self.tela_cheia:
            self.alternar_tela_cheia(False)
            self.update_idletasks()
        if self.state() != "zoomed":
            self.preferencias["geometria"] = self.geometry()
        self.preferencias.pop("maximizada", None)  # obsoleta: as janelas sempre abrem maximizadas
        self.preferencias.update(cor=self.cor, tamanho_fonte=self.tamanho_fonte,
                                 ajuste=self.modo_ajuste, zoom=self.zoom)
        salvar_preferencias(self.preferencias)
        self.geracao_busca += 1
        self.fechada = True
        if self.painel_estilo:
            self.painel_estilo.fechar()
        if self.aberto:
            self.aberto.desanexar(self)  # a última janela fecha o documento
            self.aberto = None
        self.itens_na_tela.clear()
        self.destroy()
        self.aplicativo.janela_fechada(self)
