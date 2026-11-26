"""Protótipo da interface do PDF Leve em PySide6 (Qt 6).

Experimento visual, separado do programa: reproduz a proposta “moderna” (barra enxuta, busca com
fichas coloridas, ilha de comandos flutuante, painel de cor e tamanho, tela vazia com recentes,
diálogo e avisos) e uma variação “cyberpunk”, para comparar com a interface atual em tkinter.
Os temas ficam em `temas.py`. A busca reaproveita `pdf_leve.servicos.busca`; a renderização é
feita aqui mesmo, sem os processos auxiliares.

Fora do escopo: seleção de texto, anotações e várias janelas.

Uso: python prototipos/pyside6/prototipo.py [arquivo.pdf] [--tema moderno|cyberpunk]
"""

import bisect
import math
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pymupdf  # noqa: E402
from PySide6.QtCore import (  # noqa: E402
    QByteArray, QEventLoop, QPoint, QPropertyAnimation, QRectF, QSettings, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import (  # noqa: E402
    QActionGroup, QColor, QFont, QFontDatabase, QIcon, QImage, QIntValidator, QKeySequence, QPainter,
    QPainterPath, QPen, QPixmap, QShortcut,
)
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QButtonGroup, QColorDialog, QFileDialog, QFrame,
    QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsOpacityEffect, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QPushButton,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from pdf_leve.configuracao.constantes import (  # noqa: E402
    COR_ANOTACAO_PADRAO, CORES_ANOTACAO, ESPACO_ENTRE_PAGINAS, NOME_APLICATIVO, PASSO_ZOOM, PASSO_ZOOM_RODA,
    SEPARADOR_TERMOS_BUSCA, ZOOM_MAXIMO, ZOOM_MINIMO,
)
from pdf_leve.servicos.busca import buscar_termos_na_pagina, separar_termos  # noqa: E402
from temas import TEMAS, cor, gerar_estilo, rgba, rotulo, tema  # noqa: E402

MARGEM_TOPO = 24                 # px acima da primeira página
MARGEM_LATERAL = 24
ESPACO_ILHA = 80                 # espaço extra no fim do documento: a ilha não cobre a última página
DISTANCIA_ILHA = 22              # da ilha até a borda de baixo
PASSO_GRADE = 40                 # px entre as linhas da grade do fundo (tema cyberpunk)
LARGURA_BUSCA = 380
LARGURA_BUSCA_MAXIMA = 620
TAMANHOS_RAPIDOS = (10, 12, 16, 24)
TAMANHO_PADRAO = 12
MAXIMO_RECENTES = 6
DURACAO_AVISO_MS = 2600
TEMPO_POR_ETAPA = 0.03           # s de trabalho por etapa (renderização e busca), sem travar a interface

JANELAS = []  # mantém as janelas vivas (trocar de tema cria uma nova)

# ------------------------------------------------------------------ ícones (traço, 24 × 24)
ICONES = {
    "abrir": '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15'
             'A1.5 1.5 0 0 1 3 17.5z"/>',
    "salvar": '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H16l4 4v12.5a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 5 19.5z"/>'
              '<path d="M8.5 21v-6h7v6"/>',
    "exportar": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                '<path d="M14 3v5h5M12 11v6M9 14l3 3 3-3"/>',
    "importar": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                '<path d="M14 3v5h5M12 18v-6M9 15l3-3 3 3"/>',
    "selecionar": '<path d="M6 4l12 7-5.5 1.5L10 18z"/>',
    "texto": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "buscar": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "acima": '<path d="M6 15l6-6 6 6"/>',
    "abaixo": '<path d="M6 9l6 6 6-6"/>',
    "anterior": '<path d="M15 6l-6 6 6 6"/>',
    "proxima": '<path d="M9 6l6 6-6 6"/>',
    "menos": '<path d="M6 12h12"/>',
    "mais": '<path d="M12 6v12M6 12h12"/>',
    "largura": '<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
    "pagina": '<rect x="6" y="3" width="12" height="18" rx="2"/>',
    "girar": '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    "opcoes": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    "fechar": '<path d="M7 7l10 10M17 7L7 17"/>',
    "ok": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
}


def pixmap_icone(nome, cor_traco, tamanho=18, espessura=1.6):
    juncao = "round" if tema.traco_icone == "round" else "miter"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor_traco}" '
           f'stroke-width="{espessura}" stroke-linecap="{tema.traco_icone}" stroke-linejoin="{juncao}">'
           f'{ICONES[nome]}</svg>')
    razao = 2  # desenha em dobro: nítido em telas com escala
    imagem = QPixmap(tamanho * razao, tamanho * razao)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    QSvgRenderer(QByteArray(svg.encode())).render(pintor)
    pintor.end()
    imagem.setDevicePixelRatio(razao)
    return imagem


def icone(nome, cor_normal=None, cor_ligado=None, tamanho=18):
    resultado = QIcon()
    resultado.addPixmap(pixmap_icone(nome, cor_normal or tema.texto, tamanho), QIcon.Mode.Normal, QIcon.State.Off)
    resultado.addPixmap(pixmap_icone(nome, cor_ligado or tema.destaque, tamanho), QIcon.Mode.Normal, QIcon.State.On)
    resultado.addPixmap(pixmap_icone(nome, tema.texto_apagado, tamanho), QIcon.Mode.Disabled, QIcon.State.Off)
    return resultado


def sombra(widget, raio=32, deslocamento=10, opacidade=130):
    """Sombra preta no tema moderno; brilho neon (sem deslocamento) no cyberpunk."""
    efeito = QGraphicsDropShadowEffect(widget)
    if tema.brilho:
        brilho = cor(tema.destaque)
        brilho.setAlpha(150)
        efeito.setBlurRadius(raio * 0.8)
        efeito.setOffset(0, 0)
        efeito.setColor(brilho)
    else:
        efeito.setBlurRadius(raio)
        efeito.setOffset(0, deslocamento)
        efeito.setColor(QColor(0, 0, 0, opacidade))
    widget.setGraphicsEffect(efeito)


def repolir(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def caminho_chanfrado(retangulo, chanfro):
    """Retângulo com os cantos superior esquerdo e inferior direito cortados em diagonal."""
    r = QRectF(retangulo).adjusted(0.5, 0.5, -0.5, -0.5)
    caminho = QPainterPath()
    caminho.moveTo(r.left() + chanfro, r.top())
    caminho.lineTo(r.right(), r.top())
    caminho.lineTo(r.right(), r.bottom() - chanfro)
    caminho.lineTo(r.right() - chanfro, r.bottom())
    caminho.lineTo(r.left(), r.bottom())
    caminho.lineTo(r.left(), r.top() + chanfro)
    caminho.closeSubpath()
    return caminho


def fonte_numeros(tamanho=None, base=None):
    fonte = QFont(base) if base is not None else QFont()
    fonte.setFamilies(list(tema.fontes_numeros))
    if tamanho:
        fonte.setPointSizeF(tamanho)
    return fonte


# ------------------------------------------------------------------ componentes
class Superficie(QFrame):
    """QFrame cujo fundo, no tema com chanfro, é desenhado à mão (o Qt não corta cantos em diagonal)."""

    tracejada = False

    def cores_superficie(self):
        return tema.popup, rgba(tema.destaque, 0.55)

    def paintEvent(self, evento):
        if not tema.chanfro:
            super().paintEvent(evento)
            return
        fundo, borda = self.cores_superficie()
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        caneta = QPen(cor(borda), 1)
        if self.tracejada:
            caneta.setStyle(Qt.PenStyle.DashLine)
        pintor.setPen(caneta)
        pintor.setBrush(cor(fundo))
        pintor.drawPath(caminho_chanfrado(self.rect(), tema.chanfro))


class BotaoIcone(QToolButton):

    def __init__(self, nome, dica="", cor_ligado=None, tamanho=18, texto=""):
        super().__init__()
        self.setIcon(icone(nome, cor_ligado=cor_ligado, tamanho=tamanho))
        self.setIconSize(QSize(tamanho, tamanho))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        if dica:
            self.setToolTip(dica)
            self.setAccessibleName(dica.split(" (")[0])
        if texto:
            self.setText(rotulo(texto))
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)


class BotaoSalvar(BotaoIcone):
    """Indica alterações não salvas: um ponto no tema moderno, “NÃO SALVO” no cyberpunk."""

    def __init__(self):
        super().__init__("salvar", "Salvar uma cópia (Ctrl+S)")
        self.pendente = False

    def definir_pendente(self, pendente):
        self.pendente = pendente
        self.setAccessibleName("Salvar (há alterações)" if pendente else "Salvar")
        if tema.caixa_alta:
            self.setText(rotulo("Não salvo") if pendente else "")
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if pendente
                                    else Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.setIcon(icone("salvar", tema.pendente if pendente else None))
            self.setStyleSheet(f"color: {tema.pendente}; font-family: {', '.join(tema.fontes_numeros)};"
                               f"font-size: 8pt;" if pendente else "")
        self.update()

    def paintEvent(self, evento):
        super().paintEvent(evento)
        if self.pendente and not tema.caixa_alta:
            pintor = QPainter(self)
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintor.setPen(QPen(cor(tema.barra), 2))
            pintor.setBrush(cor(tema.pendente))
            pintor.drawEllipse(QRectF(self.width() - 15, 6, 8, 8))


