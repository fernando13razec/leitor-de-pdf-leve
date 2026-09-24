"""Janela de um PDF, dividida em partes (mixins) por responsabilidade.

    janela_pdf.py         JanelaPdf: junta as partes e guarda o estado
    barra_ferramentas.py  montagem da interface, atalhos, avisos, tela cheia
    arquivo.py            abrir, salvar, exportar páginas, girar, fechar
    visualizacao.py       disposição das páginas, renderização, cache, zoom, navegação
    mouse.py              eventos do mouse, menu de contexto, Esc, modo texto
    selecao_texto.py      seleção e cópia do texto das páginas
    anotacoes.py          criar, editar, mover e excluir anotações; cor e tamanho
    busca.py              busca de texto em segundo plano
"""

from pdf_leve.interface.janela.janela_pdf import JanelaPdf

__all__ = ["JanelaPdf"]
