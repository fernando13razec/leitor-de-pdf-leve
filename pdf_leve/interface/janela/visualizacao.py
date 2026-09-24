"""Visualização: disposição das páginas, renderização com cache, rolagem, zoom e navegação.

Fluxo da renderização: `renderizar_visiveis` coloca na tela as páginas visíveis que já estão no
cache e pede as que faltam (visíveis primeiro, depois as próximas na direção da leitura) aos
processos auxiliares. As imagens voltam por `receber_imagem`. Páginas com anotações ainda não
salvas (`paginas_locais`) são renderizadas aqui mesmo, pois os processos auxiliares só enxergam
o arquivo em disco.
"""

import bisect

import fitz  # PyMuPDF

from pdf_leve.configuracao.constantes import (
    ESPACO_ENTRE_PAGINAS, LIMITE_PIXELS_CACHE, PAGINAS_PRE_CARREGADAS, PASSO_ZOOM_RODA, ZOOM_MAXIMO, ZOOM_MINIMO,
)
from pdf_leve.configuracao.tema import (
    COR_CARREGANDO, COR_CONTORNO_ANOTACAO, COR_PAGINA, COR_RESULTADO_ATUAL, COR_RESULTADO_BUSCA,
    COR_SOMBRA_PAGINA, fontes,
)
from pdf_leve.interface.utilidades import imagem_ppm
from pdf_leve.servicos.anotacoes import retangulo_exibido
from pdf_leve.servicos.renderizacao import aparar_deposito_mupdf, renderizar_pagina

ESPACO = ESPACO_ENTRE_PAGINAS


