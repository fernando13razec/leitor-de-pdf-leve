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
│   ├── busca.py               vários termos (“multa; prazo”): separação, ocorrências em ordem de leitura
│   ├── impressao.py           páginas a imprimir, encaixe no papel, processo de impressão
│   ├── assinatura.py          assinatura PAdES e verificação de assinaturas (pyHanko)
│   └── instancia_unica.py     entrega de arquivos a um programa já aberto
├── sistema/
│   ├── windows.py             barra de título escura, arrastar arquivos, DPI, ID na barra de tarefas
│   ├── impressora.py          diálogo de impressão do Windows (PrintDlgEx) e envio à impressora (GDI)
│   └── certificados.py        certificados do Windows e assinatura com a chave do token (CNG)
└── interface/
    ├── aplicativo.py          raiz Tk invisível: janelas, renderizadores, servidor de instância única
    ├── documento_aberto.py    DocumentoAberto: um PDF aberto, compartilhado pelas janelas que o exibem
    ├── utilidades.py          plural, centralizar, imagens (PPM e PNG com transparência)
    ├── componentes/           BotaoIcone, BotaoPlano, Dica, SeletorCores, SeletorTamanho
    ├── dialogos/              DialogoMensagem, DialogoAnotacao, DialogoExportacao, PainelEstilo,
    │                          DialogoAssinatura, DialogoAssinaturas
    └── janela/                JanelaPdf, dividida em mixins por responsabilidade