def divisoria():
    linha = QFrame()
    linha.setObjectName("divisoria")
    linha.setFixedSize(1, 22)
    return linha


def desenhar_amostra(pintor, area, cor_amostra, borda=None):
    """Amostra de cor: círculo no tema moderno, quadrado chanfrado no cyberpunk."""
    pintor.setPen(QPen(borda, 1.5) if borda else Qt.PenStyle.NoPen)
    pintor.setBrush(cor(cor_amostra) if cor_amostra else Qt.BrushStyle.NoBrush)
    if tema.chanfro:
        pintor.drawPath(caminho_chanfrado(area, max(3, area.width() / 4)))
    else:
        pintor.drawEllipse(area)


def pixmap_amostra(cor_amostra, tamanho=16):
    razao = 2
    imagem = QPixmap(tamanho * razao, tamanho * razao)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    desenhar_amostra(pintor, QRectF(2, 2, tamanho * razao - 4, tamanho * razao - 4), cor_amostra,
                     QColor(255, 255, 255, 70))
    pintor.end()
    imagem.setDevicePixelRatio(razao)
    return imagem


class BotaoCor(QAbstractButton):
    """Amostra de cor do painel de estilo; a escolhida ganha um contorno."""

    def __init__(self, nome, valor):
        super().__init__()
        self.valor = valor
        self.setCheckable(True)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(nome)
        self.setAccessibleName(nome)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        externo = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isChecked():
            desenhar_amostra(pintor, externo, None, cor(tema.destaque if tema.chanfro else tema.texto))
            desenhar_amostra(pintor, externo.adjusted(5, 5, -5, -5), self.valor)
        else:
            if self.underMouse():
                desenhar_amostra(pintor, externo, None, QColor(255, 255, 255, 90))
            desenhar_amostra(pintor, externo.adjusted(3, 3, -3, -3), self.valor, QColor(255, 255, 255, 46))


class Cartao(Superficie):

    def cores_superficie(self):
        return tema.popup, rgba(tema.destaque, 0.6)


