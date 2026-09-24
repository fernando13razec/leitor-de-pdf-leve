"""Gera o executável do PDF Leve para Windows (PyInstaller) e o .zip para a Release.

Como rodar (a partir da raiz do projeto, num ambiente com `pip install -r requirements-dev.txt`):

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

# Módulos que o PyInstaller poderia incluir por engano e que o programa não usa.
MODULOS_EXCLUIDOS = ["PIL", "numpy", "pytest", "unittest", "pydoc", "test", "lib2to3", "pymupdf.mupdf_cppyy"]


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
        shutil.rmtree(PASTA_SAIDA / NOME_APLICATIVO, ignore_errors=True)
        escrever_informacoes_de_versao()
        gerar_executavel()
    if opcoes.etapa in ("tudo", "zip"):
        compactar()
        resumo()
