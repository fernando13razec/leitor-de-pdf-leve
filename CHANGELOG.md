# Histórico de versões

## [Não lançado]

### Adicionado
- O mesmo PDF pode ser aberto em várias janelas, como no navegador: `Ctrl+Shift+N`, o novo botão
  da barra, o item “Abrir em nova janela” do menu de contexto ou abrir de novo um arquivo que já
  está aberto. Cada janela tem rolagem, zoom e busca próprios; anotações e rotações aparecem em
  todas, e salvar em qualquer uma salva o documento. Só a última janela do arquivo pergunta se as
  alterações devem ser salvas.

## [1.0.2] - 2026-10-02

### Adicionado
- Busca de vários termos ao mesmo tempo: separe-os com ponto e vírgula no campo de busca
  (ex.: `multa; prazo de entrega; rescisão`). Cada termo é destacado com uma cor, a navegação
  percorre todas as ocorrências na ordem do documento e o aviso final mostra quantas vezes cada
  termo apareceu.

## [1.0.1] - 2026-09-24

### Alterado
- Novo ícone, vermelho com “PDF”, usado pelo programa e pelos arquivos PDF: fica fácil achar os
  PDFs no meio de outros arquivos no Explorer. Nos tamanhos pequenos, o texto é desenhado pixel a
  pixel para ficar nítido.
- Compatibilidade com o PyMuPDF 1.28 (uso de `import pymupdf` no lugar do nome obsoleto `fitz`).
- O executável passa a ser gerado automaticamente no GitHub Actions a cada nova versão.

## [1.0.0] - 2026-09-24

Primeira versão: renderização em processos auxiliares (páginas escaneadas não travam a
interface), várias janelas numa única instância, anotações de texto coloridas, seleção e cópia
de texto, busca com contador, salvar intervalos de páginas, girar páginas, tela cheia e arrastar
e soltar.