class MixinVisualizacao:

    # ------------------------------------------------------------------ disposição
    def montar_disposicao(self, ancora=None):
        """Calcula a posição de todas as páginas no zoom atual e desenha os espaços em branco."""
        tela = self.tela
        tela.delete("all")
        self.itens_na_tela.clear()
        self.disposicao = []
        self._navegacao = None
        if not self.documento:
            self.desenhar_tela_vazia()
            return
        escala = self.zoom * self.escala_base
        largura_maxima = max(r.width for r in self.retangulos_paginas) * escala
        self.largura_total = max(tela.winfo_width(), largura_maxima + 2 * ESPACO)
        y = ESPACO
        for retangulo in self.retangulos_paginas:
            largura, altura = retangulo.width * escala, retangulo.height * escala
            x = (self.largura_total - largura) / 2
            self.disposicao.append((x, y, largura, altura))
            tela.create_rectangle(x + 2, y + 3, x + largura + 2, y + altura + 3, fill=COR_SOMBRA_PAGINA, outline="")
            tela.create_rectangle(x, y, x + largura, y + altura, fill=COR_PAGINA, outline="")
            y += altura + ESPACO
        self.altura_total = y
        tela.config(scrollregion=(0, 0, self.largura_total, self.altura_total))
        self.rotulo_zoom.config(text=f"{round(self.zoom * 100)}%")
        self.atualizar_botoes()
        if ancora:
            self.ir_para_ancora(ancora)
        self.agendar_renderizacao()

    def pagina_na_altura(self, y_tela):
        topos = [pagina[1] for pagina in self.disposicao]
        return max(0, min(len(topos) - 1, bisect.bisect_right(topos, y_tela) - 1))

    def pagina_atual(self):
        if not self.disposicao:
            return 0
        inicio, fim = self.tela.yview()
        if self._navegacao and abs(self._navegacao[1] - inicio) < 1e-9:
            return self._navegacao[0]  # a vista não mudou desde o último salto de página
        if fim >= 0.99999 and inicio > 0:  # no fim do documento, vale a última página visível
            return self.pagina_na_altura(self.tela.canvasy(self.tela.winfo_height()) - ESPACO)
        return self.pagina_na_altura(self.tela.canvasy(0) + ESPACO)

    def faixa_visivel(self):
        topo = self.tela.canvasy(0)
        base = self.tela.canvasy(self.tela.winfo_height())
        return self.pagina_na_altura(topo), self.pagina_na_altura(base)

    # ------------------------------------------------------------------ renderização
    def chave_pagina(self, pagina):
        return self.id_documento, pagina, round(self.zoom * self.escala_base * 1000), self.versao_pagina[pagina]

    def agendar_renderizacao(self):
        if self._tarefa_renderizar:
            self.after_cancel(self._tarefa_renderizar)
        self._tarefa_renderizar = self.after(10, self.renderizar_visiveis)

    def renderizar_visiveis(self):
        self._tarefa_renderizar = None
        if not self.documento or not self.disposicao:
            return
        total = len(self.disposicao)
        primeira, ultima = self.faixa_visivel()
        manter = range(max(0, primeira - 1), min(total, ultima + 2))
        for pagina in list(self.itens_na_tela):
            if pagina not in manter:
                self.tela.delete(self.itens_na_tela.pop(pagina)[1])

        para_frente = primeira >= self._ultima_primeira_visivel
        self._ultima_primeira_visivel = primeira
        seguintes = [ultima + i for i in range(1, PAGINAS_PRE_CARREGADAS + 1)] + [primeira - 1, primeira - 2]
        anteriores = [primeira - i for i in range(1, PAGINAS_PRE_CARREGADAS + 1)] + [ultima + 1, ultima + 2]
        ordem = list(range(primeira, ultima + 1)) + (seguintes if para_frente else anteriores)

        usar_processos = self.renderizadores.disponivel
        pedidos = []
        for pagina in ordem:
            if not 0 <= pagina < total:
                continue
            chave = self.chave_pagina(pagina)
            imagem = self.cache_imagens.get(chave)
            if imagem is not None:
                self.cache_imagens.move_to_end(chave)
                if pagina in manter:
                    self.posicionar(pagina, chave, imagem)
            elif pagina in self.paginas_locais or not usar_processos:
                if primeira <= pagina <= ultima:
                    self.renderizar_localmente(pagina)
            elif chave not in self.em_renderizacao:
                pedidos.append((chave, pagina))
        self.fila_pedidos = pedidos
        self.renderizadores.distribuir()
        self._desenhar_carregando(primeira, ultima)
        if self.focus_get() is not self.campo_pagina:
            self.var_pagina.set(str(self.pagina_atual() + 1))
        self.desenhar_sobreposicoes()

    def _desenhar_carregando(self, primeira, ultima):
        self.tela.delete("carregando")
        for pagina in range(primeira, ultima + 1):
            if pagina not in self.itens_na_tela:
                x, y, largura, altura = self.disposicao[pagina]
                self.tela.create_text(x + largura / 2, y + min(altura / 2, self.tela.winfo_height() / 2),
                                      text="Carregando…", fill=COR_CARREGANDO, font=fontes.interface,
                                      tags="carregando")

    def posicionar(self, pagina, chave, imagem):
        atual = self.itens_na_tela.get(pagina)
        if atual and atual[0] == chave:
            return
        if atual:
            self.tela.delete(atual[1])
        x, y, _, _ = self.disposicao[pagina]
        item = self.tela.create_image(x, y, image=imagem, anchor="nw")
        self.tela.tag_raise("sobreposicao")
        self.itens_na_tela[pagina] = (chave, item, imagem)

    def guardar_no_cache(self, chave, imagem):
        self.cache_imagens[chave] = imagem
        self.pixels_em_cache += imagem.width() * imagem.height()
        while self.pixels_em_cache > LIMITE_PIXELS_CACHE and len(self.cache_imagens) > 1:
            _, antiga = self.cache_imagens.popitem(last=False)
            self.pixels_em_cache -= antiga.width() * antiga.height()

    def renderizar_localmente(self, pagina):
        chave = self.chave_pagina(pagina)
        imagem_pdf = renderizar_pagina(self.documento[pagina], chave[2] / 1000)
        imagem = imagem_ppm(imagem_pdf.width, imagem_pdf.height, imagem_pdf.samples)
        self.guardar_no_cache(chave, imagem)
        self.posicionar(pagina, chave, imagem)
        aparar_deposito_mupdf()

    def proximo_pedido(self):
        """Próxima página que esta janela quer dos processos auxiliares (ou None)."""
        while self.fila_pedidos:
            chave, pagina = self.fila_pedidos.pop(0)
            if chave not in self.cache_imagens and chave not in self.em_renderizacao:
                return chave, pagina
        return None

    def receber_imagem(self, chave, largura, altura, amostras):
        """Página pronta vinda de um processo auxiliar. Retorna True se ela foi colocada na tela."""
        if self.fechada or not self.documento or chave[0] != self.id_documento:
            return False
        imagem = imagem_ppm(largura, altura, amostras)
        self.guardar_no_cache(chave, imagem)
        pagina = chave[1]
        primeira, ultima = self.faixa_visivel()
        if primeira - 1 <= pagina <= ultima + 1 and chave == self.chave_pagina(pagina):
            self.posicionar(pagina, chave, imagem)
            return True
        return False

    def invalidar(self, pagina):
        """A página mudou (anotação): passa a ser renderizada aqui até o arquivo ser salvo."""
        self.versao_pagina[pagina] += 1
        self.paginas_locais.add(pagina)
        self.agendar_renderizacao()

    def desenhar_sobreposicoes(self):
        """Seleção de texto, resultados da busca e contorno da anotação selecionada."""
        tela = self.tela
        tela.delete("sobreposicao")
        if not self.documento:
            return
        self.desenhar_selecao_texto()
        for pagina in self.itens_na_tela:
            for indice, retangulo in enumerate(self.retangulos_resultados(pagina)):
                x0, y0, x1, y1 = self.retangulo_na_tela(pagina, retangulo)
                atual = self.resultado_atual == (pagina, indice)
                tela.create_rectangle(x0 - 2, y0 - 1, x1 + 2, y1 + 1, tags="sobreposicao",
                                      outline=COR_RESULTADO_ATUAL if atual else COR_RESULTADO_BUSCA,
                                      width=3 if atual else 2)
        if self.anotacao_selecionada:
            encontrada = self.obter_anotacao(*self.anotacao_selecionada)
            if encontrada:
                pagina_pdf, anotacao = encontrada
                self.desenhar_contorno_anotacao(self.anotacao_selecionada[0],
                                                retangulo_exibido(pagina_pdf, anotacao))
            else:
                self.anotacao_selecionada = None

    def desenhar_contorno_anotacao(self, pagina, retangulo):
        x0, y0, x1, y1 = self.retangulo_na_tela(pagina, retangulo)
        self.tela.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, tags="sobreposicao",
                                   outline=COR_CONTORNO_ANOTACAO, width=2, dash=(4, 3))

    # ------------------------------------------------------------------ rolagem
    def _rolar_vertical(self, *argumentos):
        self.tela.yview(*argumentos)
        self.agendar_renderizacao()

    def _rolar_horizontal(self, *argumentos):
        self.tela.xview(*argumentos)
        self.agendar_renderizacao()

    def _rolar(self, eixo, delta):
        passos = -round(delta / 40) or (-1 if delta > 0 else 1)  # touchpads mandam deltas pequenos
        (self._rolar_vertical if eixo == "y" else self._rolar_horizontal)("scroll", passos, "units")

    def _ao_girar_roda(self, evento):
        self._rolar("y", evento.delta)

    def _ao_girar_roda_com_ctrl(self, evento):
        fator = PASSO_ZOOM_RODA if evento.delta > 0 else 1 / PASSO_ZOOM_RODA
        self.definir_zoom(self.zoom * fator, no_ponto=(evento.x, evento.y))

    def _ao_redimensionar(self, evento):
        if not self.documento:
            self.desenhar_tela_vazia()
            return
        tamanho = (evento.width, evento.height)
        if tamanho != self._ultimo_tamanho:
            largura_mudou = evento.width != self._ultimo_tamanho[0]
            self._ultimo_tamanho = tamanho
            if largura_mudou or self.modo_ajuste == "pagina":
                if self._tarefa_redimensionar:
                    self.after_cancel(self._tarefa_redimensionar)
                self._tarefa_redimensionar = self.after(80, self._refazer_disposicao)
        self.agendar_renderizacao()

    def _refazer_disposicao(self):
        self._tarefa_redimensionar = None
        if not self.documento:
            return
        if self.modo_ajuste == "pagina":
            atual = self.pagina_atual()
            self.zoom = self.zoom_de_ajuste("pagina", atual)
            self.montar_disposicao()
            self.ir_para_pagina(atual)
            return
        ancora = self.criar_ancora(0, 0)
        if self.modo_ajuste == "largura":
            self.zoom = self.zoom_de_ajuste("largura")
        self.montar_disposicao(ancora)

    def criar_ancora(self, x_janela, y_janela):
        """Ponto de referência (página + posição relativa) para manter a vista ao mudar o zoom."""
        if not self.disposicao:
            return None
        x_tela, y_tela = self.tela.canvasx(x_janela), self.tela.canvasy(y_janela)
        pagina = self.pagina_na_altura(y_tela)
        x, y, largura, altura = self.disposicao[pagina]
        return pagina, (x_tela - x) / largura, (y_tela - y) / altura, x_janela, y_janela

    def ir_para_ancora(self, ancora):
        pagina, fracao_x, fracao_y, x_janela, y_janela = ancora
        pagina = min(pagina, len(self.disposicao) - 1)
        x, y, largura, altura = self.disposicao[pagina]
        self.tela.xview_moveto(max(0, x + fracao_x * largura - x_janela) / self.largura_total)
        self.tela.yview_moveto(max(0, y + fracao_y * altura - y_janela) / self.altura_total)

    # ------------------------------------------------------------------ zoom
    def definir_zoom(self, zoom, no_ponto=None):
        zoom = min(max(zoom, ZOOM_MINIMO), ZOOM_MAXIMO)
        if not self.documento or abs(zoom - self.zoom) < 1e-4:
            return
        ancora = self.criar_ancora(*(no_ponto or (0, 0)))
        self.zoom = zoom
        self.modo_ajuste = None
        self.montar_disposicao(ancora)

    def zoom_de_ajuste(self, modo, pagina=0):
        largura_disponivel = max(self.tela.winfo_width(), 200) - 2 * ESPACO
        if modo == "largura":
            largura_maxima = max(r.width for r in self.retangulos_paginas)
            zoom = largura_disponivel / (largura_maxima * self.escala_base)
        else:
            retangulo = self.retangulos_paginas[pagina]
            altura_disponivel = max(self.tela.winfo_height(), 150) - ESPACO - 4
            zoom = min(largura_disponivel / (retangulo.width * self.escala_base),
                       altura_disponivel / (retangulo.height * self.escala_base))
        return min(max(zoom, ZOOM_MINIMO), ZOOM_MAXIMO)

    def definir_ajuste(self, modo):
        """“largura”: página ocupa a largura da janela; “pagina”: página inteira visível."""
        self.modo_ajuste = modo
        if not self.documento:
            self.atualizar_botoes()
            return
        atual = self.pagina_atual()
        if modo == "pagina":
            self.zoom = self.zoom_de_ajuste("pagina", atual)
            self.montar_disposicao()
            self.ir_para_pagina(atual)
        else:
            ancora = self.criar_ancora(0, 0)
            self.zoom = self.zoom_de_ajuste("largura")
            self.montar_disposicao(ancora)
        self.tela.focus_set()

    # ------------------------------------------------------------------ navegação
    def ir_para_pagina(self, pagina):
        if not self.disposicao:
            return
        pagina = max(0, min(pagina, len(self.disposicao) - 1))
        if self.modo_ajuste == "pagina" and abs(self.zoom_de_ajuste("pagina", pagina) - self.zoom) > 1e-3:
            self.zoom = self.zoom_de_ajuste("pagina", pagina)  # páginas de tamanhos diferentes
            self.montar_disposicao()
        self.tela.yview_moveto((self.disposicao[pagina][1] - ESPACO / 2) / self.altura_total)
        self._navegacao = (pagina, self.tela.yview()[0])
        self.agendar_renderizacao()

    def avancar_pagina(self, quantidade):
        if self.disposicao:
            self.ir_para_pagina(self.pagina_atual() + quantidade)

    def _ao_digitar_pagina(self, _evento):
        try:
            self.ir_para_pagina(int(self.var_pagina.get()) - 1)
        except ValueError:
            pass
        self.tela.focus_set()

    # ------------------------------------------------------------------ coordenadas
    def retangulo_na_tela(self, pagina, retangulo):
        """Retângulo (em coordenadas exibidas da página) convertido para o canvas."""
        escala = self.zoom * self.escala_base
        x, y, _, _ = self.disposicao[pagina]
        return (x + retangulo.x0 * escala, y + retangulo.y0 * escala,
                x + retangulo.x1 * escala, y + retangulo.y1 * escala)

    def ponto_na_pagina(self, x_tela, y_tela):
        """(página, ponto em coordenadas exibidas) sob um ponto do canvas, ou None fora das páginas."""
        if not self.disposicao:
            return None
        pagina = self.pagina_na_altura(y_tela)
        x, y, largura, altura = self.disposicao[pagina]
        if not (x <= x_tela <= x + largura and y <= y_tela <= y + altura):
            return None
        escala = self.zoom * self.escala_base
        return pagina, fitz.Point((x_tela - x) / escala, (y_tela - y) / escala)

    def pagina_sob_cursor(self, x_tela, y_tela):
        """Como ponto_na_pagina, mas traz o ponto para dentro da página mais próxima."""
        pagina = self.pagina_na_altura(y_tela)
        x, y, largura, altura = self.disposicao[pagina]
        escala = self.zoom * self.escala_base
        return pagina, fitz.Point((min(max(x_tela, x), x + largura) - x) / escala,
                                  (min(max(y_tela, y), y + altura) - y) / escala)
