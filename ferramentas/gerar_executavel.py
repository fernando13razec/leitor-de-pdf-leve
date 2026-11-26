"""Gera o executável do PDF Leve para Windows (PyInstaller) e o .zip para a Release.

Como rodar (a partir da raiz do projeto, com o Python da versão fixada em `.python-version` e
`pip install -r requirements-dev.txt`):

    python ferramentas/gerar_executavel.py                     # executável + zip
    python ferramentas/gerar_executavel.py --etapa executavel  # só o executável
    python ferramentas/gerar_executavel.py --etapa zip         # só o zip (ex.: depois de assinar o .exe)
    python ferramentas/gerar_executavel.py --versao            # mostra a versão (usado no GitHub Actions)

Resultado:
    dist/PDF Leve/PDF Leve.exe               programa (com a pasta _internal ao lado)
    dist/PDF-Leve-<versão>-windows-x64.zip   pasta compactada para distribuição

Usa o modo “pasta” (onedir) em vez de arquivo único: o programa inicia mais rápido, pois não
precisa se descompactar a cada abertura (nem nos processos auxiliares de renderização).
"""

import argparse
import hashlib
import platform
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO))

from pdf_leve.configuracao.constantes import NOME_APLICATIVO, VERSAO  # noqa: E402

PASTA_TRABALHO = RAIZ_PROJETO / "build"
PASTA_SAIDA = RAIZ_PROJETO / "dist"
ARQUIVO_VERSAO = PASTA_TRABALHO / "versao_windows.txt"
ZIP_SAIDA = PASTA_SAIDA / f"PDF-Leve-{VERSAO}-windows-x64.zip"
# Versão do Python que gera o executável, neste PC e no GitHub Actions (que lê o mesmo arquivo).
ARQUIVO_VERSAO_PYTHON = RAIZ_PROJETO / ".python-version"

# Módulos que o PyInstaller poderia incluir por engano e que o programa não usa.
# O PyMuPDF importa `PIL` (Pixmap.pil_save), `pandas` (Table.to_pandas) e `fontTools`
# (Document.subset_fonts) só dentro dessas funções, que o programa não chama. Num Python com
# muitos pacotes instalados, o `pandas` puxa `scipy`, que puxa `torch`, `transformers`, `cv2`…
# (centenas de MB); por isso ele e os demais ficam de fora.
MODULOS_EXCLUIDOS = ["PIL", "pandas", "fontTools", "numpy", "pytest", "unittest", "pydoc", "test", "lib2to3",
                     "pymupdf.mupdf_cppyy"]
# O pyHanko (assinatura digital) importa partes sob demanda (ex.: cliente HTTP do carimbo de tempo),
# que a análise automática do PyInstaller não enxerga.
PACOTES_COMPLETOS = ["pyhanko", "pyhanko_certvalidator"]


def conferir_versao_do_python():
    """Para com um erro se este Python não for o fixado em .python-version.

    O executável leva junto o Python e o Tk de quem o gera (o Tk 9 e o 8.6, por exemplo, tratam a
    roda do mouse de jeitos diferentes). Com a mesma versão aqui e no GitHub Actions, o executável
    gerado neste PC fica igual ao da Release.
    """
    import tkinter

    fixada = ARQUIVO_VERSAO_PYTHON.read_text(encoding="utf-8").strip()
    atual = platform.python_version()
    print(f"Python {atual}, Tk {tkinter.TkVersion}")
    if atual != fixada:
        sys.exit(f"Este é o Python {atual}, mas o executável é gerado com o {fixada}, fixado em "
                 f"{ARQUIVO_VERSAO_PYTHON.name} e usado também pelo GitHub Actions. Instale o Python "
                 f"{fixada} ou, para mudar a versão também na Release, altere {ARQUIVO_VERSAO_PYTHON.name}.")


def escrever_informacoes_de_versao():
    """Informações exibidas em Propriedades → Detalhes do .exe no Windows."""
    numeros = tuple(int(parte) for parte in VERSAO.split(".")) + (0,)
    PASTA_TRABALHO.mkdir(exist_ok=True)
    ARQUIVO_VERSAO.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros}, prodvers={numeros}),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('ProductName', '{NOME_APLICATIVO}'),
      StringStruct('FileDescription', '{NOME_APLICATIVO} — leitor de PDF leve'),
      StringStruct('ProductVersion', '{VERSAO}'),
      StringStruct('FileVersion', '{VERSAO}'),
      StringStruct('OriginalFilename', '{NOME_APLICATIVO}.exe'),
      StringStruct('LegalCopyright', 'Licença MIT'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])]),
  ]
)
""", encoding="utf-8")


def gerar_executavel():
    import PyInstaller.__main__

    argumentos = [
        str(RAIZ_PROJETO / "iniciar.pyw"),
        "--name", NOME_APLICATIVO,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(RAIZ_PROJETO / "recursos" / "icone.ico"),
        "--add-data", f"{RAIZ_PROJETO / 'recursos'}{';'}recursos",
        "--version-file", str(ARQUIVO_VERSAO),
        "--distpath", str(PASTA_SAIDA),
        "--workpath", str(PASTA_TRABALHO),
        "--specpath", str(PASTA_TRABALHO),
    ]
    for modulo in MODULOS_EXCLUIDOS:
        argumentos += ["--exclude-module", modulo]
    for pacote in PACOTES_COMPLETOS:
        argumentos += ["--collect-submodules", pacote, "--collect-data", pacote]
    PyInstaller.__main__.run(argumentos)


def compactar():
    pasta_programa = PASTA_SAIDA / NOME_APLICATIVO
    ZIP_SAIDA.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_SAIDA, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as arquivo_zip:
        for caminho in sorted(pasta_programa.rglob("*")):
            arquivo_zip.write(caminho, Path(NOME_APLICATIVO) / caminho.relative_to(pasta_programa))
        arquivo_zip.write(RAIZ_PROJETO / "LICENSE", Path(NOME_APLICATIVO) / "LICENSE.txt")


def resumo():
    tamanho_pasta = sum(c.stat().st_size for c in (PASTA_SAIDA / NOME_APLICATIVO).rglob("*") if c.is_file())
    soma = hashlib.sha256(ZIP_SAIDA.read_bytes()).hexdigest()
    print(f"\nPasta:  {PASTA_SAIDA / NOME_APLICATIVO}  ({tamanho_pasta / 2**20:.1f} MB)")
    print(f"Zip:    {ZIP_SAIDA}  ({ZIP_SAIDA.stat().st_size / 2**20:.1f} MB)")
    print(f"SHA256: {soma}")


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description="Gera o executável e o zip do PDF Leve.")
    analisador.add_argument("--etapa", choices=["tudo", "executavel", "zip"], default="tudo")
    analisador.add_argument("--versao", action="store_true", help="só mostra a versão e sai")
    opcoes = analisador.parse_args()
    if opcoes.versao:
        print(VERSAO)
        sys.exit()
    if opcoes.etapa in ("tudo", "executavel"):
        conferir_versao_do_python()  # antes de apagar o executável anterior
        shutil.rmtree(PASTA_SAIDA / NOME_APLICATIVO, ignore_errors=True)
        escrever_informacoes_de_versao()
        gerar_executavel()
    if opcoes.etapa in ("tudo", "zip"):
        compactar()
        resumo()
