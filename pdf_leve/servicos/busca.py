"""Busca de vários termos ao mesmo tempo (ex.: “multa; prazo de entrega; rescisão”)."""

import pymupdf

from pdf_leve.configuracao.constantes import SEPARADOR_TERMOS_BUSCA

# As mesmas opções que o search_for usa por padrão (junta palavras hifenizadas etc.).
OPCOES_TEXTO_BUSCA = (pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_PRESERVE_WHITESPACE
                      | pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_MEDIABOX_CLIP)


def separar_termos(texto):
    """'multa; Prazo ;; multa' -> ['multa', 'Prazo']: sem vazios nem repetições (ignorando maiúsculas)."""
    termos, vistos = [], set()
    for parte in texto.split(SEPARADOR_TERMOS_BUSCA):
        termo = " ".join(parte.split())
        chave = termo.casefold()
        if termo and chave not in vistos:
            vistos.add(chave)
            termos.append(termo)
    return termos


def buscar_termos_na_pagina(pagina, termos):
    """Ocorrências dos termos na página, como (retângulo, nº do termo), em ordem de leitura.

    O texto da página é extraído uma vez só e aproveitado por todos os termos.
    """
    texto_pagina = pagina.get_textpage(flags=OPCOES_TEXTO_BUSCA)
    return combinar_resultados([pagina.search_for(termo, textpage=texto_pagina) for termo in termos])


def combinar_resultados(retangulos_por_termo):
    """Junta os retângulos de cada termo numa só lista de (retângulo, nº do termo), em ordem de leitura.

    Quando dois termos acham o mesmo trecho (ex.: “multa” dentro de “multas”), fica só o maior.
    """
    candidatos = [(retangulo, termo) for termo, retangulos in enumerate(retangulos_por_termo)
                  for retangulo in retangulos]
    aceitos = []
    for candidato in sorted(candidatos, key=lambda item: -_area(item[0])):
        if not any(_sobrepoe(candidato[0], aceito[0]) for aceito in aceitos):
            aceitos.append(candidato)
    return _ordem_de_leitura(aceitos)


def _area(r):
    return max(0, r.x1 - r.x0) * max(0, r.y1 - r.y0)


def _sobrepoe(a, b):
    """Os retângulos se sobrepõem em mais da metade do menor deles?"""
    largura = min(a.x1, b.x1) - max(a.x0, b.x0)
    altura = min(a.y1, b.y1) - max(a.y0, b.y0)
    if largura <= 0 or altura <= 0:
        return False
    return largura * altura > min(_area(a), _area(b)) / 2


def _ordem_de_leitura(itens):
    """De cima para baixo e, na mesma linha visual, da esquerda para a direita.

    Retângulos cujo centro vertical cai dentro da faixa da linha contam como a mesma linha, para
    que palavras de alturas um pouco diferentes (negrito, outra fonte) não troquem de ordem.
    """
    linhas = []
    for item in sorted(itens, key=lambda item: item[0].y0):
        retangulo = item[0]
        centro = (retangulo.y0 + retangulo.y1) / 2
        if linhas and linhas[-1][0] <= centro <= linhas[-1][1]:
            linhas[-1][2].append(item)
        else:
            linhas.append((retangulo.y0, retangulo.y1, [item]))
    return [item for _, _, linha in linhas for item in sorted(linha, key=lambda item: item[0].x0)]
