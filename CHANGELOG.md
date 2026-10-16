# Histórico de versões

## [Não lançado]

### Adicionado
- Impressão (`Ctrl+Shift+P` ou botão de impressora): usa o diálogo de impressão padrão do Windows
  (impressora, cópias, intervalo de páginas, propriedades do driver) e imprime o documento como
  está na tela, inclusive com anotações e rotações ainda não salvas. As páginas são centralizadas
  no papel, reduzidas quando não cabem e giradas quando a orientação difere da do papel. A
  impressão roda em segundo plano, com o progresso no rodapé.

### Alterado
- O botão “Salvar páginas em PDF” (`Ctrl+P`) ganhou ícone próprio; o de impressora agora imprime.

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
