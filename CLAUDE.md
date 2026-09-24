# CLAUDE.md

Orientações para agentes de IA (e pessoas) que trabalham neste repositório.

## Projeto

PDF Leve: leitor de PDF para Windows em Python (tkinter + PyMuPDF), com tema escuro, anotações
de texto, seleção de texto, busca, várias janelas e renderização em processos auxiliares.
A arquitetura está descrita em `docs/arquitetura.md`; leia antes de mudanças estruturais.

## Convenções

- **Tudo em português do Brasil**: nomes de variáveis, funções, classes, módulos, comentários,
  docstrings e textos da interface, com acentuação correta nos textos. Exceções: nomes impostos
  por bibliotecas (métodos do tkinter como `after`, `bind`; atributos do PyMuPDF), nomes de
  eventos do Tk e os métodos `test_*` exigidos pelo unittest.
- **Constantes ajustáveis** ficam em `pdf_leve/configuracao/constantes.py`; cores, fontes e ícones
  em `pdf_leve/configuracao/tema.py`. Não espalhe números mágicos nem cores pelo código.
- **Serviços** (`pdf_leve/servicos/`) não importam nada de `interface`; mantenha-os testáveis sem Tk.
- A janela é dividida em mixins (`pdf_leve/interface/janela/`); coloque cada método no mixin do seu
  assunto.
- **Glifos** das fontes de ícones do Windows ficam como escapes `\uXXXX` em `tema.py`. Algumas
  ferramentas de edição convertem escapes em caracteres invisíveis; confira depois de editar.
- **Atalhos de teclas numéricas** no Tk usam `<Control-Key-1>` (não `<Control-1>`, que é o mouse).
- Nunca chame o tkinter fora da thread principal nem de dentro de callbacks do Windows (ctypes);
  use filas lidas pelo laço do Tk.
- Não bloqueie o laço do Tk: operações longas devem ser feitas em etapas (`after`) ou nos
  processos auxiliares.

## Comandos

```bash
pip install -r requirements.txt
python -m unittest discover -s testes -t . -v   # testes (devem passar antes de cada commit)
pythonw iniciar.pyw arquivo.pdf                 # executar
python ferramentas/gerar_icone.py               # regenerar ícones (requer Pillow)
python ferramentas/gerar_executavel.py          # executável (PyInstaller, modo pasta) + zip em dist/
```

## Versões e Releases

A versão fica em `pdf_leve/configuracao/constantes.py` (`VERSAO`). Para lançar: atualize `VERSAO`,
rode os testes, gere o executável num ambiente virtual limpo (`.venv` com `requirements-dev.txt`),
teste o `dist/PDF Leve/PDF Leve.exe` e publique o zip com `gh release create v<versão>`.

## Cuidados

- `iniciar.pyw` precisa do `if __name__ == "__main__"`: os processos de renderização (spawn)
  reimportam o arquivo principal.
- Não versione PDFs reais de usuários (podem conter dados sensíveis); use PDFs gerados nos testes.