class Flutuante(QWidget):
    """Janela sem moldura, com cantos e sombra (o cartão fica dentro de uma margem transparente)."""

    def __init__(self, pai, sinalizadores):
        super().__init__(pai, sinalizadores | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(24, 16, 24, 32)
        self.cartao = Cartao()
        self.cartao.setObjectName("cartao")
        sombra(self.cartao, raio=40, deslocamento=12, opacidade=140)
        externo.addWidget(self.cartao)


class PainelEstilo(Flutuante):
    """Cor e tamanho do texto das anotações (abre pelo botão “● 12 pt” da barra)."""

    mudou = Signal(str, int)

    def __init__(self, pai, cor_atual, tamanho):
        super().__init__(pai, Qt.WindowType.Popup)
        self.cor, self.tamanho = cor_atual, tamanho
        corpo = QVBoxLayout(self.cartao)
        corpo.setContentsMargins(16, 14, 16, 16)
        corpo.setSpacing(8)

        corpo.addWidget(self._rotulo_secao("Cor do texto"))
        grade = QGridLayout()
        grade.setSpacing(4)
        self.grupo_cores = QButtonGroup(self)
        for indice, (nome, valor) in enumerate(CORES_ANOTACAO.items()):
            botao = BotaoCor(nome, valor)
            botao.setChecked(valor.lower() == cor_atual.lower())
            botao.clicked.connect(lambda _=False, valor=valor: self._escolher_cor(valor))
            self.grupo_cores.addButton(botao)
            grade.addWidget(botao, 0, indice)
        corpo.addLayout(grade)
        outra = QPushButton(rotulo("Outra cor…"))
        outra.setObjectName("link")
        outra.setCursor(Qt.CursorShape.PointingHandCursor)
        outra.clicked.connect(self._outra_cor)
        corpo.addWidget(outra, 0, Qt.AlignmentFlag.AlignLeft)

        corpo.addSpacing(4)
        linha = QFrame()
        linha.setObjectName("divisoria")
        linha.setFixedHeight(1)
        corpo.addWidget(linha)
        corpo.addSpacing(4)

        corpo.addWidget(self._rotulo_secao("Tamanho"))
        fileira = QHBoxLayout()
        fileira.setSpacing(10)
        passo = QFrame()
        passo.setObjectName("passo")
        caixa = QHBoxLayout(passo)
        caixa.setContentsMargins(0, 0, 0, 0)
        caixa.setSpacing(0)
        menos = QToolButton()
        menos.setText("−")
        menos.setAccessibleName("Diminuir tamanho")
        menos.clicked.connect(lambda: self._definir_tamanho(self.tamanho - 1))
        self.rotulo_tamanho = QLabel()
        self.rotulo_tamanho.setFixedWidth(50)
        self.rotulo_tamanho.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mais = QToolButton()
        mais.setText("+")
        mais.setAccessibleName("Aumentar tamanho")
        mais.clicked.connect(lambda: self._definir_tamanho(self.tamanho + 1))
        for item in (menos, self.rotulo_tamanho, mais):
            caixa.addWidget(item)
        fileira.addWidget(passo)
        self.rapidos = {}
        for valor in TAMANHOS_RAPIDOS:
            botao = QPushButton(str(valor))
            botao.setObjectName("rapido")
            botao.setCheckable(True)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.setAccessibleName(f"{valor} pt")
            botao.clicked.connect(lambda _=False, valor=valor: self._definir_tamanho(valor))
            self.rapidos[valor] = botao
            fileira.addWidget(botao)
        fileira.addStretch()
        corpo.addLayout(fileira)

        corpo.addSpacing(6)
        self.previa = QLabel("Prévia da anotação")
        self.previa.setMinimumHeight(52)
        corpo.addWidget(self.previa)
        self._mostrar()

    @staticmethod
    def _rotulo_secao(texto):
        etiqueta = QLabel(rotulo(texto))
        etiqueta.setObjectName("rotuloSecao")
        return etiqueta

    def abrir_abaixo_de(self, ancora):
        self.adjustSize()
        base = ancora.mapToGlobal(QPoint(ancora.width() // 2, ancora.height()))
        self.move(base.x() - self.width() // 2, base.y() - 10)
        self.show()

    def _escolher_cor(self, valor):
        self.cor = valor
        self._mostrar()
        self.mudou.emit(self.cor, self.tamanho)

    def _outra_cor(self):
        self.hide()
        escolhida = QColorDialog.getColor(QColor(self.cor), self.parentWidget(), "Outra cor")
        if escolhida.isValid():
            self._escolher_cor(escolhida.name())
        self.close()

    def _definir_tamanho(self, valor):
        self.tamanho = max(6, min(72, valor))
        self._mostrar()
        self.mudou.emit(self.cor, self.tamanho)

    def _mostrar(self):
        self.rotulo_tamanho.setText(f"{self.tamanho} pt" if not tema.caixa_alta else f"{self.tamanho}PT")
        for valor, botao in self.rapidos.items():
            botao.setChecked(valor == self.tamanho)
        raio = 0 if tema.chanfro else 8
        self.previa.setStyleSheet(
            f"background: {tema.pagina}; color: {self.cor}; border-radius: {raio}px; padding: 10px 14px;"
            f"font-family: Helvetica, Arial; font-size: {min(self.tamanho, 28)}pt;")


class Ficha(QFrame):
    """Termo de busca já confirmado, na cor do realce que ele recebe na página."""

    remover = Signal(int)

    def __init__(self, indice, termo):
        super().__init__()
        self.indice = indice
        base = cor(tema.termos_busca[indice % len(tema.termos_busca)])
        if tema.fichas_contornadas:
            clara = base.name()
            fundo = f"background: transparent; border: 1px solid {clara}; border-radius: 0;"
        else:
            clara = base.lighter(125).name()
            fundo = f"background: rgba({base.red()},{base.green()},{base.blue()},0.16); border-radius: 6px;"
        self.setStyleSheet(
            f"Ficha {{ {fundo} }} QLabel {{ color: {clara}; border: none; background: transparent; }}"
            f"QToolButton {{ color: {clara}; min-height: 18px; min-width: 18px; padding: 0; border-radius: 4px; }}")
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(8, 0, 2, 0)
        caixa.setSpacing(4)
        self.rotulo = QLabel(termo)
        self.quantidade = QLabel("")
        self.quantidade.setStyleSheet(f"color: {rgba(clara, 0.6)};")
        self.quantidade.setFont(fonte_numeros(base=self.font()))
        fechar = QToolButton()
        fechar.setText("×")
        fechar.setAccessibleName(f"Remover “{termo}”")
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.clicked.connect(lambda: self.remover.emit(self.indice))
        for item in (self.rotulo, self.quantidade, fechar):
            caixa.addWidget(item)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if tema.fichas_contornadas:
            self.rotulo.setFont(fonte_numeros(base=self.font()))

    def definir_quantidade(self, quantidade):
        texto = "" if quantidade is None else str(quantidade)
        if texto != self.quantidade.text():
            self.quantidade.setText(texto)
            self.parentWidget()._ajustar_largura()


class CampoBusca(Superficie):
    """Campo de busca com uma ficha colorida por termo (“;” ou Enter confirmam o termo)."""

    buscar = Signal(list)
    proximo = Signal()
    anterior = Signal()
    limpar = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("campoBusca")
        self.setFixedHeight(36)
        self.setFixedWidth(LARGURA_BUSCA)
        self.termos, self.fichas, self.termos_buscados = [], [], []
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(10, 0, 4, 0)
        caixa.setSpacing(6)
        if tema.caixa_alta:
            lupa = QLabel(">")
            lupa.setObjectName("prompt")
        else:
            lupa = QLabel()
            lupa.setPixmap(pixmap_icone("buscar", tema.texto_suave, 16, 1.8))
        caixa.addWidget(lupa)
        self.caixa_fichas = QHBoxLayout()
        self.caixa_fichas.setSpacing(4)
        caixa.addLayout(self.caixa_fichas)
        self.entrada = QLineEdit()
        self.entrada.setMinimumWidth(60)
        self.entrada.textChanged.connect(self._ao_mudar_texto)
        self.entrada.installEventFilter(self)
        caixa.addWidget(self.entrada, 1)
        self.contagem = QLabel("")
        self.contagem.setObjectName("contagem")
        caixa.addWidget(self.contagem)
        self.botao_anterior = BotaoIcone("acima", "Anterior (Shift+Enter)", tamanho=15)
        self.botao_anterior.clicked.connect(self.anterior)
        self.botao_proximo = BotaoIcone("abaixo", "Próximo (Enter / F3)", tamanho=15)
        self.botao_proximo.clicked.connect(self.proximo)
        caixa.addWidget(self.botao_anterior)
        caixa.addWidget(self.botao_proximo)
        self._mostrar_dica()
        if tema.brilho:
            sombra(self, raio=18)
            self.graphicsEffect().setEnabled(False)  # o brilho acende só com o foco

    def cores_superficie(self):
        return "#05050a", tema.destaque if self.property("foco") else tema.linha_forte

    def _mostrar_dica(self):
        dica = f"Buscar  ·  “{SEPARADOR_TERMOS_BUSCA}” separa termos"
        self.entrada.setPlaceholderText("" if self.termos else (dica.upper() if tema.caixa_alta else dica))

    def focar(self):
        self.entrada.setFocus()
        self.entrada.selectAll()

    def eventFilter(self, objeto, evento):
        tipo = evento.type()
        if tipo in (evento.Type.FocusIn, evento.Type.FocusOut):
            focado = tipo == evento.Type.FocusIn
            self.setProperty("foco", focado)
            if self.graphicsEffect():
                self.graphicsEffect().setEnabled(focado)
            repolir(self)
            self.update()
        elif tipo == evento.Type.KeyPress:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if evento.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.anterior.emit()
                else:
                    self._confirmar()
                return True
            if tecla == Qt.Key.Key_Escape:
                self.limpar_tudo()
                self.limpar.emit()
                return True
            if tecla == Qt.Key.Key_Backspace and not self.entrada.text() and self.termos:
                self._remover(len(self.termos) - 1)
                return True
        return super().eventFilter(objeto, evento)

    def _ao_mudar_texto(self, texto):
        if SEPARADOR_TERMOS_BUSCA in texto:
            *prontos, resto = texto.split(SEPARADOR_TERMOS_BUSCA)
            self.entrada.blockSignals(True)
            self.entrada.setText(resto.lstrip())
            self.entrada.blockSignals(False)
            self._definir_termos(self.termos + prontos)

    def _confirmar(self):
        texto = self.entrada.text()
        if texto.strip():
            self.entrada.clear()
            self._definir_termos(self.termos + [texto])
        if self.termos and self.termos != self.termos_buscados:
            self.termos_buscados = list(self.termos)
            self.buscar.emit(list(self.termos))
        elif self.termos:
            self.proximo.emit()

    def _remover(self, indice):
        termos = list(self.termos)
        del termos[indice]
        self._definir_termos(termos)
        self.termos_buscados = list(self.termos)
        if self.termos:
            self.buscar.emit(list(self.termos))
        else:
            self.limpar.emit()

    def _definir_termos(self, termos):
        self.termos = separar_termos(SEPARADOR_TERMOS_BUSCA.join(termos))
        for ficha in self.fichas:
            ficha.deleteLater()
        self.fichas = []
        for indice, termo in enumerate(self.termos):
            ficha = Ficha(indice, termo)
            ficha.remover.connect(self._remover)
            self.caixa_fichas.addWidget(ficha)
            self.fichas.append(ficha)
        self._mostrar_dica()
        self._ajustar_largura()

    def _ajustar_largura(self):
        fichas = sum(ficha.sizeHint().width() + 4 for ficha in self.fichas)
        self.setFixedWidth(min(LARGURA_BUSCA_MAXIMA, max(LARGURA_BUSCA, fichas + LARGURA_BUSCA - 120)))

    def limpar_tudo(self):
        self.entrada.clear()
        self._definir_termos([])
        self.termos_buscados = []
        self.contagem.setText("")

    def mostrar_contagem(self, atual, total, por_termo, terminou):
        for ficha, quantidade in zip(self.fichas, por_termo):
            ficha.definir_quantidade(quantidade)
        if total == 0:
            self.contagem.setText(rotulo("buscando…") if not terminou else rotulo("nada"))
        elif tema.caixa_alta:
            self.contagem.setText(f"{atual:02d}/{total:02d}" + ("" if terminou else "…"))
        else:
            self.contagem.setText(f"{atual}/{total}" + ("" if terminou else "…"))


class IlhaComandos(Superficie):
    """Navegação, zoom, ajuste e rotação, flutuando no rodapé da área das páginas."""

    def __init__(self, pai):
        super().__init__(pai)
        self.setObjectName("ilha")
        sombra(self, raio=30, deslocamento=10, opacidade=140)
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(10 if tema.chanfro else 5, 5, 10 if tema.chanfro else 5, 5)
        caixa.setSpacing(2)
        self.botao_anterior = BotaoIcone("anterior", "Página anterior (←)")
        self.campo_pagina = QLineEdit("1")
        self.campo_pagina.setFixedWidth(38)
        self.campo_pagina.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.campo_pagina.setAccessibleName("Página atual")
        self.campo_pagina.setValidator(QIntValidator(1, 999999))
        self.rotulo_total = QLabel("de 1")
        self.botao_proxima = BotaoIcone("proxima", "Próxima página (→)")
        self.botao_menos = BotaoIcone("menos", "Diminuir zoom (Ctrl −)")
        self.botao_zoom = QToolButton()
        self.botao_zoom.setObjectName("botaoZoom")
        self.botao_zoom.setText("100%")
        self.botao_zoom.setMinimumWidth(62)
        self.botao_zoom.setToolTip("Zoom · clique para opções")
        self.botao_zoom.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.botao_mais = BotaoIcone("mais", "Aumentar zoom (Ctrl +)")
        self.botao_largura = BotaoIcone("largura", "Ajustar à largura (Ctrl+1)")
        self.botao_pagina = BotaoIcone("pagina", "Página inteira (Ctrl+2)")
        self.botao_girar = BotaoIcone("girar", "Girar página (Ctrl+R)")
        for botao in (self.botao_largura, self.botao_pagina):
            botao.setCheckable(True)
        caixa.addWidget(self.botao_anterior)
        caixa.addSpacing(4)
        caixa.addWidget(self.campo_pagina)
        caixa.addSpacing(2)
        caixa.addWidget(self.rotulo_total)
        caixa.addSpacing(4)
        caixa.addWidget(self.botao_proxima)
        for grupo in ((self.botao_menos, self.botao_zoom, self.botao_mais),
                      (self.botao_largura, self.botao_pagina, self.botao_girar)):
            caixa.addSpacing(4)
            caixa.addWidget(divisoria())
            caixa.addSpacing(4)
            for botao in grupo:
                caixa.addWidget(botao)

    def cores_superficie(self):
        return tema.ilha, tema.destaque

    def definir_total(self, total):
        self.rotulo_total.setText(f"/ {total:02d}" if tema.caixa_alta else f"de {total}")

    def definir_pagina(self, pagina):
        self.campo_pagina.setText(f"{pagina:02d}" if tema.caixa_alta else str(pagina))


class Aviso(Superficie):
    """Aviso discreto acima da ilha, que some sozinho (com ação opcional, ex.: “Desfazer”)."""

    def __init__(self, pai):
        super().__init__(pai)
        self.setObjectName("aviso")
        caixa = QHBoxLayout(self)
        caixa.setContentsMargins(14, 0, 6, 0)
        caixa.setSpacing(10)
        self.icone = QLabel()
        self.texto = QLabel()
        self.detalhe = QLabel()
        self.detalhe.setObjectName("detalhe")
        self.acao = QPushButton()
        self.acao.setCursor(Qt.CursorShape.PointingHandCursor)
        for item in (self.icone, self.texto, self.detalhe, self.acao):
            caixa.addWidget(item)
        self.setFixedHeight(42)
        self.opacidade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacidade)
        self.animacao = QPropertyAnimation(self.opacidade, b"opacity", self)
        self.animacao.setDuration(180)
        self.animacao.finished.connect(lambda: self.opacidade.opacity() == 0 and self.hide())
        self.temporizador = QTimer(self, singleShot=True, timeout=self.esconder)
        self.comando = None
        self.acao.clicked.connect(self._executar)
        self.hide()

    def cores_superficie(self):
        return tema.elevado, rgba(tema.destaque, 0.5)

    def mostrar(self, texto, detalhe="", tipo="info", acao=None, comando=None):
        cor_icone = tema.sucesso if tipo == "ok" else tema.destaque
        self.icone.setPixmap(pixmap_icone(tipo, cor_icone, 16, 2))
        self.texto.setText(rotulo(texto))
        self.detalhe.setText(detalhe)
        self.detalhe.setVisible(bool(detalhe))
        self.acao.setText(rotulo(acao or ""))
        self.acao.setVisible(bool(acao))
        self.comando = comando
        self.adjustSize()
        self.parentWidget().posicionar_flutuantes()
        visivel = self.isVisible()
        self.show()
        self.raise_()
        self.animacao.stop()
        self.animacao.setStartValue(self.opacidade.opacity() if visivel else 0.0)
        self.animacao.setEndValue(1.0)
        self.animacao.start()
        self.temporizador.start(DURACAO_AVISO_MS)

    def esconder(self):
        self.animacao.stop()
        self.animacao.setStartValue(self.opacidade.opacity())
        self.animacao.setEndValue(0.0)
        self.animacao.start()

    def _executar(self):
        if self.comando:
            self.comando()
        self.esconder()


class DialogoSalvar(Flutuante):
    """“Salvar as alterações?” com ícone, título, texto e rodapé de botões."""

    def __init__(self, pai, nome_arquivo, descricao):
        super().__init__(pai, Qt.WindowType.Dialog)
        self.resultado = "cancelar"
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.cartao.setFixedWidth(470)
        corpo = QVBoxLayout(self.cartao)
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        topo = QHBoxLayout()
        topo.setContentsMargins(24, 22, 24, 20)
        topo.setSpacing(14)
        simbolo = QLabel()
        simbolo.setObjectName("simbolo")
        simbolo.setFixedSize(36, 36)
        simbolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        simbolo.setPixmap(pixmap_icone("salvar", tema.destaque, 18, 1.7))
        topo.addWidget(simbolo, 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(6)
        titulo = QLabel(rotulo("Salvar as alterações?"))
        titulo.setObjectName("titulo")
        mensagem = QLabel(f"{nome_arquivo} tem alterações que ainda não foram salvas ({descricao}).")
        mensagem.setObjectName("suave")
        mensagem.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensagem)
        topo.addLayout(textos, 1)
        corpo.addLayout(topo)
        rodape = QFrame()
        rodape.setObjectName("rodapeDialogo")
        botoes = QHBoxLayout(rodape)
        botoes.setContentsMargins(16, 14, 16, 14)
        botoes.setSpacing(8)
        botoes.addStretch()
        for texto, nome, valor in (("Cancelar", "plano", "cancelar"), ("Não salvar", "", "descartar"),
                                   ("Salvar", "principal", "salvar")):
            botao = QPushButton(rotulo(texto))
            botao.setObjectName(nome)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.clicked.connect(lambda _=False, valor=valor: self._concluir(valor))
            botoes.addWidget(botao)
            if valor == "salvar":
                botao.setDefault(True)
                botao.setFocus()
        corpo.addWidget(rodape)
        QShortcut(QKeySequence("Esc"), self, activated=lambda: self._concluir("cancelar"))
        self._laco = None

    def executar(self):
        self.adjustSize()
        pai = self.parentWidget()
        centro = pai.mapToGlobal(pai.rect().center())
        self.move(centro.x() - self.width() // 2, centro.y() - self.height() // 2 - 40)
        self._laco = QEventLoop()
        self.show()
        self._laco.exec()
        return self.resultado

    def _concluir(self, valor):
        self.resultado = valor
        self.close()
        if self._laco:
            self._laco.quit()


# ------------------------------------------------------------------ páginas
class ItemPagina(QGraphicsItem):
    """Página com sombra (ou brilho); a imagem renderizada é desenhada por cima quando fica pronta."""

    def __init__(self, indice):
        super().__init__()
        self.indice, self.largura, self.altura = indice, 1.0, 1.0
        self.pontos = (0, 0)  # tamanho em pontos, para a etiqueta do tema cyberpunk
        self.imagem, self.escala_imagem = None, 0.0

    def definir_tamanho(self, largura, altura, pontos):
        self.prepareGeometryChange()
        self.largura, self.altura, self.pontos = largura, altura, pontos

    def definir_imagem(self, imagem, escala):
        self.imagem, self.escala_imagem = imagem, escala
        self.update()

    def boundingRect(self):
        return QRectF(-14, -30, self.largura + 28, self.altura + 46)

    def paint(self, pintor, opcao, widget=None):
        pagina = QRectF(0, 0, self.largura, self.altura)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setPen(Qt.PenStyle.NoPen)
        if tema.contorno_pagina:
            brilho = cor(tema.destaque)
            for passo in range(1, 9):
                brilho.setAlpha(7)
                pintor.setBrush(brilho)
                pintor.drawRect(pagina.adjusted(-passo * 1.5, -passo * 1.5, passo * 1.5, passo * 1.5))
            pintor.setBrush(cor(tema.pagina))
            pintor.setPen(QPen(cor(tema.contorno_pagina), 1))
            pintor.drawRect(pagina)
        else:
            for passo in range(1, 8):  # sombra suave em camadas: barata e sem efeitos gráficos
                pintor.setBrush(QColor(0, 0, 0, 13))
                pintor.drawRoundedRect(pagina.adjusted(-passo, -passo + 4, passo, passo + 6), 2 + passo, 2 + passo)
            pintor.setBrush(cor(tema.pagina))
            pintor.drawRoundedRect(pagina, 2, 2)
        if self.imagem is not None:
            pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            pintor.drawPixmap(pagina, self.imagem, QRectF(0, 0, self.imagem.width(), self.imagem.height()))
        if tema.cantoneiras:
            self._desenhar_cantoneiras(pintor, pagina)

    def _desenhar_cantoneiras(self, pintor, pagina):
        pintor.setPen(QPen(cor(tema.destaque), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        afastamento, braco = 8, 20
        r = pagina.adjusted(-afastamento, -afastamento, afastamento, afastamento)
        for x, y, dx, dy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                             (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
            pintor.drawLine(QPoint(round(x), round(y)), QPoint(round(x + dx * braco), round(y)))
            pintor.drawLine(QPoint(round(x), round(y)), QPoint(round(x), round(y + dy * braco)))
        pintor.setPen(cor(tema.texto_suave))
        pintor.setFont(fonte_numeros(7.5))
        largura, altura = self.pontos
        pintor.drawText(QPoint(round(r.left()), round(r.top()) - 7),
                        f"PÁG_{self.indice + 1:02d} · {largura:.0f}×{altura:.0f} PT")


class VisaoPaginas(QGraphicsView):
    pagina_mudou = Signal(int)
    zoom_mudou = Signal(float, str)

    def __init__(self):
        super().__init__()
        self.cena = QGraphicsScene(self)
        self.setScene(self.cena)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(cor(tema.fundo))
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.documento, self.itens, self.tamanhos, self.matrizes, self.topos = None, [], [], [], []
        self.zoom, self.modo_ajuste = 1.0, "largura"
        self.realces = []
        self._resultados, self._atual = [], None
        self.ilha = IlhaComandos(self)
        self.aviso = Aviso(self)
        self.status = QLabel(self)
        self.status.setObjectName("status")
        self.status.setVisible(False)
        self.status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.temporizador = QTimer(self, singleShot=True, interval=20, timeout=self._renderizar_visiveis)
        self.verticalScrollBar().valueChanged.connect(self._ao_rolar)
        self.horizontalScrollBar().valueChanged.connect(lambda _: self.temporizador.start())
        self._ultima_pagina = -1

    # ---------------------------------------------------- documento e disposição
    def carregar(self, documento):
        self.cena.clear()
        self.documento, self.realces = documento, []
        self._resultados, self._atual = [], None
        self.itens, self.tamanhos, self.matrizes = [], [], []
        for indice in range(len(documento)):
            item = ItemPagina(indice)
            self.cena.addItem(item)
            self.itens.append(item)
        self.atualizar_medidas()
        self._ultima_pagina = -1
        self.status.setVisible(tema.painel_status)
        self.aplicar_ajuste()
        self.verticalScrollBar().setValue(0)
        self._ao_rolar()

    def atualizar_medidas(self, indices=None):
        for indice in (range(len(self.documento)) if indices is None else indices):
            pagina = self.documento[indice]
            medida = (pagina.rect.width, pagina.rect.height)
            if indice < len(self.tamanhos):
                self.tamanhos[indice], self.matrizes[indice] = medida, pagina.rotation_matrix
            else:
                self.tamanhos.append(medida)
                self.matrizes.append(pagina.rotation_matrix)

    def dispor(self):
        y, maior = MARGEM_TOPO + (14 if tema.cantoneiras else 0), 1.0
        self.topos = []
        for item, (largura, altura) in zip(self.itens, self.tamanhos):
            item.definir_tamanho(largura * self.zoom, altura * self.zoom, (largura, altura))
            item.setPos(-largura * self.zoom / 2, y)
            self.topos.append(y)
            y += altura * self.zoom + ESPACO_ENTRE_PAGINAS + (24 if tema.cantoneiras else 0)
            maior = max(maior, largura * self.zoom)
        altura_total = y - ESPACO_ENTRE_PAGINAS + MARGEM_TOPO + ESPACO_ILHA
        self.cena.setSceneRect(-maior / 2 - MARGEM_LATERAL, 0, maior + 2 * MARGEM_LATERAL, altura_total)
        self.redesenhar_realces()

    def drawBackground(self, pintor, area):
        super().drawBackground(pintor, area)
        if not tema.grade:
            return
        pintor.setPen(QPen(cor(tema.grade), 0))  # espessura 0: sempre 1 px, em qualquer zoom
        x = math.floor(area.left() / PASSO_GRADE) * PASSO_GRADE
        while x < area.right():
            pintor.drawLine(QPoint(round(x), round(area.top())), QPoint(round(x), round(area.bottom())))
            x += PASSO_GRADE
        y = math.floor(area.top() / PASSO_GRADE) * PASSO_GRADE
        while y < area.bottom():
            pintor.drawLine(QPoint(round(area.left()), round(y)), QPoint(round(area.right()), round(y)))
            y += PASSO_GRADE

    # ---------------------------------------------------- zoom
    def _zoom_do_ajuste(self, modo):
        if not self.tamanhos:
            return self.zoom
        folga = 2 * MARGEM_LATERAL + 2 + (36 if tema.cantoneiras else 0)
        largura_util = self.viewport().width() - folga
        if modo == "largura":
            return largura_util / max(largura for largura, _ in self.tamanhos)
        largura, altura = self.tamanhos[self.pagina_atual()]
        altura_util = self.viewport().height() - MARGEM_TOPO - ESPACO_ILHA - (30 if tema.cantoneiras else 0)
        return min(largura_util / largura, altura_util / altura)

    def aplicar_ajuste(self, modo=None):
        if modo:
            self.modo_ajuste = modo
        if self.modo_ajuste:
            self.definir_zoom(self._zoom_do_ajuste(self.modo_ajuste), manter_ajuste=True)

    def definir_zoom(self, zoom, manter_ajuste=False):
        if self.documento is None:
            return
        if not manter_ajuste:
            self.modo_ajuste = None
        zoom = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, zoom))
        pagina = self.pagina_atual() if self.topos else 0
        fracao = 0.0
        if self.topos:
            topo_visivel = self.mapToScene(QPoint(0, 0)).y()
            fracao = (topo_visivel - self.topos[pagina]) / max(1.0, self.tamanhos[pagina][1] * self.zoom)
        self.zoom = zoom
        self.dispor()
        if self.modo_ajuste == "pagina":
            self.verticalScrollBar().setValue(int(self.topos[pagina] - MARGEM_TOPO))
        else:
            self.verticalScrollBar().setValue(int(self.topos[pagina] + fracao * self.tamanhos[pagina][1] * zoom))
        self.zoom_mudou.emit(self.zoom, self.modo_ajuste or "")
        self.temporizador.start()

    # ---------------------------------------------------- navegação
    def pagina_atual(self):
        if not self.topos:
            return 0
        y = self.mapToScene(QPoint(0, int(self.viewport().height() * 0.3))).y()
        return max(0, min(len(self.topos) - 1, bisect.bisect_right(self.topos, y) - 1))

    def ir_para_pagina(self, indice):
        if self.topos:
            indice = max(0, min(len(self.topos) - 1, indice))
            self.verticalScrollBar().setValue(int(self.topos[indice] - MARGEM_TOPO))

    def _ao_rolar(self, *_):
        pagina = self.pagina_atual()
        if pagina != self._ultima_pagina:
            self._ultima_pagina = pagina
            self.pagina_mudou.emit(pagina)
        self.temporizador.start()

    def paginas_visiveis(self, margem=1):
        if not self.topos:
            return range(0)
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        primeira = max(0, bisect.bisect_right(self.topos, area.top()) - 1 - margem)
        ultima = min(len(self.topos) - 1, bisect.bisect_right(self.topos, area.bottom()) - 1 + margem)
        return range(primeira, ultima + 1)

    # ---------------------------------------------------- renderização
    def _renderizar_visiveis(self):
        if self.documento is None:
            return
        visiveis = self.paginas_visiveis()
        razao = self.devicePixelRatioF()
        escala = self.zoom * razao
        inicio = time.perf_counter()
        for indice in visiveis:
            item = self.itens[indice]
            if item.imagem is not None and abs(item.escala_imagem - escala) < 1e-6:
                continue
            if time.perf_counter() - inicio > TEMPO_POR_ETAPA:
                self.temporizador.start(0)  # continua na próxima volta do laço de eventos
                break
            imagem_mupdf = self.documento[indice].get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)
            imagem = QImage(imagem_mupdf.samples, imagem_mupdf.width, imagem_mupdf.height, imagem_mupdf.stride,
                            QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(imagem)
            pixmap.setDevicePixelRatio(razao)
            item.definir_imagem(pixmap, escala)
        if visiveis:
            for indice, item in enumerate(self.itens):  # libera a memória das páginas distantes
                if item.imagem is not None and not (visiveis.start - 3 <= indice < visiveis.stop + 3):
                    item.definir_imagem(None, 0.0)

    def invalidar_pagina(self, indice):
        self.itens[indice].definir_imagem(None, 0.0)
        self.atualizar_medidas([indice])
        self.dispor()
        self.temporizador.start()

    # ---------------------------------------------------- realces da busca
    def redesenhar_realces(self, resultados=None, atual=None):
        if resultados is not None:
            self._resultados, self._atual = resultados, atual
        for item, _ in self.realces:
            self.cena.removeItem(item)
        self.realces = []
        for indice, (pagina, retangulo, termo) in enumerate(self._resultados):
            item = QGraphicsRectItem(self.area_resultado(pagina, retangulo))
            if indice == self._atual:
                cor_realce = cor(tema.resultado_atual)
                item.setPen(QPen(cor_realce, 2))
                cor_realce.setAlpha(100)
            else:
                cor_realce = cor(tema.termos_busca[termo % len(tema.termos_busca)])
                item.setPen(Qt.PenStyle.NoPen)
                cor_realce.setAlpha(115)
            item.setBrush(cor_realce)
            item.setZValue(1)
            self.cena.addItem(item)
            self.realces.append((item, indice))

    def area_resultado(self, pagina, retangulo):
        r = pymupdf.Rect(retangulo) * self.matrizes[pagina]
        item = self.itens[pagina]
        return QRectF(item.x() + r.x0 * self.zoom - 1, item.y() + r.y0 * self.zoom - 1,
                      r.width * self.zoom + 2, r.height * self.zoom + 2)

    def mostrar_area(self, area):
        self.ensureVisible(area, 60, int(self.viewport().height() * 0.3))

    # ---------------------------------------------------- eventos
    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.posicionar_flutuantes()
        if self.modo_ajuste and self.documento is not None:
            self.aplicar_ajuste()
        self.temporizador.start()

    def posicionar_flutuantes(self):
        area = self.viewport().geometry()
        self.ilha.adjustSize()
        x = area.x() + (area.width() - self.ilha.width()) // 2
        y = area.bottom() - self.ilha.height() - DISTANCIA_ILHA
        self.ilha.move(x, y)
        self.aviso.adjustSize()
        self.aviso.move(area.x() + (area.width() - self.aviso.width()) // 2, y - self.aviso.height() - 12)
        self.status.adjustSize()
        self.status.move(area.x() + 16, area.bottom() - self.status.height() - DISTANCIA_ILHA - 4)

    def definir_status(self, linhas):
        self.status.setText("\n".join(linhas))
        self.posicionar_flutuantes()

    def wheelEvent(self, evento):
        if evento.modifiers() & Qt.KeyboardModifier.ControlModifier and self.documento is not None:
            passos = evento.angleDelta().y() / 120
            self.definir_zoom(self.zoom * (PASSO_ZOOM_RODA ** passos))
            return
        super().wheelEvent(evento)

    def keyPressEvent(self, evento):
        tecla = evento.key()
        sem_modificador = not evento.modifiers()
        if tecla == Qt.Key.Key_Right and sem_modificador:
            self.ir_para_pagina(self.pagina_atual() + 1)
        elif tecla == Qt.Key.Key_Left and sem_modificador:
            self.ir_para_pagina(self.pagina_atual() - 1)
        elif tecla == Qt.Key.Key_Home:
            self.ir_para_pagina(0)
        elif tecla == Qt.Key.Key_End:
            self.ir_para_pagina(len(self.topos) - 1)
        else:
            super().keyPressEvent(evento)


# ------------------------------------------------------------------ tela vazia
class AreaSoltar(Superficie):
    """Área tracejada da tela vazia: clicar (ou Enter/Espaço) abre o diálogo de arquivo."""

    clicada = Signal()
    tracejada = True

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def cores_superficie(self):
        destaque = self.underMouse() or self.property("arrastando")
        return rgba(tema.destaque, 0.09 if destaque else 0.03), rgba(tema.destaque, 0.9 if destaque else 0.45)

    def enterEvent(self, evento):
        self.update()

    def leaveEvent(self, evento):
        self.update()

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton and self.rect().contains(evento.position().toPoint()):
            self.clicada.emit()

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicada.emit()
        else:
            super().keyPressEvent(evento)


class TelaVazia(QWidget):

    def __init__(self, ao_abrir, ao_abrir_recente):
        super().__init__()
        self.ao_abrir_recente = ao_abrir_recente
        externo = QVBoxLayout(self)
        externo.setContentsMargins(40, 40, 40, 40)
        externo.addStretch()
        linha = QHBoxLayout()
        linha.setSpacing(20)
        linha.addStretch()

        self.area_soltar = AreaSoltar()
        self.area_soltar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.area_soltar.setFixedSize(420, 340)
        self.area_soltar.setAccessibleName("Abrir PDF")
        self.area_soltar.clicada.connect(ao_abrir)
        conteudo = QVBoxLayout(self.area_soltar)
        conteudo.setSpacing(12)
        conteudo.addStretch()
        simbolo = QLabel()
        simbolo.setObjectName("simbolo")
        simbolo.setFixedSize(64, 64)
        simbolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        simbolo.setPixmap(pixmap_icone("importar", tema.destaque, 30, 1.5))
        conteudo.addWidget(simbolo, 0, Qt.AlignmentFlag.AlignCenter)
        titulo = QLabel(rotulo("Arraste PDFs para cá"))
        titulo.setObjectName("titulo")
        conteudo.addWidget(titulo, 0, Qt.AlignmentFlag.AlignCenter)
        subtitulo = QLabel("ou clique para abrir")
        subtitulo.setStyleSheet(f"color: {tema.texto_suave}; background: transparent;")
        conteudo.addWidget(subtitulo, 0, Qt.AlignmentFlag.AlignCenter)
        teclas = QHBoxLayout()
        teclas.setSpacing(4)
        teclas.addStretch()
        for texto in ("Ctrl", "O"):
            tecla = QLabel(rotulo(texto))
            tecla.setObjectName("tecla")
            teclas.addWidget(tecla)
        teclas.addStretch()
        conteudo.addLayout(teclas)
        conteudo.addStretch()
        for filho in self.area_soltar.findChildren(QLabel):
            filho.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        linha.addWidget(self.area_soltar)

        self.coluna_recentes = QWidget()
        self.coluna_recentes.setFixedWidth(260)
        self.caixa_recentes = QVBoxLayout(self.coluna_recentes)
        self.caixa_recentes.setContentsMargins(0, 0, 0, 0)
        self.caixa_recentes.setSpacing(2)
        linha.addWidget(self.coluna_recentes, 0, Qt.AlignmentFlag.AlignTop)
        linha.addStretch()
        externo.addLayout(linha)
        externo.addStretch()

    def mostrar_recentes(self, caminhos):
        while self.caixa_recentes.count():
            item = self.caixa_recentes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.coluna_recentes.setVisible(bool(caminhos))
        if not caminhos:
            return
        etiqueta = QLabel(rotulo("Recentes"))
        etiqueta.setObjectName("rotuloSecao")
        etiqueta.setContentsMargins(10, 6, 0, 8)
        self.caixa_recentes.addWidget(etiqueta)
        for caminho in caminhos:
            botao = QPushButton()
            botao.setObjectName("recente")
            botao.setIcon(QIcon(self._miniatura()))
            botao.setIconSize(QSize(28, 34))
            botao.setToolTip(caminho)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.clicked.connect(lambda _=False, caminho=caminho: self.ao_abrir_recente(caminho))
            largura = 260 - 70
            nome = botao.fontMetrics().elidedText(os.path.basename(caminho), Qt.TextElideMode.ElideMiddle, largura)
            pasta = botao.fontMetrics().elidedText(os.path.dirname(caminho), Qt.TextElideMode.ElideLeft, largura)
            botao.setText(f"{nome}\n{pasta}")
            self.caixa_recentes.addWidget(botao)
        self.caixa_recentes.addStretch()

    @staticmethod
    def _miniatura():
        razao = 2
        imagem = QPixmap(28 * razao, 34 * razao)
        imagem.fill(Qt.GlobalColor.transparent)
        pintor = QPainter(imagem)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.scale(razao, razao)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(cor(tema.pagina))
        if tema.chanfro:
            pintor.drawPath(caminho_chanfrado(QRectF(0, 0, 28, 34), 6))
        else:
            pintor.drawRoundedRect(QRectF(0, 0, 28, 34), 4, 4)
        pintor.setPen(cor(tema.pendente if tema.chanfro else "#e5484d"))
        fonte = QFont(pintor.font())
        fonte.setPixelSize(7)
        fonte.setBold(True)
        pintor.setFont(fonte)
        pintor.drawText(QRectF(0, 20, 28, 12), Qt.AlignmentFlag.AlignCenter, "PDF")
        pintor.end()
        imagem.setDevicePixelRatio(razao)
        return imagem

    def definir_arrastando(self, arrastando):
        self.area_soltar.setProperty("arrastando", arrastando)
        repolir(self.area_soltar)
        self.area_soltar.update()


# ------------------------------------------------------------------ janela
class Janela(QMainWindow):

    def __init__(self):
        super().__init__()
        self.configuracoes = QSettings("PDF Leve", "Protótipo PySide6")
        self.documento, self.caminho = None, None
        self.rotacoes_pendentes = 0
        self.cor, self.tamanho = COR_ANOTACAO_PADRAO, TAMANHO_PADRAO
        self.termos, self.resultados, self.resultado_atual = [], [], None
        self.por_termo, self.busca_terminou = [], True
        self.geracao_busca = 0
        self.setAcceptDrops(True)
        icone_programa = RAIZ / "recursos" / "icone.ico"
        if icone_programa.exists():
            self.setWindowIcon(QIcon(str(icone_programa)))
        self.resize(1280, 820)
        self._montar()
        self._ligar_atalhos()
        self.atualizar_titulo()
        self.atualizar_estado()

    # ---------------------------------------------------- montagem
    def _montar(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        coluna = QVBoxLayout(central)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)

        self.barra = QFrame()
        self.barra.setObjectName("barra")
        self.barra.setFixedHeight(52)
        caixa = QHBoxLayout(self.barra)
        caixa.setContentsMargins(10, 0, 10, 0)
        caixa.setSpacing(4)
        self.botao_abrir = BotaoIcone("abrir", "Abrir PDF (Ctrl+O)")
        self.botao_abrir.clicked.connect(self.abrir)
        self.botao_salvar = BotaoSalvar()
        self.botao_salvar.clicked.connect(self.salvar)
        self.botao_exportar = BotaoIcone("exportar", "Salvar páginas em PDF (Ctrl+P)")
        self.botao_exportar.clicked.connect(
            lambda: self.visao.aviso.mostrar("Salvar páginas", "fora do escopo do protótipo"))
        for botao in (self.botao_abrir, self.botao_salvar, self.botao_exportar):
            caixa.addWidget(botao)
        caixa.addSpacing(6)
        caixa.addWidget(divisoria())
        caixa.addSpacing(6)

        segmento = QFrame()
        segmento.setObjectName("segmento")
        modos = QHBoxLayout(segmento)
        modos.setContentsMargins(3, 3, 3, 3)
        modos.setSpacing(2)
        ligado = tema.destaque if tema.chanfro else tema.texto
        self.botao_selecionar = BotaoIcone("selecionar", "Selecionar texto (Esc)", cor_ligado=ligado)
        self.botao_texto = BotaoIcone("texto", "Anotar com texto (T)", cor_ligado=ligado, texto="Texto")
        grupo = QButtonGroup(self)
        for botao in (self.botao_selecionar, self.botao_texto):
            botao.setCheckable(True)
            grupo.addButton(botao)
            modos.addWidget(botao)
        self.botao_selecionar.setChecked(True)
        grupo.buttonClicked.connect(lambda _: self._ao_mudar_modo())
        caixa.addWidget(segmento)

        self.botao_estilo = QToolButton()
        self.botao_estilo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.botao_estilo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_estilo.setStyleSheet(f"color: {tema.texto_suave};")
        if tema.caixa_alta:
            self.botao_estilo.setFont(fonte_numeros(base=self.botao_estilo.font()))
        self.botao_estilo.clicked.connect(self.abrir_painel_estilo)
        caixa.addWidget(self.botao_estilo)
        caixa.addStretch()

        self.campo_busca = CampoBusca()
        self.campo_busca.buscar.connect(self.iniciar_busca)
        self.campo_busca.proximo.connect(lambda: self.avancar_resultado(1))
        self.campo_busca.anterior.connect(lambda: self.avancar_resultado(-1))
        self.campo_busca.limpar.connect(self.limpar_busca)
        caixa.addWidget(self.campo_busca)
        self.botao_opcoes = BotaoIcone("opcoes", "Mais opções")
        self.botao_opcoes.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.botao_opcoes.setMenu(self._menu_opcoes())
        caixa.addWidget(self.botao_opcoes)
        coluna.addWidget(self.barra)
        linha_barra = QFrame()
        linha_barra.setObjectName("linhaBarra")
        linha_barra.setFixedHeight(1)
        coluna.addWidget(linha_barra)
        if tema.brilho:
            brilho_barra = QFrame()
            brilho_barra.setObjectName("brilhoBarra")
            brilho_barra.setFixedHeight(6)
            coluna.addWidget(brilho_barra)

        self.pilha = QStackedWidget()
        self.tela_vazia = TelaVazia(self.abrir, self.abrir_caminho)
        self.visao = VisaoPaginas()
        self.pilha.addWidget(self.tela_vazia)
        self.pilha.addWidget(self.visao)
        coluna.addWidget(self.pilha, 1)

        ilha = self.visao.ilha
        ilha.botao_anterior.clicked.connect(lambda: self.visao.ir_para_pagina(self.visao.pagina_atual() - 1))
        ilha.botao_proxima.clicked.connect(lambda: self.visao.ir_para_pagina(self.visao.pagina_atual() + 1))
        ilha.campo_pagina.returnPressed.connect(self._ao_digitar_pagina)
        ilha.botao_menos.clicked.connect(lambda: self.visao.definir_zoom(self.visao.zoom / PASSO_ZOOM))
        ilha.botao_mais.clicked.connect(lambda: self.visao.definir_zoom(self.visao.zoom * PASSO_ZOOM))
        ilha.botao_largura.clicked.connect(lambda: self.visao.aplicar_ajuste("largura"))
        ilha.botao_pagina.clicked.connect(lambda: self.visao.aplicar_ajuste("pagina"))
        ilha.botao_girar.clicked.connect(self.girar)
        menu_zoom = self._menu()
        for valor in (50, 75, 100, 125, 150, 200, 300):
            menu_zoom.addAction(f"{valor}%", lambda valor=valor: self.visao.definir_zoom(valor / 100))
        menu_zoom.addSeparator()
        menu_zoom.addAction("Ajustar à largura\tCtrl+1", lambda: self.visao.aplicar_ajuste("largura"))
        menu_zoom.addAction("Página inteira\tCtrl+2", lambda: self.visao.aplicar_ajuste("pagina"))
        ilha.botao_zoom.setMenu(menu_zoom)
        self.visao.pagina_mudou.connect(self._ao_mudar_pagina)
        self.visao.zoom_mudou.connect(self._ao_mudar_zoom)
        self.atualizar_botao_estilo()
        self.tela_vazia.mostrar_recentes(self.recentes())

    def _menu(self, pai=None):
        menu = QMenu(pai or self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        return menu

    def _menu_opcoes(self):
        menu = self._menu()
        temas = self._menu(menu)
        temas.setTitle("Tema")
        grupo = QActionGroup(temas)
        for nome, item in TEMAS.items():
            marcador = "●  " if nome == tema.nome else "     "
            acao = temas.addAction(marcador + item.titulo, lambda nome=nome: self.trocar_tema(nome))
            grupo.addAction(acao)
        menu.addMenu(temas)
        menu.addAction("Tela cheia\tF11", self.alternar_tela_cheia)
        menu.addSeparator()
        menu.addAction("Sobre o protótipo", lambda: self.visao.aviso.mostrar(
            f"PySide6 {self._versao_qt()}", "PyMuPDF " + pymupdf.VersionBind))
        return menu

    @staticmethod
    def _versao_qt():
        import PySide6
        return PySide6.__version__

    def _ligar_atalhos(self):
        def atalho(sequencia, funcao):
            QShortcut(QKeySequence(sequencia), self, activated=funcao)

        atalho("Ctrl+O", self.abrir)
        atalho("Ctrl+S", self.salvar)
        atalho("Ctrl+F", self.campo_busca.focar)
        atalho("F3", lambda: self.avancar_resultado(1))
        atalho("Shift+F3", lambda: self.avancar_resultado(-1))
        atalho("Ctrl++", lambda: self.visao.definir_zoom(self.visao.zoom * PASSO_ZOOM))
        atalho("Ctrl+=", lambda: self.visao.definir_zoom(self.visao.zoom * PASSO_ZOOM))
        atalho("Ctrl+-", lambda: self.visao.definir_zoom(self.visao.zoom / PASSO_ZOOM))
        atalho("Ctrl+0", lambda: self.visao.definir_zoom(1.0))
        atalho("Ctrl+1", lambda: self.visao.aplicar_ajuste("largura"))
        atalho("Ctrl+2", lambda: self.visao.aplicar_ajuste("pagina"))
        atalho("Ctrl+R", self.girar)
        atalho("F11", self.alternar_tela_cheia)
        atalho("T", lambda: self._definir_modo_texto(not self.botao_texto.isChecked()))

    # ---------------------------------------------------- tema
    def trocar_tema(self, nome):
        """O tema é lido na montagem da interface: a troca recria a janela, no mesmo arquivo e página."""
        if nome == tema.nome or not self.confirmar_descarte():
            return
        caminho, pagina = self.caminho, self.visao.pagina_atual()
        self.configuracoes.setValue("tema", nome)
        aplicar_tema(QApplication.instance(), nome)
        nova = Janela()
        nova.setGeometry(self.geometry())
        if self.isMaximized():
            nova.showMaximized()
        else:
            nova.show()
        JANELAS.append(nova)
        if caminho:
            nova.abrir_caminho(caminho)
            QTimer.singleShot(0, lambda: nova.visao.ir_para_pagina(pagina))
        self.rotacoes_pendentes = 0  # já confirmado acima
        self.close()
        if self in JANELAS:
            JANELAS.remove(self)

    # ---------------------------------------------------- arquivo
    def recentes(self):
        valor = self.configuracoes.value("recentes", [])
        lista = [valor] if isinstance(valor, str) else list(valor or [])
        return [caminho for caminho in lista if os.path.exists(caminho)][:MAXIMO_RECENTES]

    def _lembrar(self, caminho):
        lista = [caminho] + [item for item in self.recentes() if os.path.normcase(item) != os.path.normcase(caminho)]
        self.configuracoes.setValue("recentes", lista[:MAXIMO_RECENTES])

    def abrir(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", os.path.dirname(self.caminho or ""),
                                                 "Documentos PDF (*.pdf)")
        if caminho:
            self.abrir_caminho(caminho)

    def abrir_caminho(self, caminho):
        if not self.confirmar_descarte():
            return
        try:
            documento = pymupdf.open(caminho)
        except Exception as erro:
            self.visao.aviso.mostrar("Não foi possível abrir", str(erro)[:60])
            return
        if self.documento is not None:
            self.documento.close()
        self.documento, self.caminho, self.rotacoes_pendentes = documento, caminho, 0
        self.limpar_busca()
        self.campo_busca.limpar_tudo()
        self.pilha.setCurrentWidget(self.visao)
        self.visao.carregar(documento)
        self.visao.setFocus()
        self._lembrar(caminho)
        self.atualizar_titulo()
        self.atualizar_estado()

    def salvar(self):
        """No protótipo, sempre salva uma cópia: o arquivo original nunca é alterado."""
        if self.documento is None:
            return False
        base, _ = os.path.splitext(self.caminho)
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar uma cópia", f"{base} (cópia).pdf",
                                                 "Documentos PDF (*.pdf)")
        if not caminho:
            return False
        if os.path.normcase(os.path.abspath(caminho)) == os.path.normcase(os.path.abspath(self.caminho)):
            self.visao.aviso.mostrar("Escolha outro nome", "o protótipo não altera o original")
            return False
        self.documento.save(caminho, garbage=1, deflate=True)
        self.rotacoes_pendentes = 0
        self.atualizar_titulo()
        self.visao.aviso.mostrar("Cópia salva", os.path.basename(caminho), tipo="ok")
        return True

    def confirmar_descarte(self):
        if not self.rotacoes_pendentes:
            return True
        quantidade = self.rotacoes_pendentes
        descricao = "1 página girada" if quantidade == 1 else f"{quantidade} páginas giradas"
        resposta = DialogoSalvar(self, os.path.basename(self.caminho), descricao).executar()
        if resposta == "salvar":
            return self.salvar()
        return resposta == "descartar"

    def closeEvent(self, evento):
        if self.confirmar_descarte():
            evento.accept()
        else:
            evento.ignore()

    # ---------------------------------------------------- arrastar e soltar
    @staticmethod
    def _pdfs(evento):
        return [url.toLocalFile() for url in evento.mimeData().urls()
                if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")]

    def dragEnterEvent(self, evento):
        if self._pdfs(evento):
            evento.acceptProposedAction()
            self.tela_vazia.definir_arrastando(True)

    def dragLeaveEvent(self, evento):
        self.tela_vazia.definir_arrastando(False)

    def dropEvent(self, evento):
        self.tela_vazia.definir_arrastando(False)
        pdfs = self._pdfs(evento)
        if pdfs:
            self.abrir_caminho(pdfs[0])
            if len(pdfs) > 1:
                self.visao.aviso.mostrar(f"Aberto: {os.path.basename(pdfs[0])}",
                                         "várias janelas ficam fora do protótipo")

    # ---------------------------------------------------- estado visual
    def atualizar_titulo(self):
        nome = os.path.basename(self.caminho) if self.caminho else ""
        marcador = "● " if self.rotacoes_pendentes else ""
        sufixo = f"{NOME_APLICATIVO} (protótipo PySide6)"
        self.setWindowTitle(f"{marcador}{nome} — {sufixo}" if nome else sufixo)
        self.botao_salvar.definir_pendente(bool(self.rotacoes_pendentes))
        self.atualizar_status()

    def atualizar_estado(self):
        aberto = self.documento is not None
        for widget in (self.botao_salvar, self.botao_exportar, self.campo_busca, self.botao_texto,
                       self.botao_selecionar):
            widget.setEnabled(aberto)
        if aberto:
            self.visao.ilha.definir_total(len(self.documento))
            self.visao.posicionar_flutuantes()
        self.atualizar_status()

    def atualizar_status(self):
        """Painel “MODO // SELEÇÃO” do tema cyberpunk."""
        if not tema.painel_status or self.documento is None:
            return
        modo = "TEXTO" if self.botao_texto.isChecked() else "SELEÇÃO"
        linhas = [f"MODO // {modo}", f"ZOOM // {round(self.visao.zoom * 100)}%"]
        if self.rotacoes_pendentes:
            linhas.append(f"ALTERAÇÕES // {self.rotacoes_pendentes} PENDENTE(S)")
        if self.termos:
            linhas.append(f"BUSCA // {len(self.termos)} TERMO(S) · {len(self.resultados)} OCORR.")
        self.visao.definir_status(linhas)

    def _ao_mudar_pagina(self, pagina):
        ilha = self.visao.ilha
        if not ilha.campo_pagina.hasFocus():
            ilha.definir_pagina(pagina + 1)
        ilha.botao_anterior.setEnabled(pagina > 0)
        ilha.botao_proxima.setEnabled(self.documento is not None and pagina < len(self.documento) - 1)

    def _ao_mudar_zoom(self, zoom, modo):
        ilha = self.visao.ilha
        ilha.botao_zoom.setText(f"{round(zoom * 100)}%")
        ilha.botao_largura.setChecked(modo == "largura")
        ilha.botao_pagina.setChecked(modo == "pagina")
        self.atualizar_status()

    def _ao_digitar_pagina(self):
        texto = self.visao.ilha.campo_pagina.text()
        if texto.isdigit():
            self.visao.ir_para_pagina(int(texto) - 1)
        self.visao.setFocus()

    def girar(self):
        if self.documento is None:
            return
        indice = self.visao.pagina_atual()
        pagina = self.documento[indice]
        pagina.set_rotation((pagina.rotation + 90) % 360)
        self.rotacoes_pendentes += 1
        self.visao.invalidar_pagina(indice)
        if self.visao.modo_ajuste:
            self.visao.aplicar_ajuste()
        self.visao.ir_para_pagina(indice)
        self.atualizar_titulo()
        self.visao.aviso.mostrar(f"Página {indice + 1} girada", tipo="ok", acao="Desfazer",
                                 comando=lambda: self._desfazer_giro(indice))

    def _desfazer_giro(self, indice):
        pagina = self.documento[indice]
        pagina.set_rotation((pagina.rotation - 90) % 360)
        self.rotacoes_pendentes = max(0, self.rotacoes_pendentes - 1)
        self.visao.invalidar_pagina(indice)
        self.visao.ir_para_pagina(indice)
        self.atualizar_titulo()

    def alternar_tela_cheia(self):
        if self.isFullScreen():
            self.showNormal()
            self.barra.show()
        else:
            self.showFullScreen()
            self.barra.hide()
            self.visao.aviso.mostrar("Tela cheia", "F11 para sair")

    # ---------------------------------------------------- modos e estilo
    def _definir_modo_texto(self, ligado):
        if self.documento is None or self.campo_busca.entrada.hasFocus():
            return
        (self.botao_texto if ligado else self.botao_selecionar).setChecked(True)
        self._ao_mudar_modo()

    def _ao_mudar_modo(self):
        texto = self.botao_texto.isChecked()
        self.visao.viewport().setCursor(Qt.CursorShape.IBeamCursor if texto else Qt.CursorShape.ArrowCursor)
        self.atualizar_status()
        if texto:
            self.visao.aviso.mostrar("Modo texto", "anotações ficam fora do protótipo")

    def atualizar_botao_estilo(self):
        self.botao_estilo.setIcon(QIcon(pixmap_amostra(self.cor)))
        self.botao_estilo.setText(f"{self.tamanho}PT  ▾" if tema.caixa_alta else f"{self.tamanho} pt  ▾")
        self.botao_estilo.setToolTip(f"Cor e tamanho do texto ({self.tamanho} pt)")
        self.botao_estilo.setAccessibleName(f"Cor e tamanho do texto: {self.tamanho} pt")

    def abrir_painel_estilo(self):
        painel = PainelEstilo(self, self.cor, self.tamanho)
        painel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        painel.mudou.connect(self._ao_mudar_estilo)
        painel.abrir_abaixo_de(self.botao_estilo)

    def _ao_mudar_estilo(self, cor_escolhida, tamanho):
        self.cor, self.tamanho = cor_escolhida, tamanho
        self.atualizar_botao_estilo()

    # ---------------------------------------------------- busca
    def iniciar_busca(self, termos):
        self.geracao_busca += 1
        self.termos, self.resultados, self.resultado_atual = termos, [], None
        self.por_termo = [0] * len(termos)
        self.pagina_inicial = self.visao.pagina_atual()
        self.proxima_pagina_busca = 0
        self.busca_terminou = False
        self.visao.redesenhar_realces([], None)
        self._etapa_busca(self.geracao_busca)

    def _etapa_busca(self, geracao):
        if geracao != self.geracao_busca or self.documento is None:
            return
        inicio = time.perf_counter()
        total = len(self.documento)
        novos = False
        while self.proxima_pagina_busca < total and time.perf_counter() - inicio < TEMPO_POR_ETAPA:
            indice = self.proxima_pagina_busca
            for retangulo, termo in buscar_termos_na_pagina(self.documento[indice], self.termos):
                self.resultados.append((indice, retangulo, termo))
                self.por_termo[termo] += 1
                novos = True
            self.proxima_pagina_busca += 1
        self.busca_terminou = self.proxima_pagina_busca >= total
        if self.resultado_atual is None:
            primeiro = next((i for i, item in enumerate(self.resultados) if item[0] >= self.pagina_inicial), None)
            if primeiro is not None:
                self.ir_para_resultado(primeiro)
            elif self.busca_terminou and self.resultados:
                self.ir_para_resultado(0)
        elif novos:
            self.visao.redesenhar_realces(self.resultados, self.resultado_atual)
        self._mostrar_contagem()
        if not self.busca_terminou:
            QTimer.singleShot(0, lambda: self._etapa_busca(geracao))
        else:
            self.atualizar_status()
            if not self.resultados:
                self.visao.aviso.mostrar("Nada encontrado", "; ".join(self.termos))

    def _mostrar_contagem(self):
        atual = 0 if self.resultado_atual is None else self.resultado_atual + 1
        self.campo_busca.mostrar_contagem(atual, len(self.resultados), self.por_termo, self.busca_terminou)

    def ir_para_resultado(self, indice):
        self.resultado_atual = indice
        self.visao.redesenhar_realces(self.resultados, indice)
        pagina, retangulo, _ = self.resultados[indice]
        self.visao.mostrar_area(self.visao.area_resultado(pagina, retangulo))
        self._mostrar_contagem()

    def avancar_resultado(self, passo):
        if not self.resultados:
            if self.campo_busca.termos:
                self.iniciar_busca(self.campo_busca.termos)
            return
        atual = -1 if self.resultado_atual is None else self.resultado_atual
        self.ir_para_resultado((atual + passo) % len(self.resultados))

    def limpar_busca(self):
        self.geracao_busca += 1
        self.termos, self.resultados, self.resultado_atual = [], [], None
        self.visao.redesenhar_realces([], None)
        self.visao.setFocus()
        self.atualizar_status()


def aplicar_tema(aplicativo, nome):
    tema.definir(nome)
    familias = set(QFontDatabase.families())
    base = next((nome_fonte for nome_fonte in tema.fontes if nome_fonte in familias), "Segoe UI")
    aplicativo.setFont(QFont(base, 10))
    aplicativo.setStyleSheet(gerar_estilo())


def tema_inicial(argumentos):
    if "--tema" in argumentos:
        posicao = argumentos.index("--tema")
        if posicao + 1 < len(argumentos):
            return argumentos[posicao + 1]
    return QSettings("PDF Leve", "Protótipo PySide6").value("tema", "moderno")


def principal():
    aplicativo = QApplication(sys.argv)
    aplicativo.setStyle("Fusion")
    aplicativo.styleHints().setColorScheme(Qt.ColorScheme.Dark)  # barra de título escura no Windows 11
    aplicar_tema(aplicativo, tema_inicial(sys.argv[1:]))
    janela = Janela()
    JANELAS.append(janela)
    janela.show()
    argumentos = [arg for arg in sys.argv[1:] if arg.lower().endswith(".pdf")]
    if argumentos:
        janela.abrir_caminho(os.path.abspath(argumentos[0]))
    sys.exit(aplicativo.exec())


if __name__ == "__main__":
    principal()
