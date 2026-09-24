# Arquitetura do PDF Leve

## Visão geral

```
iniciar.pyw                    lançador (duplo clique); chama pdf_leve.principal.principal()
pdf_leve/
├── principal.py               ponto de entrada: DPI, instância única, cria o Aplicativo
├── configuracao/
│   ├── constantes.py          valores ajustáveis (zoom, cache, cores das anotações, porta…)
│   ├── tema.py                cores do tema escuro, fontes e ícones (glifos)
│   └── preferencias.py        preferências do usuário (%APPDATA%\PdfLeve\preferencias.json)
├── servicos/                  lógica sem interface gráfica (testável isoladamente)
│   ├── renderizacao.py        processos auxiliares de renderização
│   ├── anotacoes.py           anotações FreeText: criar, ler, alterar, medir
│   ├── texto.py               palavras, linhas visuais, texto selecionado
│   ├── intervalos.py          “1-5, 8, 11-13” → páginas
│   └── instancia_unica.py     entrega de arquivos a um programa já aberto
├── sistema/
│   └── windows.py             barra de título escura, arrastar arquivos, DPI, ID na barra de tarefas
└── interface/
    ├── aplicativo.py          raiz Tk invisível: janelas, renderizadores, servidor de instância única
    ├── utilidades.py          plural, centralizar, imagens (PPM e PNG com transparência)
    ├── componentes/           BotaoIcone, BotaoPlano, Dica, SeletorCores, SeletorTamanho
    ├── dialogos/              DialogoMensagem, DialogoAnotacao, DialogoExportacao, PainelEstilo
    └── janela/                JanelaPdf, dividida em mixins por responsabilidade
```

As dependências seguem uma direção só: `interface` → `servicos` / `sistema` → `configuracao`.
Os serviços não importam nada da interface.

## A janela (`interface/janela/`)

`JanelaPdf` herda de `tk.Toplevel` e de sete mixins; cada um cuida de um assunto e todos
compartilham o estado criado em `JanelaPdf.__init__`:

| Mixin | Responsabilidade |
|---|---|
| `barra_ferramentas.py` | monta a interface, liga atalhos, avisos, diálogos, tela cheia |
| `arquivo.py` | abrir, carregar, salvar, salvar como, exportar páginas, girar, fechar |
| `visualizacao.py` | disposição das páginas, renderização e cache, rolagem, zoom, navegação, coordenadas |
| `mouse.py` | eventos do mouse, menu de contexto, Esc, modo texto |
| `selecao_texto.py` | seleção e cópia de texto |
| `anotacoes.py` | criar/editar/mover/excluir anotações, cor e tamanho |
| `busca.py` | busca em etapas, contador e navegação entre resultados |

## Renderização

O PyMuPDF não libera o GIL enquanto renderiza, e uma página escaneada em JPEG 2000 pode levar
~600 ms. Por isso as páginas são renderizadas em **processos auxiliares** (`ConjuntoRenderizadores`,
dois por padrão), compartilhados por todas as janelas.

1. `renderizar_visiveis` monta a fila de pedidos da janela: páginas visíveis primeiro, depois as
   próximas na direção da leitura (`PAGINAS_PRE_CARREGADAS`).
2. `distribuir` entrega os pedidos aos processos livres, começando pela janela em foco.
3. `receber` (chamado periodicamente pelo laço do Tk) recebe os pixels e os passa a
   `receber_imagem`, que guarda a imagem no cache (LRU limitado por `LIMITE_PIXELS_CACHE`).

Cada imagem tem a chave `(id_documento, página, escala × 1000, versão_da_página)`. A versão muda
quando a página é girada ou anotada, o que invalida imagens antigas sem precisar apagá-las.

Os processos auxiliares mantêm cópias próprias dos documentos, lidas do disco:

- **rotações** ainda não salvas são espelhadas para eles (mensagem `"girar"`);
- **páginas anotadas** e ainda não salvas (`paginas_locais`) são renderizadas no próprio processo
  da interface até o arquivo ser salvo; depois disso, os auxiliares relêem o arquivo (`"abrir"`).

Antes de substituir o arquivo em disco (salvamento completo), `fechar_documento` pede aos
auxiliares que o fechem e espera a confirmação, porque o Windows não substitui arquivos abertos.

O MuPDF guarda imagens decodificadas sem limite prático; `aparar_deposito_mupdf` esvazia esse
depósito a cada `RENDERIZACOES_ENTRE_LIMPEZAS` páginas.

## Instância única

Ao iniciar, `enviar_para_instancia_aberta` tenta entregar os arquivos a um programa já aberto por
um soquete TCP em `127.0.0.1:48213`. Se ninguém responder, este processo vira a instância principal
e passa a escutar a porta (`ouvir_novas_instancias`). O `Aplicativo` abre cada arquivo recebido em
uma nova janela (ou traz para a frente a janela que já o exibe).

## Detalhes do Windows

- **Arrastar e soltar**: `aceitar_arquivos_arrastados` substitui o procedimento de janela para
  receber `WM_DROPFILES`. O tkinter não pode ser chamado de dentro desse procedimento, então os
  arquivos vão para uma fila lida pelo laço do Tk.
- **Barra de título escura**: `DwmSetWindowAttribute` (modo escuro e, no Windows 11, a cor exata).
- **Atalhos numéricos**: no Tk, `<Control-1>` significa Ctrl + botão 1 do mouse; para a tecla,
  use `<Control-Key-1>`.
- **Temporizadores**: `JanelaPdf.after` agenda no `Aplicativo`, e o callback só roda se a janela
  ainda estiver aberta. Isso evita erros de temporizadores pendentes de janelas fechadas.

## Coordenadas

- **Canvas** (`tela`): pixels da área de rolagem.
- **Página exibida**: pontos PDF da página como aparece (já girada) — `ponto_na_pagina`,
  `retangulo_na_tela`.
- **Página sem rotação**: como o PDF guarda anotações, palavras e resultados de busca.
  Converte-se com `page.rotation_matrix` / `page.derotation_matrix`.
