# Histórico de versões

## [Não lançado]

### Corrigido
- A roda do mouse não rolava o documento no programa baixado da Release quando o aparelho tinha
  rolagem de alta resolução: touchpads de notebook e mouses com rolagem suave (como os Logitech MX).
  O Tk 9, usado no executável da Release, entrega esses movimentos como um evento próprio, que o
  programa ignorava. Mouses comuns não eram afetados. A correção vale também para o zoom com
  `Ctrl` + roda e para a lista de certificados da assinatura, que nesses aparelhos também não rolava.

## [1.0.3] - 2026-11-26

### Adicionado
- O mesmo PDF pode ser aberto em várias janelas, como no navegador: `Ctrl+Shift+N`, o novo botão
  da barra, o item “Abrir em nova janela” do menu de contexto ou abrir de novo um arquivo que já
  está aberto. Cada janela tem rolagem, zoom e busca próprios; anotações e rotações aparecem em
  todas, e salvar em qualquer uma salva o documento. Só a última janela do arquivo pergunta se as
  alterações devem ser salvas.
- Impressão (`Ctrl+Shift+P` ou botão de impressora): usa o diálogo de impressão padrão do Windows
  (impressora, cópias, intervalo de páginas, propriedades do driver) e imprime o documento como
  está na tela, inclusive com anotações e rotações ainda não salvas. As páginas são centralizadas
  no papel, reduzidas quando não cabem e giradas quando a orientação difere da do papel. A
  impressão roda em segundo plano, com o progresso no rodapé.
- Assinatura digital com certificado ICP-Brasil A3 em token (`Ctrl+Shift+A` ou botão da caneta):
  arraste na página para posicionar o selo, escolha o certificado e digite o PIN na janela do
  Windows. Gera uma cópia `_assinado.pdf` no padrão PAdES (a mesma assinatura do Acrobat), com
  carimbo de tempo opcional. O token é usado pelo repositório de certificados do Windows, sem
  depender do programa do fabricante.
- Verificação das assinaturas ao abrir um PDF assinado: uma faixa abaixo da barra informa se as
  assinaturas são válidas, se o certificado é de uma autoridade confiável e se o documento foi
  alterado depois de assinado; “Ver assinaturas” mostra os detalhes de cada uma.
- Aviso ao salvar alterações num PDF assinado (as assinaturas passariam a acusar a alteração).

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
