"""Seleção e cópia do texto das páginas (inclusive entre páginas diferentes).

A seleção é um par de posições ((página, palavra), (página, palavra)) na ordem em que o usuário
arrastou; `faixas_selecionadas` a normaliza em faixas de palavras por página.
"""

import fitz  # PyMuPDF

from pdf_leve.configuracao.constantes import LIMITE_CACHE_PALAVRAS
from pdf_leve.configuracao.tema import COR_SELECAO_TEXTO_RGBA
from pdf_leve.interface.utilidades import imagem_cor_solida
from pdf_leve.servicos.texto import linha_da_palavra, linhas_visuais, palavra_mais_proxima, texto_das_palavras

LIMITE_IMAGENS_SELECAO = 400


class MixinSelecaoTexto:

    def palavras_da_pagina(self, pagina):
        palavras = self.cache_palavras.get(pagina)
        if palavras is None:
            palavras = self.documento[pagina].get_text("words")
            self.cache_palavras[pagina] = palavras
            if len(self.cache_palavras) > LIMITE_CACHE_PALAVRAS:
                self.cache_palavras.popitem(last=False)
        else:
            self.cache_palavras.move_to_end(pagina)
        return palavras

    def palavra_no_ponto(self, pagina, ponto_exibido, exata=False):
        """Índice da palavra sob o ponto (ou a mais próxima, se exata=False)."""
        palavras = self.palavras_da_pagina(pagina)
        if not palavras:
            return None
        ponto = ponto_exibido * self.documento[pagina].derotation_matrix
        return palavra_mais_proxima(palavras, ponto, exata)

    def faixas_selecionadas(self):
        """(página, primeira palavra, última palavra) de cada página da seleção."""
        if not self.selecao_texto:
            return
        (pagina_inicio, palavra_inicio), (pagina_fim, palavra_fim) = sorted(self.selecao_texto)
        for pagina in range(pagina_inicio, pagina_fim + 1):
            total = len(self.palavras_da_pagina(pagina))
            if total:
                yield (pagina,
                       palavra_inicio if pagina == pagina_inicio else 0,
                       palavra_fim if pagina == pagina_fim else total - 1)

    def desenhar_selecao_texto(self):
        """Destaque azul translúcido (um retângulo por linha visual) nas páginas visíveis."""
        if not self.selecao_texto:
            return
        if len(self._imagens_selecao) > LIMITE_IMAGENS_SELECAO:
            self._imagens_selecao.clear()
        (pagina_inicio, _), (pagina_fim, _) = sorted(self.selecao_texto)
        for pagina, primeira, ultima in self.faixas_selecionadas():
            if pagina not in self.itens_na_tela or not pagina_inicio <= pagina <= pagina_fim:
                continue
            rotacao = self.documento[pagina].rotation_matrix
            for linha in linhas_visuais(self.palavras_da_pagina(pagina)[primeira:ultima + 1]):
                retangulo = fitz.Rect(linha[0][:4])
                for palavra in linha[1:]:
                    retangulo |= fitz.Rect(palavra[:4])
                x0, y0, x1, y1 = (round(v) for v in self.retangulo_na_tela(pagina, retangulo * rotacao))
                tamanho = (max(1, x1 - x0), max(1, y1 - y0))
                imagem = self._imagens_selecao.get(tamanho)
                if imagem is None:
                    imagem = self._imagens_selecao[tamanho] = imagem_cor_solida(*tamanho, COR_SELECAO_TEXTO_RGBA)
                self.tela.create_image(x0, y0, image=imagem, anchor="nw", tags="sobreposicao")

    def texto_selecionado(self):
        partes = [texto_das_palavras(self.palavras_da_pagina(pagina)[primeira:ultima + 1])
                  for pagina, primeira, ultima in self.faixas_selecionadas()]
        return "\n".join(partes)

    def copiar_selecao(self):
        texto = self.texto_selecionado() if self.selecao_texto else ""
        if not texto:
            return
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.avisar("Texto copiado")

    def selecionar_palavra(self, pagina, ponto):
        indice = self.palavra_no_ponto(pagina, ponto, exata=True)
        if indice is not None:
            self.selecao_texto = ((pagina, indice), (pagina, indice))
            self.desenhar_sobreposicoes()

    def selecionar_linha(self, pagina, ponto):
        indice = self.palavra_no_ponto(pagina, ponto, exata=True)
        if indice is None:
            return
        primeira, ultima = linha_da_palavra(self.palavras_da_pagina(pagina), indice)
        self.selecao_texto = ((pagina, primeira), (pagina, ultima))
        self.desenhar_sobreposicoes()