```

As dependências seguem uma direção só: `interface` → `servicos` / `sistema` → `configuracao`.
Os serviços não importam nada da interface.

## Documento e janelas

O mesmo PDF pode estar em várias janelas (`Ctrl+Shift+N`, botão da barra, menu de contexto ou
abrindo de novo um arquivo que já está aberto). Cada janela é uma **vista** de um
`DocumentoAberto`, que guarda o que é do arquivo: o documento do PyMuPDF, `caminho`, `senha`,
`modificado`, `id_documento`, `versao_pagina`, `retangulos_paginas`, `paginas_locais`, o cache de
palavras e o cache de páginas prontas. A janela lê esses valores por propriedades de mesmo nome;
rolagem, zoom, modo de ajuste, busca, seleções e modo texto são de cada janela.

Uma alteração feita numa vista é avisada a todas pelo documento: `paginas_alteradas` (anotação),
`disposicao_alterada` (rotação: cada janela chama `refazer_por_rotacao`) e `marcar_modificado`
(título com “●”). Salvar em qualquer janela salva o documento; depois de um salvamento completo
ou de “Salvar como”, o documento é relido e todas as vistas o exibem de novo (`exibir`), cada uma
na posição em que estava. Fechar uma janela só a desanexa; a última fecha o documento e é a única
que pergunta se as alterações devem ser salvas. Com mais de uma vista, o título mostra o número
da janela (`contrato.pdf (2) — PDF Leve`).

## A janela (`interface/janela/`)

`JanelaPdf` herda de `tk.Toplevel` e de nove mixins; cada um cuida de um assunto e todos
compartilham o estado criado em `JanelaPdf.__init__`:

| Mixin | Responsabilidade |
|---|---|
| `barra_ferramentas.py` | monta a interface, liga atalhos, avisos, diálogos, tela cheia |
| `arquivo.py` | abrir, carregar/exibir, nova janela do mesmo PDF, salvar, salvar como, exportar páginas, girar, fechar |
| `visualizacao.py` | disposição das páginas, renderização e cache, rolagem, zoom, navegação, coordenadas |
| `mouse.py` | eventos do mouse, menu de contexto, Esc, modo texto |
| `selecao_texto.py` | seleção e cópia de texto |
| `anotacoes.py` | criar/editar/mover/excluir anotações, cor e tamanho |
| `busca.py` | busca em etapas (um ou vários termos, uma cor por termo), contador e navegação entre resultados |
| `impressao.py` | diálogo de impressão e acompanhamento do processo de impressão |
| `assinatura.py` | posicionar o selo, assinar com o token, faixa de verificação das assinaturas |

## Renderização

O PyMuPDF não libera o GIL enquanto renderiza, e uma página escaneada em JPEG 2000 pode levar
~600 ms. Por isso as páginas são renderizadas em **processos auxiliares** (`ConjuntoRenderizadores`,
dois por padrão), compartilhados por todas as janelas.

1. `renderizar_visiveis` monta a fila de pedidos da janela: páginas visíveis primeiro, depois as
   próximas na direção da leitura (`PAGINAS_PRE_CARREGADAS`).
2. `distribuir` entrega os pedidos aos processos livres, começando pela janela em foco.
3. `receber` (chamado periodicamente pelo laço do Tk) recebe os pixels e os passa ao
   `DocumentoAberto.receber_imagem`, que guarda a imagem no cache do documento (LRU limitado por
   `LIMITE_PIXELS_CACHE`) e a oferece a todas as suas janelas (`posicionar_se_visivel`).

O cache e o conjunto `em_renderizacao` são do documento: duas janelas do mesmo PDF no mesmo zoom
não pedem a mesma página duas vezes.

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

## Impressão

`imprimir` abre o diálogo padrão do Windows (`escolher_impressora`, via `PrintDlgExW`), que
devolve a impressora, as configurações do driver (DEVMODE: cópias, papel, orientação…) e as
páginas escolhidas. A impressão roda num **processo próprio** (`processo_impressor`), que recebe o
caminho do arquivo ou, se houver alterações não salvas, o PDF em bytes (`documento.tobytes()`):

1. cria o contexto da impressora (`CreateDCW` com o DEVMODE) e inicia o trabalho (`StartDocW`);
2. para cada página, calcula o encaixe no papel (`calcular_encaixe`: tamanho real, reduzido se não
   couber na área imprimível, centralizado e girado 90° se a orientação diferir da do papel);
3. renderiza a página com o PyMuPDF (até `DPI_MAXIMO_IMPRESSAO`) e a desenha com `StretchDIBits`.

O progresso volta por um `Pipe` lido com `after`. Se a janela for fechada, a conexão é encerrada e
a impressão continua até o fim sem informar o progresso.

## Assinatura digital

A lógica segue a do [pdfcraft](https://github.com/storytold/pdfcraft): o token A3 é usado pelo
**repositório de certificados do Windows** (CNG), e não por PKCS#11. O minidriver do token registra
o certificado em `CurrentUser\My`, e o Windows pede o PIN na própria janela. A chave privada nunca
sai do token.

- `sistema/certificados.py` (ctypes: crypt32 e ncrypt):
  - `listar_certificados` abre cada chave em **modo silencioso**. `NTE_SILENT_CONTEXT` significa
    que o certificado pode ser usado e que o PIN fica para a hora de assinar; erros de cartão
    inteligente significam "token não conectado". A listagem leva alguns segundos e roda numa thread.
  - `assinar_hash` reabre a chave sem modo silencioso, com a janela como dona do diálogo de PIN
    (`NCRYPT_WINDOW_HANDLE_PROPERTY`), e chama `NCryptSignHash` (RSA PKCS#1 v1.5; ECDSA em DER).
  - `cadeia_certificado` monta a cadeia com `CertGetCertificateChain`. `certificados_raiz` e
    `certificados_intermediarios` alimentam a verificação.
- `servicos/assinatura.py` (pyHanko, sem Tk e sem Windows):
  - `AssinanteExterno` é um `Signer` que recebe a função que assina o hash. No programa, essa
    função é `assinar_hash`; nos testes, uma chave em memória.
  - `assinar_pdf` gera PAdES (`/SubFilter /ETSI.CAdES.detached`, SHA-256) num campo novo
    `AssinaturaN`, com selo visível no retângulo escolhido. Inclui carimbo de tempo RFC 3161
    (PAdES-B-T) quando há servidor. A gravação é **incremental**, numa cópia (`_assinado.pdf`), e o
    original fica intacto.
  - `converter_retangulo` leva o retângulo exibido (já girado) para o espaço do PDF.
  - `verificar_assinaturas` devolve, para cada assinatura, uma situação: `valida`,
    `nao_confiavel` (íntegra, mas sem cadeia até uma raiz do Windows), `alterada` (confere, mas o
    arquivo mudou depois de modo não permitido) ou `invalida`. A revogação não é consultada.
- `interface/janela/assinatura.py`:
  - **Fluxo:** `assinar` faz o usuário desenhar o retângulo (modo de posicionamento tratado pelo
    `mouse.py`). Depois vêm o `DialogoAssinatura` e o nome do arquivo de destino. A assinatura roda
    numa thread, e o arquivo assinado é aberto numa nova janela.
  - **Verificação:** ao exibir um PDF com `/SigFlags`, a verificação roda numa thread. O resultado
    fica no `DocumentoAberto` (`assinaturas`) e aparece na faixa de todas as vistas. Salvar descarta
    o resultado, e a verificação é refeita.

As threads não chamam o tkinter. O resultado volta por `executar_em_segundo_plano`
(`interface/utilidades.py`), que usa uma fila lida com `after`. A assinatura não usa processo
auxiliar porque o diálogo de PIN precisa de uma janela deste processo como dona.

**Cuidado:** salvar alterações (anotações, rotações) num PDF assinado faz as assinaturas acusarem
a mudança. Por isso `salvar` pede confirmação (`confirmar_salvar_assinado`). Um salvamento não
incremental invalida as assinaturas de vez.

## Ícones

Um único desenho (folha branca com faixa vermelha “PDF”), gerado por `ferramentas/gerar_icone.py`,
serve ao programa e aos arquivos PDF:

- `recursos/icone.ico`: embutido no `.exe` pelo PyInstaller e usado nas janelas (`iconbitmap`).
  Nos tamanhos até 32 px, o texto é desenhado pixel a pixel para ficar nítido.
- `recursos/icone.png` (alternativa para as janelas) e `recursos/icone-512.png` (README).

Ao registrar o PDF Leve como leitor de PDFs, o `DefaultIcon` do tipo de arquivo
(`PdfLeve.Documento`) e de `Applications\PDF Leve.exe` aponta para o próprio executável
(`"...\PDF Leve.exe",0`).

## Instância única

Ao iniciar, `enviar_para_instancia_aberta` tenta entregar os arquivos a um programa já aberto por
um soquete TCP em `127.0.0.1:48213`. Se ninguém responder, este processo vira a instância principal
e passa a escutar a porta (`ouvir_novas_instancias`). O `Aplicativo` abre cada arquivo recebido em
uma nova janela; se o arquivo já estiver aberto, a nova janela é mais uma vista do mesmo documento.

## Detalhes do Windows

- **Arrastar e soltar**: `aceitar_arquivos_arrastados` substitui o procedimento de janela para
  receber `WM_DROPFILES`. O tkinter não pode ser chamado de dentro desse procedimento, então os
  arquivos vão para uma fila lida pelo laço do Tk.
- **Barra de título escura**: `DwmSetWindowAttribute` (modo escuro e, no Windows 11, a cor exata).
- **Atalhos numéricos**: no Tk, `<Control-1>` significa Ctrl + botão 1 do mouse; para a tecla,
  use `<Control-Key-1>`.
- **Roda do mouse**: no Tk 9, deltas que não são múltiplos de 120 viram `<TouchpadScroll>` em vez
  de `<MouseWheel>`. Esses deltas vêm de touchpads e de mouses de rolagem suave, e depois deles até
  o clique seguinte da roda chega assim. O evento traz os deltas X e Y juntos no `%D`. A função
  `ligar_roda` (`interface/utilidades.py`) liga os dois eventos e entrega os deltas já separados.
  O Tk 8.6 não tem `<TouchpadScroll>` e entrega tudo como `<MouseWheel>`. O executável leva o Tk
  do Python fixado em `.python-version`.
- **Temporizadores**: `JanelaPdf.after` agenda no `Aplicativo`, e o callback só roda se a janela
  ainda estiver aberta. Isso evita erros de temporizadores pendentes de janelas fechadas.

## Coordenadas

- **Canvas** (`tela`): pixels da área de rolagem.
- **Página exibida**: pontos PDF da página como aparece (já girada) — `ponto_na_pagina`,
  `retangulo_na_tela`.
- **Página sem rotação**: como o PDF guarda anotações, palavras e resultados de busca.
  Converte-se com `page.rotation_matrix` / `page.derotation_matrix`.
