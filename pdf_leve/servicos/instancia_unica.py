"""Instância única: ao abrir o programa de novo (ex.: duplo clique num PDF), os arquivos são
entregues à cópia que já está rodando, que os abre em novas janelas.

A comunicação usa um soquete TCP em 127.0.0.1 (só aceita conexões do próprio computador).
"""

import json
import socket

from pdf_leve.configuracao.constantes import IDENTIFICADOR_MENSAGEM, PORTA_INSTANCIA_UNICA

INTERVALO_VERIFICACAO_MS = 250
TAMANHO_MAXIMO_MENSAGEM = 1_000_000


def enviar_para_instancia_aberta(caminhos):
    """Se o programa já está aberto, entrega os arquivos a ele e retorna True."""
    try:
        with socket.create_connection(("127.0.0.1", PORTA_INSTANCIA_UNICA), timeout=0.5) as conexao:
            mensagem = {"app": IDENTIFICADOR_MENSAGEM, "caminhos": caminhos}
            conexao.sendall(json.dumps(mensagem).encode("utf-8") + b"\n")
            conexao.settimeout(2)
            return conexao.recv(2) == b"ok"
    except OSError:
        return False


def ouvir_novas_instancias(aplicativo):
    """Passa a aceitar arquivos de novas execuções. `aplicativo` precisa de `after(ms, funcao)`,
    `abrir_arquivos(caminhos)` e da lista `janelas` (a escuta para quando não há janelas).
    Retorna o soquete (para ser fechado ao sair) ou None se a porta estiver ocupada."""
    try:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.bind(("127.0.0.1", PORTA_INSTANCIA_UNICA))
        servidor.listen(4)
        servidor.setblocking(False)
    except OSError:
        return None

    def verificar():
        try:
            while True:
                conexao, _ = servidor.accept()
                with conexao:
                    caminhos = _ler_pedido(conexao)
                    if caminhos is not None:
                        conexao.sendall(b"ok")
                        aplicativo.abrir_arquivos(caminhos)
        except (BlockingIOError, OSError, ValueError):
            pass
        if aplicativo.janelas:
            aplicativo.after(INTERVALO_VERIFICACAO_MS, verificar)

    aplicativo.after(INTERVALO_VERIFICACAO_MS, verificar)
    return servidor


def _ler_pedido(conexao):
    conexao.setblocking(True)
    conexao.settimeout(1)
    dados = b""
    while not dados.endswith(b"\n") and len(dados) < TAMANHO_MAXIMO_MENSAGEM:
        parte = conexao.recv(65536)
        if not parte:
            break
        dados += parte
    mensagem = json.loads(dados.decode("utf-8"))
    if mensagem.get("app") != IDENTIFICADOR_MENSAGEM:
        return None
    caminhos = mensagem.get("caminhos", mensagem.get("paths", []))  # "paths": versões anteriores
    return [caminho for caminho in caminhos if isinstance(caminho, str)]
