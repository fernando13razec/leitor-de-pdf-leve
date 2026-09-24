"""Texto selecionável das páginas.

As “palavras” são as tuplas do PyMuPDF `page.get_text("words")`:
(x0, y0, x1, y1, texto, bloco, linha, número_da_palavra), em coordenadas sem rotação.
"""


def palavra_mais_proxima(palavras, ponto, exata=False):
    """Índice da palavra que contém o ponto; se exata=False e nenhuma contém, a mais próxima."""
    melhor, menor_distancia = None, float("inf")
    for indice, palavra in enumerate(palavras):
        x0, y0, x1, y1 = palavra[:4]
        if x0 <= ponto.x <= x1 and y0 <= ponto.y <= y1:
            return indice
        if exata:
            continue
        dist_y = 0 if y0 <= ponto.y <= y1 else min(abs(ponto.y - y0), abs(ponto.y - y1))
        dist_x = 0 if x0 <= ponto.x <= x1 else min(abs(ponto.x - x0), abs(ponto.x - x1))
        distancia = dist_y * 4 + dist_x  # estar na mesma linha pesa mais que a distância lateral
        if distancia < menor_distancia:
            melhor, menor_distancia = indice, distancia
    return melhor


def linhas_visuais(palavras):
    """Agrupa palavras consecutivas que estão na mesma linha visual (sobreposição vertical).

    Não usa a numeração de linhas do PDF: no texto justificado de OCR ela costuma colocar
    cada palavra numa “linha” própria.
    """
    linhas = []
    for palavra in palavras:
        if linhas:
            anterior = linhas[-1][-1]
            sobreposicao = min(anterior[3], palavra[3]) - max(anterior[1], palavra[1])
            if sobreposicao > 0.5 * min(anterior[3] - anterior[1], palavra[3] - palavra[1]):
                linhas[-1].append(palavra)
                continue
        linhas.append([palavra])
    return linhas


def texto_das_palavras(palavras):
    """Texto com espaços entre palavras da mesma linha e quebras entre linhas."""
    return "\n".join(" ".join(palavra[4] for palavra in linha) for linha in linhas_visuais(palavras))


def linha_da_palavra(palavras, indice):
    """(primeiro, último) índice da linha visual que contém a palavra."""
    inicio = 0
    for linha in linhas_visuais(palavras):
        if inicio <= indice < inicio + len(linha):
            return inicio, inicio + len(linha) - 1
        inicio += len(linha)
    return indice, indice
