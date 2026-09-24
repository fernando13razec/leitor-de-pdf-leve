"""Tema escuro: cores, fontes e ícones (glifos) da interface."""

import tkinter.font as tkfont

# ------------------------------------------------------------------ cores
COR_FUNDO = "#1b1c1f"             # atrás das páginas
COR_BARRA = "#25262a"             # barra de ferramentas e diálogos
COR_PASSAR_MOUSE = "#34363b"
COR_ATIVO = "#2e3a52"             # botão ligado (ex.: modo texto)
COR_LINHA = "#34363b"             # divisórias e bordas
COR_CAMPO = "#1b1c1f"             # fundo dos campos de digitação
COR_TEXTO = "#e4e5e7"
COR_TEXTO_SUAVE = "#8b8e96"
COR_TEXTO_APAGADO = "#62656d"
COR_DESTAQUE = "#7aa2f7"
COR_DESTAQUE_CLARO = "#99b8fa"
COR_TEXTO_SOBRE_DESTAQUE = "#10131a"
COR_PERIGO = "#f28b82"
COR_AVISO = "#3a3c42"             # fundo dos avisos flutuantes e dicas
COR_BOTAO_SECUNDARIO_ATIVO = "#42444a"
COR_BORDA_CIRCULO = "#5a5c63"
COR_BORDA_BOTAO_COR = "#6a6d75"

COR_SOMBRA_PAGINA = "#0f1012"
COR_PAGINA = "white"
COR_CARREGANDO = "#9a9ca3"
COR_ICONE_TELA_VAZIA = "#4a4c53"
COR_BARRA_ROLAGEM = "#44464d"
COR_BARRA_ROLAGEM_ATIVA = "#5a5d66"

COR_RESULTADO_BUSCA = "#f9c74f"
COR_RESULTADO_ATUAL = "#ff6d00"
COR_CONTORNO_ANOTACAO = "#1e88e5"
COR_SELECAO_TEXTO_RGBA = (51, 136, 255, 80)  # azul translúcido
COR_FUNDO_EDITOR_ANOTACAO = "#ffffff"
COR_SELECAO_EDITOR_ANOTACAO = "#c6d6fb"


# ------------------------------------------------------------------ fontes
class Fontes:
    """Fontes da interface. Só podem ser definidas depois que o Tk existe (iniciar_fontes)."""

    interface = ("Segoe UI", 10)
    pequena = ("Segoe UI", 9)
    icone = ("Segoe UI", 12)
    icone_grande = ("Segoe UI", 44)
    tem_icones = False  # se há uma fonte de ícones do Windows instalada


fontes = Fontes()


def iniciar_fontes(raiz):
    familias = set(tkfont.families(raiz))
    base = "Segoe UI Variable Text" if "Segoe UI Variable Text" in familias else "Segoe UI"
    icones = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in familias), None)
    fontes.interface = (base, 10)
    fontes.pequena = (base, 9)
    fontes.tem_icones = icones is not None
    fontes.icone = (icones or base, 12)
    fontes.icone_grande = (icones or base, 44)


def fonte_icone(tamanho):
    """Fonte de ícones num tamanho específico (ou a fonte da interface, se não houver ícones)."""
    return (fontes.icone[0], tamanho) if fontes.tem_icones else fontes.pequena


# ------------------------------------------------------------------ ícones
# Glifos das fontes Segoe Fluent Icons / Segoe MDL2 Assets, com alternativa em texto.
GLIFOS = {
    "abrir": ("\uE8E5", "Abrir"),
    "salvar": ("\uE74E", "Salvar"),
    "imprimir": ("\uE749", "Páginas"),
    "anterior": ("\uE76B", "‹"),
    "proxima": ("\uE76C", "›"),
    "diminuir_zoom": ("\uE71F", "−"),
    "aumentar_zoom": ("\uE8A3", "+"),
    "ajustar_largura": ("\uE799", "↔"),
    "ajustar_pagina": ("\uE9A6", "▭"),
    "girar": ("\uE7AD", "↻"),
    "texto": ("\uE8D2", "T"),
    "buscar": ("\uE721", "⌕"),
    "acima": ("\uE70E", "▲"),
    "abaixo": ("\uE70D", "▼"),
    "fechar": ("\uE711", "×"),
}


def glifo(nome):
    icone, alternativa = GLIFOS[nome]
    return icone if fontes.tem_icones else alternativa
