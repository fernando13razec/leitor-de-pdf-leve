"""Operações com o arquivo: abrir, salvar, salvar como, exportar páginas, girar e fechar a janela."""

import os
from tkinter import filedialog, simpledialog

import pymupdf

from pdf_leve.configuracao.constantes import NOME_APLICATIVO
from pdf_leve.configuracao.preferencias import salvar_preferencias
from pdf_leve.interface.dialogos import DialogoExportacao
from pdf_leve.interface.utilidades import plural
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

    def carregar(self, caminho, ancora=None):
        """Abre o PDF nesta janela. `ancora` preserva a posição (usado ao recarregar)."""
        try:
            documento = pymupdf.open(caminho)
        except Exception as erro:
            self.mostrar_erro(f"Não foi possível abrir o arquivo:\n{erro}")
            return
        senha = None
        if documento.needs_pass:
            senha = simpledialog.askstring(NOME_APLICATIVO, "Este PDF é protegido. Senha:", show="*", parent=self)
            if not senha or not documento.authenticate(senha):
                documento.close()
                self.mostrar_erro("Senha incorreta ou não informada.")
                return
        if documento.page_count == 0:
            documento.close()
            self.mostrar_erro("O arquivo não tem páginas.")
            return
        if self.documento:
            self.documento.close()
            self.renderizadores.enviar_a_todos(("descartar", self.id_documento))

        self.documento = documento
        self.caminho = os.path.abspath(caminho)
        self.senha = senha
        self.preferencias["ultima_pasta"] = os.path.dirname(self.caminho)
        self.modificado = False
        self.anotacao_selecionada = None
        self.selecao_texto = None
        self.id_documento = self.aplicativo.proximo_id_documento()
        self.versao_pagina = [0] * len(documento)
        self.paginas_locais.clear()
        self.cache_imagens.clear()
        self.pixels_em_cache = 0
        self.em_renderizacao.clear()
        self.fila_pedidos = []
        self.cache_palavras.clear()
        self.renderizadores.enviar_a_todos(("abrir", self.id_documento, self.caminho, self.senha))
        self.limpar_busca(focar=False)
        self.retangulos_paginas = [pagina.rect for pagina in documento]
        self.rotulo_total.config(text=f"/ {len(documento)}")
        self.update_idletasks()
        if ancora is None and self.modo_ajuste:
            self.zoom = self.zoom_de_ajuste(self.modo_ajuste, 0)
        self.montar_disposicao(ancora)
        if ancora is None:
            self.tela.xview_moveto(0)
            self.ir_para_pagina(0)
        self.atualizar_titulo()
        self.tela.focus_set()

    # ------------------------------------------------------------------ salvar
    def salvar(self):
        if not self.documento:
            return False
        try:
            if self.documento.can_save_incrementally():
                self.documento.saveIncr()
                # os processos auxiliares relêem o arquivo, que agora contém as alterações
                self.renderizadores.enviar_a_todos(("abrir", self.id_documento, self.caminho, self.senha))
                self.paginas_locais.clear()
            else:
                ancora = self.criar_ancora(0, 0)
                temporario = self.caminho + ".tmp"
                self.documento.save(temporario, garbage=3, deflate=True)
                self.renderizadores.fechar_documento(self.id_documento)  # o Windows não substitui arquivos abertos
                self.documento.close()
                self.documento = None
                os.replace(temporario, self.caminho)
                self.carregar(self.caminho, ancora)
        except Exception as erro:
            self.mostrar_erro(f"Erro ao salvar:\n{erro}\n\nTente “Salvar como” (Ctrl+Shift+S).")
            return False
        self.modificado = False
        self.atualizar_titulo()
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
            ancora = self.criar_ancora(0, 0)
            self.documento.save(destino, garbage=3, deflate=True)
        except Exception as erro:
            self.mostrar_erro(f"Erro ao salvar:\n{erro}")
            return False
        self.carregar(destino, ancora)
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
        self.anotacao_selecionada = None
        self.marcar_modificado()
        if self.modo_ajuste:
            self.zoom = self.zoom_de_ajuste(self.modo_ajuste, atual)
        self.montar_disposicao()
        self.ir_para_pagina(atual)
        self.avisar("Todas as páginas giradas" if todas else f"Página {atual + 1} girada")

    # ------------------------------------------------------------------ fechar
    def confirmar_descarte(self):
        """Pergunta se deve salvar alterações pendentes. Retorna False se o usuário cancelar."""
        if not self.modificado:
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
        maximizada = self.state() == "zoomed"
        if not maximizada:
            self.preferencias["geometria"] = self.geometry()
        self.preferencias.update(maximizada=maximizada, cor=self.cor, tamanho_fonte=self.tamanho_fonte,
                                 ajuste=self.modo_ajuste, zoom=self.zoom)
        salvar_preferencias(self.preferencias)
        self.geracao_busca += 1
        self.fechada = True
        if self.painel_estilo:
            self.painel_estilo.fechar()
        if self.documento:
            self.renderizadores.enviar_a_todos(("descartar", self.id_documento))
            self.documento.close()
            self.documento = None
        self.cache_imagens.clear()
        self.itens_na_tela.clear()
        self.destroy()
        self.aplicativo.janela_fechada(self)
