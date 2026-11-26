"""Temas do protótipo: “moderno” (a proposta do canvas) e “cyberpunk”.

Cada tema é um conjunto de valores; `tema` aponta para o tema em uso e é consultado na hora de
montar a interface (trocar de tema recria a janela). `gerar_estilo` produz a folha de estilo do Qt.
"""

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class Tema:
    nome: str
    titulo: str
    # superfícies
    fundo: str
    barra: str
    popup: str
    elevado: str
    segmento: str
    segmento_ativo: str
    ilha: str
    linha: str
    linha_forte: str
    linha_barra: str          # divisória entre a barra e as páginas
    # texto
    texto: str
    texto_suave: str
    texto_apagado: str
    # destaques
    destaque: str
    destaque_claro: str
    texto_sobre_destaque: str
    pendente: str             # ponto do “Salvar” e avisos de alteração
    sucesso: str
    termos_busca: tuple
    resultado_atual: str
    # forma
    raio: int                 # cantos de botões e campos
    raio_grande: int          # cantos de painéis, ilha e diálogos
    chanfro: int              # > 0: cantos cortados em diagonal, desenhados à mão
    brilho: bool              # sombras coloridas (neon) em vez de pretas
    grade: str                # cor da grade do fundo ("" = sem grade)
    pagina: str
    contorno_pagina: str      # "" = sombra preta suave
    cantoneiras: bool         # marcas nos cantos e etiqueta acima da página
    painel_status: bool       # “MODO // SELEÇÃO” no canto da área das páginas
    fichas_contornadas: bool  # termos da busca com contorno em vez de fundo
    caixa_alta: bool          # rótulos em maiúsculas
    traco_icone: str          # "round" ou "square"
    fontes: tuple
    fontes_numeros: tuple


MODERNO = Tema(
    nome="moderno", titulo="Moderno",
    fundo="#131416", barra="#1c1d20", popup="#222327", elevado="#2a2b30", segmento="#26272b",
    segmento_ativo="#34363c", ilha="rgba(38,39,43,0.95)", linha="rgba(255,255,255,0.08)",
    linha_forte="rgba(255,255,255,0.12)", linha_barra="rgba(255,255,255,0.06)",
    texto="#e6e7ea", texto_suave="#9a9da6", texto_apagado="#6c6f78",
    destaque="#8fb0ff", destaque_claro="#a9c2ff", texto_sobre_destaque="#0f1320", pendente="#8fb0ff",
    sucesso="#5fd39a", termos_busca=("#f9c74f", "#2ec4b6", "#e040fb", "#4cc9f0", "#90be6d"),
    resultado_atual="#ff6d00",
    raio=8, raio_grande=12, chanfro=0, brilho=False, grade="", pagina="#ffffff", contorno_pagina="",
    cantoneiras=False, painel_status=False, fichas_contornadas=False, caixa_alta=False, traco_icone="round",
    fontes=("Segoe UI Variable Text", "Segoe UI"), fontes_numeros=("Segoe UI Variable Text", "Segoe UI"),
)

CYBERPUNK = Tema(
    nome="cyberpunk", titulo="Cyberpunk",
    fundo="#07070d", barra="#0b0b14", popup="#0d0d19", elevado="#12122a", segmento="#0f0f1d",
    segmento_ativo="#16243a", ilha="rgba(11,11,20,0.94)", linha="#1c1c33", linha_forte="#2a2a4a",
    linha_barra="#00f0ff",
    texto="#c9d6e8", texto_suave="#6f7a99", texto_apagado="#3d4560",
    destaque="#00f0ff", destaque_claro="#7ff8ff", texto_sobre_destaque="#021014", pendente="#ff2bd6",
    sucesso="#39ff88", termos_busca=("#f5ff3c", "#00f0ff", "#39ff88", "#b18cff", "#ff8a00"),
    resultado_atual="#ff2bd6",
    raio=0, raio_grande=0, chanfro=9, brilho=True, grade="rgba(0,240,255,0.06)", pagina="#f4f4f0",
    contorno_pagina="rgba(0,240,255,0.45)", cantoneiras=True, painel_status=True, fichas_contornadas=True,
    caixa_alta=True, traco_icone="square",
    fontes=("Bahnschrift", "Segoe UI"), fontes_numeros=("Cascadia Mono", "Consolas"),
)

TEMAS = {item.nome: item for item in (MODERNO, CYBERPUNK)}


class TemaAtual:
    """Encaminha a leitura de atributos para o tema em uso."""

    def __init__(self):
        object.__setattr__(self, "_tema", MODERNO)

    def definir(self, nome):
        object.__setattr__(self, "_tema", TEMAS.get(nome, MODERNO))

    def __getattr__(self, nome):
        return getattr(self._tema, nome)


