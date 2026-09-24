"""Busca de texto em segundo plano.

A busca percorre as páginas em pequenas etapas (sem travar a interface), começando pela página
atual e dando a volta até o início. Os resultados ficam em duas listas — a partir da página
inicial e antes dela — que juntas formam a ordem do documento. Os retângulos são guardados sem
rotação; a rotação atual da página é aplicada só ao desenhar.
"""

import bisect
import time

from pdf_leve.configuracao.constantes import TEMPO_POR_ETAPA_BUSCA
from pdf_leve.configuracao.tema import COR_PERIGO, COR_TEXTO, COR_TEXTO_SUAVE
from pdf_leve.interface.utilidades import plural


class MixinBusca:

    def _zerar_busca(self):
        self.termo_busca = ""
        self.resultados_depois, self.resultados_antes = [], []  # (página, índice, retângulo)
        self._cache_resultados = None
        self.resultados_por_pagina = {}
        self.resultado_atual = None  # (página, índice na página)
        self.buscando = False

    def todos_resultados(self):
        if self._cache_resultados is None:
            self._cache_resultados = self.resultados_antes + self.resultados_depois
        return self._cache_resultados

    def focar_busca(self):
        self._mostrar_barra()  # em tela cheia, a barra reaparece para a busca
        self.campo_busca.focus_set()
        self.campo_busca.select_range(0, "end")

    def limpar_busca(self, focar=True):
        self.geracao_busca += 1  # interrompe uma busca em andamento
        self._zerar_busca()
        self.rotulo_contagem.config(text="")
        self.desenhar_sobreposicoes()
        if focar:
            self.tela.focus_set()
            if self.tela_cheia:
                self._esconder_barra()

    def buscar(self, voltar=False):
        """Enter: nova busca se o termo mudou; senão, vai ao próximo (ou anterior) resultado."""
        termo = self.var_busca.get().strip()
        if not termo or not self.documento:
            return
        if termo != self.termo_busca:
            self._iniciar_busca(termo)
        else:
            self.mover_resultado(-1 if voltar else 1)

    def _iniciar_busca(self, termo):
        self.geracao_busca += 1
        self._zerar_busca()
        self.termo_busca = termo
        self.buscando = True
        inicio = self.pagina_atual()
        ordem = list(range(inicio, len(self.documento))) + list(range(0, inicio))
        self.atualizar_contagem()
        self.after(1, self._etapa_busca, self.geracao_busca, ordem, inicio, 0)

    def _etapa_busca(self, geracao, ordem, inicio, posicao):
        if geracao != self.geracao_busca or not self.documento:
            return  # busca cancelada ou substituída
        comeco = time.perf_counter()
        while posicao < len(ordem) and time.perf_counter() - comeco < TEMPO_POR_ETAPA_BUSCA:
            pagina = ordem[posicao]
            retangulos = self.documento[pagina].search_for(self.termo_busca)
            if retangulos:
                self.resultados_por_pagina[pagina] = retangulos
                destino = self.resultados_depois if pagina >= inicio else self.resultados_antes
                destino.extend((pagina, indice, r) for indice, r in enumerate(retangulos))
                self._cache_resultados = None
                if self.resultado_atual is None:
                    self.resultado_atual = (pagina, 0)
                    self.mostrar_resultado()
                elif pagina in self.itens_na_tela:
                    self.desenhar_sobreposicoes()
            posicao += 1
        if posicao < len(ordem):
            self.atualizar_contagem()
            self.after(1, self._etapa_busca, geracao, ordem, inicio, posicao)
            return
        self.buscando = False
        self.atualizar_contagem()
        total, paginas = len(self.todos_resultados()), len(self.resultados_por_pagina)
        if total:
            self.avisar(f"“{self.termo_busca}”: {plural(total, 'ocorrência', 'ocorrências')} "
                        f"em {plural(paginas, 'página', 'páginas')}")
        else:
            self.avisar(f"“{self.termo_busca}” não foi encontrado")

    def indice_resultado(self):
        if self.resultado_atual is None:
            return -1
        return bisect.bisect_left(self.todos_resultados(), self.resultado_atual)

    def mover_resultado(self, passo):
        resultados = self.todos_resultados()
        if not resultados:
            return
        indice = (self.indice_resultado() + passo) % len(resultados)
        self.resultado_atual = resultados[indice][:2]
        self.mostrar_resultado()

    def retangulos_resultados(self, pagina):
        """Retângulos dos resultados na página, já na rotação atual."""
        retangulos = self.resultados_por_pagina.get(pagina)
        if not retangulos:
            return []
        rotacao = self.documento[pagina].rotation_matrix
        return [r * rotacao for r in retangulos]

    def mostrar_resultado(self):
        """Rola a tela até o resultado atual, se ele não estiver visível."""
        pagina, indice = self.resultado_atual
        x0, y0, x1, y1 = self.retangulo_na_tela(pagina, self.retangulos_resultados(pagina)[indice])
        altura, largura = self.tela.winfo_height(), self.tela.winfo_width()
        if not (self.tela.canvasy(0) < y0 and y1 < self.tela.canvasy(altura)):
            self.tela.yview_moveto(max(0, y0 - altura / 3) / self.altura_total)
        if not (self.tela.canvasx(0) < x0 and x1 < self.tela.canvasx(largura)):
            self.tela.xview_moveto(max(0, x0 - largura / 3) / self.largura_total)
        self.atualizar_contagem()
        self.renderizar_visiveis()

    def atualizar_contagem(self):
        """“3 de 27” na caixa de busca (com “…” enquanto ainda está buscando)."""
        total = len(self.todos_resultados())
        if not self.termo_busca:
            texto, cor = "", COR_TEXTO_SUAVE
        elif total == 0:
            texto, cor = ("buscando…", COR_TEXTO_SUAVE) if self.buscando else ("0 resultados", COR_PERIGO)
        else:
            reticencias = "…" if self.buscando else ""
            texto, cor = f"{self.indice_resultado() + 1} de {total}{reticencias}", COR_TEXTO
        self.rotulo_contagem.config(text=texto, fg=cor)
