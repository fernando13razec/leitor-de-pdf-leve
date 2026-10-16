"""Impressão no Windows via ctypes (sem dependências externas): diálogo de impressão padrão
(PrintDlgEx) e envio de imagens de página à impressora pela GDI."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from pdf_leve.configuracao.constantes import MAXIMO_INTERVALOS_IMPRESSAO
from pdf_leve.sistema.windows import NO_WINDOWS, identificador_janela

# PrintDlgEx (commdlg.h)
_PD_PAGENUMS = 0x2
_PD_NOSELECTION = 0x4
_PD_USEDEVMODECOPIESANDCOLLATE = 0x40000
_PD_CURRENTPAGE = 0x400000
_START_PAGE_GENERAL = 0xFFFFFFFF
_PD_RESULT_PRINT = 1
_COINIT_APARTMENTTHREADED = 0x2

# GDI (wingdi.h)
_HORZRES, _VERTRES = 8, 10
_LOGPIXELSX, _LOGPIXELSY = 88, 90
_PHYSICALWIDTH, _PHYSICALHEIGHT = 110, 111
_PHYSICALOFFSETX, _PHYSICALOFFSETY = 112, 113
_HALFTONE = 4
_DIB_RGB_COLORS = 0
_SRCCOPY = 0x00CC0020
_GDI_ERROR = -1

# No Windows de 32 bits, as estruturas do commdlg.h são compactadas em 1 byte.
_COMPACTACAO = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8


class _IntervaloPaginas(ctypes.Structure):  # PRINTPAGERANGE
    _pack_ = _COMPACTACAO
    _fields_ = [("nFromPage", wintypes.DWORD), ("nToPage", wintypes.DWORD)]


class _DialogoImpressao(ctypes.Structure):  # PRINTDLGEXW
    _pack_ = _COMPACTACAO
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hDevMode", wintypes.HGLOBAL),
        ("hDevNames", wintypes.HGLOBAL),
        ("hDC", wintypes.HDC),
        ("Flags", wintypes.DWORD),
        ("Flags2", wintypes.DWORD),
        ("ExclusionFlags", wintypes.DWORD),
        ("nPageRanges", wintypes.DWORD),
        ("nMaxPageRanges", wintypes.DWORD),
        ("lpPageRanges", ctypes.POINTER(_IntervaloPaginas)),
        ("nMinPage", wintypes.DWORD),
        ("nMaxPage", wintypes.DWORD),
        ("nCopies", wintypes.DWORD),
        ("hInstance", wintypes.HINSTANCE),
        ("lpPrintTemplateName", wintypes.LPCWSTR),
        ("lpCallback", ctypes.c_void_p),
        ("nPropertyPages", wintypes.DWORD),
        ("lphPropertyPages", ctypes.c_void_p),
        ("nStartPage", wintypes.DWORD),
        ("dwResultAction", wintypes.DWORD),
    ]


class _InformacoesDocumento(ctypes.Structure):  # DOCINFOW
    _fields_ = [
        ("cbSize", ctypes.c_int),
        ("lpszDocName", wintypes.LPCWSTR),
        ("lpszOutput", wintypes.LPCWSTR),
        ("lpszDatatype", wintypes.LPCWSTR),
        ("fwType", wintypes.DWORD),
    ]


class _CabecalhoBitmap(ctypes.Structure):  # BITMAPINFOHEADER
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


@dataclass
class EscolhaImpressao:
    """Resultado do diálogo de impressão."""
    impressora: str
    devmode: bytes            # configurações do driver: cópias, agrupamento, papel, orientação…
    intervalos: list | None   # [(início, fim)] numerados a partir de 1; None = todas as páginas
    apenas_atual: bool


def _ler_memoria_global(kernel32, identificador):
    """Copia o conteúdo de um bloco HGLOBAL."""
    ponteiro = kernel32.GlobalLock(identificador)
    if not ponteiro:
        return b""
    try:
        return ctypes.string_at(ponteiro, kernel32.GlobalSize(identificador))
    finally:
        kernel32.GlobalUnlock(identificador)


def escolher_impressora(janela, total_paginas, pagina_atual):
    """Abre o diálogo de impressão padrão do Windows. Devolve uma EscolhaImpressao, ou None se
    o usuário cancelar. Levanta OSError se o diálogo não puder ser aberto (ex.: sem impressoras)."""
    if not NO_WINDOWS:
        return None
    comdlg32, kernel32, ole32 = ctypes.windll.comdlg32, ctypes.windll.kernel32, ctypes.windll.ole32
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    comdlg32.PrintDlgExW.argtypes = [ctypes.POINTER(_DialogoImpressao)]
    comdlg32.PrintDlgExW.restype = ctypes.HRESULT  # levanta OSError se falhar

    intervalos = (_IntervaloPaginas * MAXIMO_INTERVALOS_IMPRESSAO)()
    intervalos[0].nFromPage = intervalos[0].nToPage = pagina_atual + 1
    dialogo = _DialogoImpressao()
    dialogo.lStructSize = ctypes.sizeof(_DialogoImpressao)
    janela.update_idletasks()
    dialogo.hwndOwner = identificador_janela(janela)
    dialogo.Flags = _PD_USEDEVMODECOPIESANDCOLLATE | _PD_NOSELECTION
    dialogo.nMaxPageRanges = MAXIMO_INTERVALOS_IMPRESSAO
    dialogo.lpPageRanges = intervalos
    dialogo.nMinPage, dialogo.nMaxPage = 1, total_paginas
    dialogo.nCopies = 1
    dialogo.nStartPage = _START_PAGE_GENERAL

    com_iniciado = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED) in (0, 1)  # S_OK, S_FALSE
    try:
        comdlg32.PrintDlgExW(ctypes.byref(dialogo))
    finally:
        if com_iniciado:
            ole32.CoUninitialize()
    try:
        if dialogo.dwResultAction != _PD_RESULT_PRINT or not dialogo.hDevNames:
            return None
        nomes = _ler_memoria_global(kernel32, dialogo.hDevNames)  # DEVNAMES: deslocamentos em caracteres
        deslocamento = int.from_bytes(nomes[2:4], "little") * 2
        impressora = nomes[deslocamento:].decode("utf-16-le").split("\0", 1)[0]
        devmode = _ler_memoria_global(kernel32, dialogo.hDevMode) if dialogo.hDevMode else b""
        selecionados = None
        if dialogo.Flags & _PD_PAGENUMS:
            selecionados = [(intervalos[i].nFromPage, intervalos[i].nToPage) for i in range(dialogo.nPageRanges)]
        return EscolhaImpressao(impressora, devmode, selecionados, bool(dialogo.Flags & _PD_CURRENTPAGE))
    finally:
        for identificador in (dialogo.hDevMode, dialogo.hDevNames):
            if identificador:
                kernel32.GlobalFree(identificador)


class DispositivoImpressao:
    """Um trabalho de impressão na GDI: cada página é uma imagem desenhada com StretchDIBits.
    `arquivo_saida` desvia a impressão para um arquivo (usado nos testes com impressoras de PDF)."""

    def __init__(self, impressora, devmode, nome_documento, arquivo_saida=None):
        self.gdi32 = gdi32 = ctypes.windll.gdi32
        gdi32.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
        gdi32.CreateDCW.restype = wintypes.HDC
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
        gdi32.StartDocW.argtypes = [wintypes.HDC, ctypes.POINTER(_InformacoesDocumento)]
        for funcao in (gdi32.StartPage, gdi32.EndPage, gdi32.EndDoc, gdi32.AbortDoc):
            funcao.argtypes = [wintypes.HDC]
        gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
        gdi32.SetBrushOrgEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        gdi32.StretchDIBits.argtypes = [wintypes.HDC] + [ctypes.c_int] * 8 + [
            ctypes.c_void_p, ctypes.POINTER(_CabecalhoBitmap), wintypes.UINT, wintypes.DWORD]

        self._devmode = ctypes.create_string_buffer(devmode, len(devmode)) if devmode else None
        self.hdc = gdi32.CreateDCW(None, impressora, None, self._devmode)
        if not self.hdc:
            raise OSError(f"Não foi possível acessar a impressora “{impressora}”.")
        self.em_andamento = False
        informacoes = _InformacoesDocumento(ctypes.sizeof(_InformacoesDocumento), nome_documento, arquivo_saida, None, 0)
        if gdi32.StartDocW(self.hdc, ctypes.byref(informacoes)) <= 0:
            self.fechar()
            raise OSError(f"A impressora “{impressora}” recusou o trabalho de impressão.")
        self.em_andamento = True

    def medidas(self):
        """(largura física, altura física, margem esquerda, margem do topo, largura imprimível,
        altura imprimível, DPI horizontal, DPI vertical), em pixels do dispositivo. A origem do
        desenho é o canto da área imprimível."""
        return tuple(self.gdi32.GetDeviceCaps(self.hdc, indice) for indice in (
            _PHYSICALWIDTH, _PHYSICALHEIGHT, _PHYSICALOFFSETX, _PHYSICALOFFSETY,
            _HORZRES, _VERTRES, _LOGPIXELSX, _LOGPIXELSY))

    def iniciar_pagina(self):
        if self.gdi32.StartPage(self.hdc) <= 0:
            raise OSError("A impressora recusou uma nova página.")

    def desenhar(self, dib, largura, altura, x, y, largura_destino, altura_destino):
        """Desenha uma imagem BGR de 24 bits (linhas alinhadas em 4 bytes, de cima para baixo)."""
        cabecalho = _CabecalhoBitmap(ctypes.sizeof(_CabecalhoBitmap), largura, -altura, 1, 24, 0, len(dib))
        self.gdi32.SetStretchBltMode(self.hdc, _HALFTONE)
        self.gdi32.SetBrushOrgEx(self.hdc, 0, 0, None)
        linhas = self.gdi32.StretchDIBits(self.hdc, x, y, largura_destino, altura_destino, 0, 0, largura, altura,
                                          dib, ctypes.byref(cabecalho), _DIB_RGB_COLORS, _SRCCOPY)
        if linhas in (0, _GDI_ERROR):
            raise OSError("A impressora não aceitou a imagem da página.")

    def terminar_pagina(self):
        if self.gdi32.EndPage(self.hdc) <= 0:
            raise OSError("A impressora não aceitou a página.")

    def concluir(self):
        if self.em_andamento:
            self.em_andamento = False
            if self.gdi32.EndDoc(self.hdc) <= 0:
                raise OSError("A impressora não concluiu o trabalho de impressão.")

    def abortar(self):
        if self.em_andamento:
            self.em_andamento = False
            self.gdi32.AbortDoc(self.hdc)

    def fechar(self):
        self.abortar()
        if self.hdc:
            self.gdi32.DeleteDC(self.hdc)
            self.hdc = None
