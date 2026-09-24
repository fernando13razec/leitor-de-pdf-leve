"""Abre o PDF Leve (duplo clique neste arquivo, ou `pythonw iniciar.pyw arquivo.pdf`).

A extensão .pyw faz o Windows usar o pythonw.exe, que não abre a janela preta do console.
"""

from pdf_leve.principal import principal

if __name__ == "__main__":  # obrigatório: os processos de renderização reimportam este arquivo
    principal()
