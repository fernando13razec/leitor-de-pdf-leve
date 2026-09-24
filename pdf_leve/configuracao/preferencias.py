"""Leitura e gravação das preferências do usuário (janela, zoom, cor e tamanho do texto…)."""

import json

from pdf_leve.configuracao.constantes import ARQUIVO_PREFERENCIAS

# Versões anteriores (arquivo único) gravavam config.json com chaves em inglês.
ARQUIVO_PREFERENCIAS_ANTIGO = ARQUIVO_PREFERENCIAS.with_name("config.json")
CHAVES_ANTIGAS = {"geometry": "geometria", "zoomed": "maximizada", "color": "cor", "fontsize": "tamanho_fonte",
                  "fit": "ajuste", "zoom": "zoom", "lastdir": "ultima_pasta"}
AJUSTES_ANTIGOS = {"width": "largura", "page": "pagina"}


def _ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        return None


def carregar_preferencias():
    preferencias = _ler_json(ARQUIVO_PREFERENCIAS)
    if preferencias is not None:
        return preferencias
    antigas = _ler_json(ARQUIVO_PREFERENCIAS_ANTIGO) or {}
    migradas = {CHAVES_ANTIGAS[chave]: valor for chave, valor in antigas.items() if chave in CHAVES_ANTIGAS}
    if "ajuste" in migradas:
        migradas["ajuste"] = AJUSTES_ANTIGOS.get(migradas["ajuste"])
    return migradas


def salvar_preferencias(preferencias):
    try:
        ARQUIVO_PREFERENCIAS.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO_PREFERENCIAS, "w", encoding="utf-8") as arquivo:
            json.dump(preferencias, arquivo, ensure_ascii=False, indent=2)
    except OSError:
        pass