tema = TemaAtual()


# ------------------------------------------------------------------ cores
def cor(texto):
    """QColor a partir de "#rrggbb" ou "rgba(r,g,b,a)" (o QColor não entende rgba())."""
    if texto.startswith("rgba("):
        vermelho, verde, azul, alfa = (parte.strip() for parte in texto[5:-1].split(","))
        return QColor(int(vermelho), int(verde), int(azul), round(float(alfa) * 255))
    return QColor(texto)


def rgba(texto, alfa):
    base = cor(texto)
    return f"rgba({base.red()},{base.green()},{base.blue()},{alfa})"


def rotulo(texto):
    return texto.upper() if tema.caixa_alta else texto


def familia(fontes):
    return ", ".join(f'"{nome}"' for nome in fontes)


# ------------------------------------------------------------------ folha de estilo
def gerar_estilo(t=tema):
    d = t.destaque
    chanfrado = "background: transparent; border: none;"  # o fundo é desenhado à mão
    superficie = (lambda fundo, borda, raio: chanfrado if t.chanfro
                  else f"background: {fundo}; border: 1px solid {borda}; border-radius: {raio}px;")
    letras = "letter-spacing: 1px;" if t.caixa_alta else ""
    return f"""
QWidget {{ color: {t.texto}; }}
#central {{ background: {t.fundo}; }}
#barra {{ background: {t.barra}; }}
#linhaBarra {{ background: {t.linha_barra}; }}
#brilhoBarra {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {rgba(t.linha_barra, 0.28)},
                stop:1 {rgba(t.linha_barra, 0)}); }}
#divisoria {{ background: {t.linha}; }}
QToolButton {{ background: transparent; border: none; border-radius: {t.raio}px; padding: 0 8px;
               min-height: 36px; min-width: 20px; {letras} }}
QToolButton:hover {{ background: {rgba(t.texto, 0.07)}; }}
QToolButton:pressed {{ background: {rgba(t.texto, 0.12)}; }}
QToolButton:checked {{ background: {rgba(d, 0.16)}; color: {d}; }}
QToolButton:disabled {{ color: {t.texto_apagado}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
#segmento {{ background: {t.segmento}; border-radius: {t.raio + 2}px;
             border: 1px solid {t.linha if t.chanfro else t.segmento}; }}
#segmento QToolButton {{ min-height: 30px; border-radius: {max(0, t.raio - 1)}px; }}
#segmento QToolButton:checked {{ background: {t.segmento_ativo}; color: {d if t.chanfro else t.texto}; }}
#campoBusca {{ {superficie(t.fundo, t.linha_forte, t.raio + 2)} }}
#campoBusca[foco="true"] {{ {chanfrado if t.chanfro else f"border: 1px solid {d};"} }}
#campoBusca QLineEdit {{ background: transparent; border: none; padding: 0;
                         selection-background-color: {rgba(d, 0.35)}; }}
#campoBusca QToolButton {{ min-height: 26px; min-width: 26px; padding: 0; border-radius: {max(0, t.raio - 2)}px; }}
#prompt {{ color: {d}; font-family: {familia(t.fontes_numeros)}; }}
#contagem {{ color: {t.texto_suave}; font-family: {familia(t.fontes_numeros)}; }}
#ilha {{ {superficie(t.ilha, t.linha, t.raio_grande + 2)} }}
#ilha QToolButton {{ min-height: 32px; min-width: 32px; padding: 0 6px; }}
#ilha QLineEdit {{ background: {t.fundo if not t.chanfro else "transparent"}; border: none;
                   border-radius: {max(0, t.raio - 2)}px; min-height: 26px;
                   {f"border-bottom: 1px solid {d}; color: {d};" if t.chanfro else ""}
                   font-family: {familia(t.fontes_numeros)}; }}
#ilha QLabel, #botaoZoom {{ font-family: {familia(t.fontes_numeros)}; }}
#ilha QLabel {{ color: {t.texto_suave}; }}
#aviso {{ {superficie(t.elevado, t.linha, t.raio_grande)} }}
#aviso QLabel#detalhe {{ color: {t.texto_suave}; }}
#aviso QPushButton {{ background: transparent; color: {d}; border: none; padding: 4px 8px; min-height: 0; }}
#cartao {{ {superficie(t.popup, t.linha, t.raio_grande)} }}
#rodapeDialogo {{ background: {"transparent" if t.chanfro else t.barra}; border-top: 1px solid {t.linha};
                  border-bottom-left-radius: {t.raio_grande}px; border-bottom-right-radius: {t.raio_grande}px; }}
QLabel#rotuloSecao {{ color: {t.texto_suave}; {letras} }}
QLabel#titulo {{ font-size: 12pt; font-weight: 600; {letras} }}
QLabel#suave {{ color: {t.texto_suave if t.chanfro else "#b8bbc3"}; }}
QLabel#simbolo {{ background: {rgba(d, 0.14)}; border-radius: {t.raio + 2}px;
                  {f"border: 1px solid {rgba(d, 0.5)};" if t.chanfro else ""} }}
QLabel#status {{ color: {t.texto_suave}; font-family: {familia(t.fontes_numeros)}; font-size: 8pt;
                 letter-spacing: 1px; background: {t.barra}; padding: 6px 10px;
                 border-left: 2px solid {d}; }}
QPushButton {{ background: {t.elevado}; border: 1px solid {t.linha_forte}; border-radius: {t.raio}px;
               padding: 0 14px; min-height: 34px; {letras} }}
QPushButton:hover {{ background: {t.segmento_ativo}; }}
QPushButton#plano {{ background: transparent; border: none; color: {t.texto_suave}; }}
QPushButton#plano:hover {{ background: {rgba(t.texto, 0.06)}; }}
QPushButton#principal {{ background: {d}; border: none; color: {t.texto_sobre_destaque};
                         font-weight: 600; padding: 0 16px; }}
QPushButton#principal:hover {{ background: {t.destaque_claro}; }}
QPushButton#link {{ background: transparent; border: none; color: {d}; padding: 0;
                    min-height: 20px; text-align: left; }}
QPushButton#link:hover {{ color: {t.destaque_claro}; }}
QPushButton#rapido {{ background: {rgba(t.texto, 0.05)}; border: none; border-radius: {max(0, t.raio - 2)}px;
                      color: {t.texto_suave}; min-height: 28px; padding: 0 9px;
                      font-family: {familia(t.fontes_numeros)}; }}
QPushButton#rapido:checked {{ background: {rgba(d, 0.16)}; color: {d}; }}
#passo {{ background: {t.fundo}; border: 1px solid {t.linha}; border-radius: {t.raio}px; }}
#passo QToolButton {{ min-height: 30px; min-width: 30px; padding: 0; font-size: 12pt; }}
#passo QLabel {{ font-family: {familia(t.fontes_numeros)}; }}
AreaSoltar {{ {chanfrado if t.chanfro else
               f"background: {rgba(d, 0.04)}; border: 1.5px dashed {rgba(d, 0.35)}; border-radius: 16px;"} }}
AreaSoltar:hover {{ {"" if t.chanfro else f"background: {rgba(d, 0.08)};"} }}
AreaSoltar[arrastando="true"] {{ {"" if t.chanfro else f"background: {rgba(d, 0.12)}; border-color: {d};"} }}
QPushButton#recente {{ background: transparent; border: none; border-radius: {t.raio}px; text-align: left;
                       padding: 8px 10px; min-height: 40px; }}
QPushButton#recente:hover {{ background: {rgba(t.texto, 0.05)}; }}
#tecla {{ background: {t.segmento}; border: 1px solid {t.linha_forte}; border-radius: {max(0, t.raio - 3)}px;
          color: {t.texto_suave}; padding: 1px 7px; font-family: {familia(t.fontes_numeros)}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle {{ background: {rgba(d, 0.55) if t.brilho else "rgba(255,255,255,0.18)"};
                      border-radius: {0 if t.chanfro else 3}px; margin: {4 if t.chanfro else 3}px; }}
QScrollBar::handle:hover {{ background: {d if t.brilho else "rgba(255,255,255,0.34)"}; }}
QScrollBar::handle:vertical {{ min-height: 40px; }}
QScrollBar::handle:horizontal {{ min-width: 40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {t.elevado}; color: {t.texto}; border: 1px solid {t.linha_forte if not t.chanfro else d};
            padding: 5px 8px; }}
QMenu {{ background: {t.popup}; border: 1px solid {t.linha_forte if not t.chanfro else d};
         border-radius: {t.raio + 2}px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: {max(0, t.raio - 2)}px; }}
QMenu::item:selected {{ background: {rgba(d, 0.12) if t.chanfro else rgba(t.texto, 0.07)};
                        {f"color: {d};" if t.chanfro else ""} }}
QMenu::indicator {{ width: 0; }}
QMenu::separator {{ height: 1px; background: {t.linha}; margin: 5px 6px; }}
"""
