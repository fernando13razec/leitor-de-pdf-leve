# Assinatura de código (SignPath Foundation)

O executável é gerado no GitHub Actions (`.github/workflows/release.yml`). O passo de assinatura
já está no fluxo e é ativado automaticamente quando a configuração abaixo existir no repositório.

## Por que a SignPath

- Gratuita para projetos de código aberto (licença aprovada pela OSI, como a MIT).
- A assinatura sai em nome da **SignPath Foundation**: os dados pessoais do mantenedor não ficam
  expostos no executável (certificados ICP-Brasil, como e-CPF e OAB, não servem para assinar
  programas: não têm o uso “Assinatura de Código” e contêm nome e CPF).
- Exige que o executável seja gerado a partir do código-fonte num serviço de integração contínua,
  o que este repositório já faz.

## Passo a passo

1. Inscreva o projeto em <https://signpath.org> (programa para código aberto). O repositório já
   atende aos requisitos técnicos: licença MIT, código público e executável gerado no GitHub Actions.
2. Após a aprovação, no painel da SignPath, anote: o **ID da organização**, o **slug do projeto**,
   o **slug da política de assinatura** (ex.: `release-signing`) e o **slug da configuração de
   artefato**. A configuração de artefato deve assinar `PDF Leve.exe` na raiz do artefato
   (o executável que o PyInstaller gera).
3. No GitHub: **Settings → Secrets and variables → Actions** e crie:
   - Segredo `SIGNPATH_API_TOKEN`: token de API de um usuário “CI” criado na SignPath.
   - Variáveis `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`
     e `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`.
4. Na SignPath, conecte o projeto a este repositório do GitHub (a SignPath confere de onde veio
   o artefato).
5. Acrescente ao README a menção exigida pela SignPath Foundation, por exemplo:
   “Assinatura de código gratuita fornecida pela [SignPath.io](https://signpath.io),
   certificado da [SignPath Foundation](https://signpath.org).” Acrescente também a política de
   assinatura de código que eles pedirem.

A partir daí, cada tag `v*` gera uma Release com o executável assinado. Sem a variável
`SIGNPATH_ORGANIZATION_ID`, o fluxo continua funcionando e publica o executável sem assinatura.

## Observação sobre o SmartScreen

A assinatura faz o Windows mostrar o editor e garante a integridade do arquivo. O aviso do
SmartScreen, porém, também depende da reputação do arquivo, que cresce com os downloads: um
programa novo pode continuar mostrando o aviso por um tempo, mesmo assinado.
