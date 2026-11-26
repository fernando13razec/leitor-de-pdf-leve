"""Pequenas funções auxiliares da interface."""

import base64
import queue
import struct
import threading
import tkinter as tk
import zlib

# O Tk 9 (o do Python 3.14.10 em diante no Windows, usado no executável da Release) entrega a
# rolagem de alta resolução como <TouchpadScroll>, e não como <MouseWheel>. Ela vem dos touchpads e
# dos mouses de rolagem suave, cujos deltas não são múltiplos de 120. Depois de um desses deltas,
# até o clique seguinte da roda chega como <TouchpadScroll>. O Tk 8.6 não tem esse evento e entrega
# tudo como <MouseWheel>.
ROLAGEM_PRECISA_DISPONIVEL = tk.TkVersion >= 9.0


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


def executar_em_segundo_plano(widget, tarefa, ao_concluir, intervalo_ms):
    """Roda `tarefa()` numa thread e chama `ao_concluir(resultado, erro)` no laço do Tk.

    A thread não toca no tkinter: o resultado volta por uma fila, lida com `after` a cada
    `intervalo_ms`. Se `widget` for destruído antes, o resultado é descartado."""
    fila = queue.Queue(maxsize=1)

    def executar():
        try:
            fila.put((tarefa(), None))
        except Exception as erro:
            fila.put((None, erro))

    def verificar():
        try:
            resultado, erro = fila.get_nowait()
        except queue.Empty:
            widget.after(intervalo_ms, verificar)
            return
        try:
            existe = widget.winfo_exists()
        except tk.TclError:
            existe = False
        if existe:
            ao_concluir(resultado, erro)

    threading.Thread(target=executar, daemon=True).start()
    widget.after(intervalo_ms, verificar)


def ligar_roda(widget, funcao, modificador=""):
    """Liga `funcao(evento, delta_x, delta_y)` à roda do mouse e à rolagem de alta resolução.

    Use sempre esta função em vez de ligar só o <MouseWheel>: no Tk 9, touchpads e mouses de rolagem
    suave não geram <MouseWheel>. `modificador` é "", "Shift" ou "Control". Os deltas seguem a
    convenção do Tk (positivo rola para cima ou para a esquerda; um clique da roda vale 120). Na roda
    comum, o delta vem sempre em `delta_y`, mesmo com Shift, que o Tk usa para a rolagem horizontal."""
    prefixo = f"{modificador}-" if modificador else ""
    widget.bind(f"<{prefixo}MouseWheel>", lambda evento: funcao(evento, 0, evento.delta))
    if ROLAGEM_PRECISA_DISPONIVEL:
        widget.bind(f"<{prefixo}TouchpadScroll>",
                    lambda evento: funcao(evento, *separar_deltas_precisos(evento.delta)))


def separar_deltas_precisos(valor):
    """Separa o %D de um <TouchpadScroll> em (delta_x, delta_y), como o `tk::PreciseScrollDeltas`.

    O Tk junta os dois deltas num inteiro, com o X nos 16 bits altos e o Y nos 16 bits baixos, cada
    um com sinal."""
    valor &= 0xFFFFFFFF  # aceita o inteiro com ou sem sinal

    def com_sinal(parte):
        return parte - 0x10000 if parte >= 0x8000 else parte

    return com_sinal(valor >> 16), com_sinal(valor & 0xFFFF)


def passos_da_roda(delta, delta_por_passo):
    """Passos para o `xview/yview scroll` a partir de um delta da roda (positivo rola para baixo).

    Touchpads e mouses de rolagem suave mandam deltas menores que um passo, então cada evento rola
    ao menos um passo, para a rolagem não ficar parada."""
    if not delta:
        return 0
    return -round(delta / delta_por_passo) or (-1 if delta > 0 else 1)


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
