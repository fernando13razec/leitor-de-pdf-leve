"""Recursos do Windows via ctypes (sem dependências externas). Em outros sistemas, nada é feito."""

import ctypes
import sys

from pdf_leve.configuracao.constantes import ID_APLICATIVO_WINDOWS
from pdf_leve.configuracao.tema import COR_BARRA

NO_WINDOWS = sys.platform == "win32"

_ATRIBUTO_MODO_ESCURO = 20        # DWMWA_USE_IMMERSIVE_DARK_MODE
_ATRIBUTO_COR_TITULO = 35         # DWMWA_CAPTION_COLOR (Windows 11)
_MENSAGEM_ARQUIVOS_SOLTOS = 0x0233  # WM_DROPFILES
_PROCEDIMENTO_JANELA = -4         # GWLP_WNDPROC
_INTERVALO_ARQUIVOS_SOLTOS_MS = 150


def preparar_processo():
    """Nitidez em telas de alta resolução e ícone próprio na barra de tarefas."""
    if not NO_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APLICATIVO_WINDOWS)
    except Exception:
        pass


def identificador_janela(janela):
    """HWND da moldura da janela Tk (o pai do identificador interno)."""
    user32 = ctypes.windll.user32
    user32.GetParent.argtypes = [ctypes.c_void_p]
    user32.GetParent.restype = ctypes.c_void_p
    return user32.GetParent(janela.winfo_id())


def barra_titulo_escura(janela):
    """Barra de título escura (Windows 10/11), com a cor da barra de ferramentas no Windows 11."""
    if not NO_WINDOWS:
        return
    try:
        janela.update_idletasks()
        hwnd = ctypes.c_void_p(identificador_janela(janela))
        dwm = ctypes.windll.dwmapi
        ligado = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, _ATRIBUTO_MODO_ESCURO, ctypes.byref(ligado), 4)
        r, g, b = (int(COR_BARRA[i:i + 2], 16) for i in (1, 3, 5))
        cor = ctypes.c_int(r | g << 8 | b << 16)  # COLORREF: 0x00BBGGRR
        dwm.DwmSetWindowAttribute(hwnd, _ATRIBUTO_COR_TITULO, ctypes.byref(cor), 4)
    except Exception:
        pass


def aceitar_arquivos_arrastados(janela, ao_receber):
    """Aceita arquivos arrastados do Explorer (WM_DROPFILES).

    A mensagem chega dentro do procedimento de janela do Windows, onde o tkinter não pode ser
    chamado; por isso os arquivos vão para uma fila, lida periodicamente pelo laço do Tk.
    """
    if not NO_WINDOWS:
        return
    try:
        from ctypes import wintypes

        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, ctypes.c_uint,
                                           wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        shell32.DragQueryFileW.restype = ctypes.c_uint
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        procedimento_original, fila = [None], []

        def procedimento(hwnd, mensagem, wparam, lparam):
            if mensagem == _MENSAGEM_ARQUIVOS_SOLTOS:
                arquivos = []
                for i in range(shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)):
                    tamanho = shell32.DragQueryFileW(wparam, i, None, 0)
                    memoria = ctypes.create_unicode_buffer(tamanho + 1)
                    shell32.DragQueryFileW(wparam, i, memoria, tamanho + 1)
                    arquivos.append(memoria.value)
                shell32.DragFinish(wparam)
                fila.append(arquivos)
                return 0
            if procedimento_original[0]:
                return user32.CallWindowProcW(procedimento_original[0], hwnd, mensagem, wparam, lparam)
            return user32.DefWindowProcW(hwnd, mensagem, wparam, lparam)

        janela.update_idletasks()
        hwnd = identificador_janela(janela)
        janela._procedimento_arrastar = WNDPROC(procedimento)  # precisa continuar referenciado
        procedimento_original[0] = user32.SetWindowLongPtrW(
            hwnd, _PROCEDIMENTO_JANELA, ctypes.cast(janela._procedimento_arrastar, ctypes.c_void_p))
        shell32.DragAcceptFiles(hwnd, True)

        def verificar_fila():
            while fila:
                ao_receber(fila.pop(0))
            janela.after(_INTERVALO_ARQUIVOS_SOLTOS_MS, verificar_fila)

        verificar_fila()
    except Exception:
        pass
