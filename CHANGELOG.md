# Histórico de versões

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
