"""Impressão: escolha das páginas, encaixe no papel e envio das páginas como imagens.

A impressão roda num processo próprio (`processo_impressor`), que renderiza cada página com o
PyMuPDF e a entrega à impressora pela GDI do Windows; a interface só acompanha o progresso.

Mensagens enviadas pelo processo:
    ("progresso", impressas, total)
    ("concluido",) | ("cancelado",) | ("erro", mensagem)
Mensagem aceita pelo processo:
    "cancelar"
"""

from dataclasses import dataclass

import pymupdf

from pdf_leve.configuracao.constantes import DPI_MAXIMO_IMPRESSAO
from pdf_leve.servicos.renderizacao import aparar_deposito_mupdf

PONTOS_POR_POLEGADA = 72


@dataclass
class MedidasPapel:
    """Medidas do papel em pixels do dispositivo. A origem do desenho é o canto da área imprimível."""
    largura_fisica: int
    altura_fisica: int
    deslocamento_x: int     # margem não imprimível à esquerda
    deslocamento_y: int     # margem não imprimível no topo
    largura_imprimivel: int
    altura_imprimivel: int
    dpi_x: int
    dpi_y: int


@dataclass
class Encaixe:
    """Onde e como uma página é desenhada no papel."""
    x: int
    y: int
    largura: int
    altura: int
    escala: float  # pixels da imagem por ponto PDF
    girar: bool    # 90°, para uma página deitada caber em papel em pé (ou o contrário)


def paginas_selecionadas(intervalos, apenas_atual, total, pagina_atual):
    """Índices (a partir de 0) das páginas a imprimir, na ordem pedida. `intervalos` vem do
    diálogo, numerado a partir de 1; None significa todas as páginas."""
    if apenas_atual:
        return [pagina_atual]
    if intervalos is None:
        return list(range(total))
    paginas = []
    for inicio, fim in intervalos:
        inicio, fim = max(1, min(inicio, fim)), min(total, max(inicio, fim))
        paginas.extend(range(inicio - 1, fim))
    return paginas


def calcular_encaixe(largura_pt, altura_pt, medidas):
    """Centraliza a página no papel em tamanho real, reduzindo-a se não couber na área imprimível
    (nunca amplia). Gira 90° quando a orientação da página difere da do papel."""
    papel_deitado = medidas.largura_fisica > medidas.altura_fisica
    pagina_deitada = largura_pt > altura_pt
    girar = largura_pt != altura_pt and papel_deitado != pagina_deitada
    if girar:
        largura_pt, altura_pt = altura_pt, largura_pt
    largura = largura_pt / PONTOS_POR_POLEGADA * medidas.dpi_x
    altura = altura_pt / PONTOS_POR_POLEGADA * medidas.dpi_y
    fator = min(1.0, medidas.largura_imprimivel / largura, medidas.altura_imprimivel / altura)
    largura, altura = max(1, round(largura * fator)), max(1, round(altura * fator))
    x = (medidas.largura_fisica - largura) // 2 - medidas.deslocamento_x
    y = (medidas.altura_fisica - altura) // 2 - medidas.deslocamento_y
    x = max(0, min(x, medidas.largura_imprimivel - largura))
    y = max(0, min(y, medidas.altura_imprimivel - altura))
    escala = min(largura / largura_pt, altura / altura_pt, DPI_MAXIMO_IMPRESSAO / PONTOS_POR_POLEGADA)
    return Encaixe(x, y, largura, altura, escala, girar)


def rgb_para_dib(amostras, largura, altura):
    """Converte amostras RGB (como as de um Pixmap) no formato de bitmap do Windows:
    BGR, com cada linha completada até um múltiplo de 4 bytes."""
    dados = bytearray(amostras)
    dados[0::3], dados[2::3] = dados[2::3], dados[0::3]
    passo = largura * 3
    complemento = -passo % 4
    if not complemento:
        return bytes(dados)
    preenchimento = bytes(complemento)
    return b"".join(dados[i:i + passo] + preenchimento for i in range(0, passo * altura, passo))


def imprimir_documento(documento, paginas, dispositivo, ao_progredir, deve_cancelar):
    """Envia as páginas ao dispositivo. Devolve False se a impressão for cancelada; em caso de
    erro ou cancelamento, o trabalho é abortado na impressora."""
    try:
        medidas = MedidasPapel(*dispositivo.medidas())
        for impressas, indice in enumerate(paginas):
            if deve_cancelar():
                dispositivo.abortar()
                return False
            pagina = documento[indice]
            encaixe = calcular_encaixe(pagina.rect.width, pagina.rect.height, medidas)
            matriz = pymupdf.Matrix(encaixe.escala, encaixe.escala)
            if encaixe.girar:
                matriz.prerotate(90)
            imagem = pagina.get_pixmap(matrix=matriz, alpha=False)
            dib = rgb_para_dib(imagem.samples, imagem.width, imagem.height)
            dispositivo.iniciar_pagina()
            dispositivo.desenhar(dib, imagem.width, imagem.height,
                                 encaixe.x, encaixe.y, encaixe.largura, encaixe.altura)
            dispositivo.terminar_pagina()
            del imagem, dib
            aparar_deposito_mupdf()
            ao_progredir(impressas + 1, len(paginas))
        dispositivo.concluir()
        return True
    except BaseException:
        dispositivo.abortar()
        raise


def processo_impressor(conexao, origem, senha, impressora, devmode, paginas, nome_documento):
    """Alvo do processo de impressão. `origem` é o caminho do PDF ou o próprio PDF em bytes
    (com anotações e rotações ainda não salvas). Se a janela for fechada, a conexão se perde e
    a impressão continua sem informar o progresso."""
    from pdf_leve.sistema.impressora import DispositivoImpressao

    conectado = [True]

    def enviar(mensagem):
        if conectado[0]:
            try:
                conexao.send(mensagem)
            except (EOFError, OSError):
                conectado[0] = False

    def deve_cancelar():
        try:
            return conectado[0] and conexao.poll() and conexao.recv() == "cancelar"
        except (EOFError, OSError):
            conectado[0] = False
            return False

    try:
        documento = pymupdf.open(stream=origem) if isinstance(origem, bytes) else pymupdf.open(origem)
        try:
            if documento.needs_pass:
                documento.authenticate(senha or "")
            dispositivo = DispositivoImpressao(impressora, devmode, nome_documento)
            try:
                concluido = imprimir_documento(documento, paginas, dispositivo,
                                               lambda impressas, total: enviar(("progresso", impressas, total)),
                                               deve_cancelar)
            finally:
                dispositivo.fechar()
        finally:
            documento.close()
        enviar(("concluido",) if concluido else ("cancelado",))
    except Exception as erro:
        enviar(("erro", str(erro)))
