"""Renderização de páginas em processos auxiliares.

Páginas escaneadas (JPEG 2000, JBIG2…) podem levar ~600 ms para decodificar, e o PyMuPDF
não libera o GIL enquanto renderiza: por isso a renderização roda em processos separados,
e a interface nunca trava. Os processos são compartilhados por todas as janelas.

Mensagens enviadas aos processos:
    ("abrir", id_documento, caminho, senha)   abre (ou relê) um documento
    ("descartar", id_documento)               fecha, sem resposta
    ("fechar", id_documento)                  fecha e responde ("fechado", id_documento)
    ("girar", id_documento, pagina, rotacao)  espelha uma rotação ainda não salva
    ("renderizar", chave, pagina, escala)     responde ("imagem", chave, largura, altura, amostras)
                                              ou ("erro", chave, mensagem)
    None                                      encerra o processo
A chave é (id_documento, página, escala × 1000, versão da página).
"""

import multiprocessing
import time

import pymupdf

from pdf_leve.configuracao.constantes import RENDERIZACOES_ENTRE_LIMPEZAS

_contador_renderizacoes = [0]


def aparar_deposito_mupdf():
    """O MuPDF guarda imagens já decodificadas (~26 MB por página escaneada) sem limite prático
    e o PyMuPDF não informa o tamanho desse depósito: ele é esvaziado a cada poucas páginas."""
    _contador_renderizacoes[0] += 1
    if _contador_renderizacoes[0] % RENDERIZACOES_ENTRE_LIMPEZAS == 0:
        pymupdf.TOOLS.store_shrink(100)


def renderizar_pagina(pagina, escala):
    return pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)


def processo_renderizador(conexao):
    """Laço do processo auxiliar. Mantém cópias próprias dos documentos de todas as janelas."""
    documentos = {}
    while True:
        try:
            mensagem = conexao.recv()
        except (EOFError, OSError):
            break
        if mensagem is None:
            break
        tipo = mensagem[0]
        try:
            if tipo == "abrir":
                _, id_documento, caminho, senha = mensagem
                if id_documento in documentos:
                    documentos.pop(id_documento).close()
                documento = pymupdf.open(caminho)
                if documento.needs_pass:
                    documento.authenticate(senha or "")
                documentos[id_documento] = documento
            elif tipo in ("descartar", "fechar"):
                if mensagem[1] in documentos:
                    documentos.pop(mensagem[1]).close()
                if tipo == "fechar":
                    conexao.send(("fechado", mensagem[1]))
            elif tipo == "girar":
                _, id_documento, pagina, rotacao = mensagem
                documentos[id_documento][pagina].set_rotation(rotacao)
            elif tipo == "renderizar":
                _, chave, pagina, escala = mensagem
                imagem = renderizar_pagina(documentos[chave[0]][pagina], escala)
                conexao.send(("imagem", chave, imagem.width, imagem.height, imagem.samples))
                aparar_deposito_mupdf()
        except Exception as erro:
            if tipo == "renderizar":
                conexao.send(("erro", mensagem[1], str(erro)))
            elif tipo == "fechar":
                conexao.send(("fechado", mensagem[1]))


class ConjuntoRenderizadores:
    """Processos auxiliares de renderização, compartilhados por todas as janelas.

    `aplicativo` deve oferecer: `after(ms, funcao)`, `janelas`, `janelas_por_prioridade()` e
    `janela_do_documento(id)`. Cada janela oferece `proximo_pedido()`, `receber_imagem(...)`,
    `renderizar_visiveis()`, `agendar_renderizacao()` e o conjunto `em_renderizacao`.
    Se os processos não puderem ser criados, `disponivel` é False e as janelas renderizam
    no próprio processo.
    """

    def __init__(self, aplicativo, quantidade):
        self.aplicativo = aplicativo
        self.processos = []  # [conexão, processo, chave em renderização ou None]
        self._tarefa_receber = None
        try:
            contexto = multiprocessing.get_context("spawn")
            for _ in range(quantidade):
                local, remota = contexto.Pipe()
                processo = contexto.Process(target=processo_renderizador, args=(remota,), daemon=True)
                processo.start()
                self.processos.append([local, processo, None])
        except Exception:
            self.encerrar()

    @property
    def disponivel(self):
        return bool(self.processos)

    def enviar_a_todos(self, mensagem):
        for processo in list(self.processos):
            try:
                processo[0].send(mensagem)
            except Exception:
                self._processo_perdido(processo)

    def _processo_perdido(self, processo):
        """Um processo auxiliar terminou: as janelas passam a renderizar localmente o que faltar."""
        if processo in self.processos:
            self.processos.remove(processo)
        for janela in self.aplicativo.janelas:
            janela.em_renderizacao.clear()
            janela.agendar_renderizacao()

    def distribuir(self):
        """Entrega as páginas pedidas pelas janelas aos processos livres (a janela em foco primeiro)."""
        janelas = self.aplicativo.janelas_por_prioridade()
        for processo in self.processos:
            if processo[2] is not None:
                continue
            for janela in janelas:
                pedido = janela.proximo_pedido()
                if pedido:
                    chave, pagina = pedido
                    try:
                        processo[0].send(("renderizar", chave, pagina, chave[2] / 1000))
                    except Exception:
                        self._processo_perdido(processo)
                        return
                    processo[2] = chave
                    janela.em_renderizacao.add(chave)
                    break
        if any(processo[2] for processo in self.processos) and not self._tarefa_receber:
            self._tarefa_receber = self.aplicativo.after(10, self.receber)

    def _tratar_mensagem(self, processo, mensagem, atualizadas):
        if mensagem[0] not in ("imagem", "erro"):
            return
        chave = mensagem[1]
        processo[2] = None
        janela = self.aplicativo.janela_do_documento(chave[0])
        if not janela:
            return
        janela.em_renderizacao.discard(chave)
        if mensagem[0] == "imagem" and janela.receber_imagem(chave, *mensagem[2:]):
            atualizadas.add(janela)

    def receber(self):
        """Recebe as páginas prontas e as entrega às janelas correspondentes."""
        self._tarefa_receber = None
        atualizadas = set()
        for processo in list(self.processos):
            try:
                while processo[0].poll():
                    self._tratar_mensagem(processo, processo[0].recv(), atualizadas)
            except (EOFError, OSError):
                self._processo_perdido(processo)
        for janela in atualizadas:
            janela.renderizar_visiveis()
        self.distribuir()

    def fechar_documento(self, id_documento, tempo_limite=5.0):
        """Fecha um documento em todos os processos e espera a confirmação
        (necessário antes de substituir o arquivo: o Windows não substitui arquivos abertos)."""
        self.enviar_a_todos(("fechar", id_documento))
        atualizadas = set()
        for processo in list(self.processos):
            limite = time.time() + tempo_limite
            try:
                while time.time() < limite and processo[0].poll(max(0.0, limite - time.time())):
                    mensagem = processo[0].recv()
                    if mensagem == ("fechado", id_documento):
                        break
                    self._tratar_mensagem(processo, mensagem, atualizadas)
            except (EOFError, OSError):
                self._processo_perdido(processo)

    def encerrar(self):
        for processo in self.processos:
            try:
                processo[0].send(None)
            except Exception:
                pass
        for processo in self.processos:
            processo[1].join(0.5)
            if processo[1].is_alive():
                processo[1].terminate()
        self.processos = []
