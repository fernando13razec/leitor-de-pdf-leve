"""Anotações de texto livre (FreeText) do PDF: criação, leitura e alteração.

Coordenadas “exibidas” são as da página como aparece na tela (já girada);
o PDF guarda as anotações em coordenadas sem rotação.
"""

import re

import pymupdf

from pdf_leve.configuracao.constantes import FONTE_ANOTACAO

_fonte = pymupdf.Font(FONTE_ANOTACAO)


def hex_para_rgb(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_para_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in rgb)


def medir_caixa_texto(texto, tamanho):
    """Largura e altura (em pontos PDF) para o texto caber sem quebras nem cortes."""
    linhas = texto.split("\n") or [""]
    largura = max(_fonte.text_length(linha, fontsize=tamanho) for linha in linhas)
    altura = (len(linhas) - 1) * tamanho * 1.15 + tamanho * 1.1 + 4
    return largura * 1.02 + tamanho * 0.2 + 6, altura


def encaixar_caixa_texto(pagina, x, y, texto, tamanho):
    """Retângulo (exibido) para o texto a partir de (x, y), mantido dentro da página."""
    largura, altura = medir_caixa_texto(texto, tamanho)
    limites = pagina.rect
    x = max(limites.x0, min(x, limites.x1 - largura))
    y = max(limites.y0, min(y, limites.y1 - altura))
    return pymupdf.Rect(x, y, x + largura, y + altura)


def retangulo_exibido(pagina, anotacao):
    return anotacao.rect * pagina.rotation_matrix


def retangulo_sem_rotacao(pagina, retangulo):
    return (pymupdf.Rect(retangulo) * pagina.derotation_matrix).normalize()


def criar_anotacao(pagina, retangulo, texto, cor, tamanho):
    return pagina.add_freetext_annot(retangulo_sem_rotacao(pagina, retangulo), texto, fontsize=tamanho,
                                     fontname=FONTE_ANOTACAO, text_color=hex_para_rgb(cor),
                                     rotate=pagina.rotation)


def aplicar_anotacao(pagina, anotacao, texto, cor, tamanho, retangulo):
    """Atualiza texto, cor, tamanho e posição (retângulo exibido) de uma anotação existente."""
    anotacao.set_info(content=texto)
    anotacao.set_rect(retangulo_sem_rotacao(pagina, retangulo))
    anotacao.update(fontsize=tamanho, fontname=FONTE_ANOTACAO, text_color=hex_para_rgb(cor),
                    rotate=pagina.rotation)


def ler_propriedades(documento, anotacao):
    """(texto, cor em hex, tamanho) de uma anotação, lidos da string de aparência (DA) do PDF."""
    texto = anotacao.info.get("content", "")
    cor, tamanho = "#000000", 12
    try:
        aparencia = documento.xref_get_key(anotacao.xref, "DA")[1]
        rgb = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", aparencia)
        if rgb:
            cor = rgb_para_hex([float(v) for v in rgb.groups()])
        else:
            cinza = re.search(r"([\d.]+)\s+g\b", aparencia)
            if cinza:
                cor = rgb_para_hex([float(cinza.group(1))] * 3)
        fonte = re.search(r"([\d.]+)\s+Tf", aparencia)
        if fonte and float(fonte.group(1)) > 0:
            tamanho = round(float(fonte.group(1)))
    except Exception:
        pass
    return texto, cor, tamanho


def anotacoes_de_texto(pagina):
    return pagina.annots(types=[pymupdf.PDF_ANNOT_FREE_TEXT])
