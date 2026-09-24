"""Pequenas funções auxiliares da interface."""

import base64
import struct
import tkinter as tk
import zlib


def plural(quantidade, singular, plural_):
    return f"{quantidade} {singular if quantidade == 1 else plural_}"


def centralizar(janela, sobre):
    """Posiciona a janela centralizada horizontalmente sobre outra (um pouco acima do meio)."""
    janela.update_idletasks()
    x = sobre.winfo_rootx() + (sobre.winfo_width() - janela.winfo_width()) // 2
    y = sobre.winfo_rooty() + (sobre.winfo_height() - janela.winfo_height()) // 3
    janela.geometry(f"+{max(0, x)}+{max(0, y)}")


def trazer_para_frente(janela):
    janela.deiconify()
    janela.lift()
    janela.attributes("-topmost", True)
    janela.after(200, lambda: janela.attributes("-topmost", False))
    janela.focus_force()


def imagem_cor_solida(largura, altura, rgba):
    """PhotoImage de cor sólida com transparência (PNG gerado na hora; o Tk mistura o alfa)."""
    def bloco(tipo, dados):
        verificacao = zlib.crc32(tipo + dados) & 0xFFFFFFFF
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", verificacao)

    pixels = (b"\x00" + bytes(rgba) * largura) * altura
    png = (b"\x89PNG\r\n\x1a\n"
           + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0))
           + bloco(b"IDAT", zlib.compress(pixels, 1))
           + bloco(b"IEND", b""))
    return tk.PhotoImage(data=base64.b64encode(png).decode())


def imagem_ppm(largura, altura, amostras):
    """PhotoImage a partir de pixels RGB crus (formato PPM, lido rapidamente pelo Tk)."""
    return tk.PhotoImage(data=b"P6\n%d %d\n255\n" % (largura, altura) + amostras)
