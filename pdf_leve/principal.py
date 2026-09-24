"""Ponto de entrada do PDF Leve."""

import multiprocessing
import os
import sys

from pdf_leve.servicos.instancia_unica import enviar_para_instancia_aberta
from pdf_leve.sistema.windows import preparar_processo


def principal():
    multiprocessing.freeze_support()  # necessário quando empacotado como .exe (PyInstaller)
    preparar_processo()
    caminhos = [os.path.abspath(caminho) for caminho in sys.argv[1:]]
    if enviar_para_instancia_aberta(caminhos):
        return  # o programa já aberto abre os arquivos em novas janelas

    from pdf_leve.interface.aplicativo import Aplicativo  # só carrega a interface se for preciso

    aplicativo = Aplicativo()
    aplicativo.abrir_arquivos(caminhos)  # sem caminhos, abre uma janela vazia
    aplicativo.mainloop()
