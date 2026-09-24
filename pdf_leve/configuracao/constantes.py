"""Constantes de configuração do PDF Leve, reunidas num só lugar para facilitar ajustes."""

import os
import sys
from pathlib import Path

NOME_APLICATIVO = "PDF Leve"
VERSAO = "1.0.0"

# ------------------------------------------------------------------ pastas e arquivos
# Quando empacotado com PyInstaller, os recursos ficam em sys._MEIPASS.
PASTA_RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
PASTA_RECURSOS = PASTA_RAIZ / "recursos"
ICONE_ICO = PASTA_RECURSOS / "icone.ico"
ICONE_PNG = PASTA_RECURSOS / "icone.png"

PASTA_DADOS = Path(os.environ.get("APPDATA", Path.home())) / "PdfLeve"
ARQUIVO_PREFERENCIAS = PASTA_DADOS / "preferencias.json"

# ------------------------------------------------------------------ visualização
ESPACO_ENTRE_PAGINAS = 16       # px entre as páginas e nas margens
ZOOM_MINIMO = 0.1
ZOOM_MAXIMO = 6.0
PASSO_ZOOM = 1.2                # botões e Ctrl +/−
PASSO_ZOOM_RODA = 1.1           # Ctrl + roda do mouse
LINHAS_POR_SETA = 3             # unidades roladas por ↑/↓
PIXELS_POR_UNIDADE_ROLAGEM = 20
MARGEM_ROLAGEM_AUTOMATICA = 24  # px da borda que fazem a seleção de texto rolar a tela
DURACAO_AVISO_MS = 2600

# ------------------------------------------------------------------ renderização
PROCESSOS_RENDERIZACAO = 2        # processos auxiliares que renderizam páginas em paralelo
LIMITE_PIXELS_CACHE = 16_000_000  # cache de páginas prontas por janela (~64 MB)
PAGINAS_PRE_CARREGADAS = 4        # páginas preparadas à frente na direção da leitura
RENDERIZACOES_ENTRE_LIMPEZAS = 4  # a cada N páginas, esvazia o depósito de imagens do MuPDF
LIMITE_CACHE_PALAVRAS = 80        # páginas com palavras (texto selecionável) em memória

# ------------------------------------------------------------------ anotações
FONTE_ANOTACAO = "helv"  # Helvetica padrão do PDF (cobre o português)
CORES_ANOTACAO = {
    "Preto": "#000000",
    "Vermelho": "#d32f2f",
    "Azul": "#1565c0",
    "Verde": "#2e7d32",
    "Laranja": "#ef6c00",
    "Roxo": "#6a1b9a",
    "Azul-petróleo": "#00838f",
    "Rosa": "#c2185b",
}
COR_ANOTACAO_PADRAO = "#d32f2f"
TAMANHO_FONTE_PADRAO = 12
TAMANHO_FONTE_MINIMO = 6
TAMANHO_FONTE_MAXIMO = 72

# ------------------------------------------------------------------ busca
TEMPO_POR_ETAPA_BUSCA = 0.04  # s de busca por vez, para a interface continuar respondendo

# ------------------------------------------------------------------ instância única
PORTA_INSTANCIA_UNICA = 48213       # só aceita conexões do próprio computador (127.0.0.1)
IDENTIFICADOR_MENSAGEM = "pdfleve"  # confirma que quem responde é o próprio PDF Leve
ID_APLICATIVO_WINDOWS = "PdfLeve.LeitorDePdf"  # agrupa as janelas na barra de tarefas
