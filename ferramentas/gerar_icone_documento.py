"""Gera o ícone dos ARQUIVOS PDF (o ícone do programa é outro: gerar_icone.py).

Folha branca com o canto dobrado e uma faixa vermelha com “PDF” em branco, para que os PDFs se
destaquem no meio de outros arquivos no Explorer.

Como rodar (a partir da raiz do projeto):

    python ferramentas/gerar_icone_documento.py

Gera recursos/icone-documento.ico (16 a 256 px). Nos tamanhos pequenos (até 32 px) o texto é
desenhado pixel a pixel, para ficar nítido; nos maiores, usa uma fonte em negrito do Windows.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_ICO = RAIZ_PROJETO / "recursos" / "icone-documento.ico"

TAMANHOS_ICO = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
TAMANHO_BASE = 1024
SUPERAMOSTRAGEM = 4

COR_FOLHA = (0xFA, 0xFA, 0xFB, 255)
COR_BORDA_FOLHA = (0xB9, 0xBE, 0xC8, 255)
COR_DOBRA = (0xD5, 0xD9, 0xE0, 255)
COR_LINHA_TEXTO = (0xCF, 0xD3, 0xDB, 255)
COR_VERMELHA = (0xD9, 0x30, 0x25, 255)
COR_TEXTO = (0xFF, 0xFF, 0xFF, 255)

FONTES_NEGRITO = [Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]

# Letras 3×5 para os tamanhos pequenos (1 = pixel aceso).
LETRAS_PIXEL = {
    "P": ["111", "101", "111", "100", "100"],
    "D": ["110", "101", "101", "101", "110"],
    "F": ["111", "100", "110", "100", "100"],
}

# Tamanho → (escala das letras em pixels, linha inicial e final da faixa vermelha)
PEQUENOS = {16: (1, 7, 13), 20: (1, 9, 16), 24: (1, 11, 19), 32: (2, 15, 28)}


def desenhar_folha(lado, esquerda, topo, direita, base, dobra, borda):
    """Folha branca com o canto superior direito dobrado, com antialiasing (supersampling)."""
    grande = lado * SUPERAMOSTRAGEM
    s = SUPERAMOSTRAGEM
    imagem = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    contorno = [(esquerda * s, topo * s), ((direita - dobra) * s, topo * s), (direita * s, (topo + dobra) * s),
                (direita * s, base * s), (esquerda * s, base * s)]
    desenho.polygon(contorno, fill=COR_FOLHA)
    desenho.line(contorno + [contorno[0]], fill=COR_BORDA_FOLHA, width=max(1, round(borda * s)), joint="curve")
    aba = [((direita - dobra) * s, topo * s), ((direita - dobra) * s, (topo + dobra) * s),
           (direita * s, (topo + dobra) * s)]
    desenho.polygon(aba, fill=COR_DOBRA)
    desenho.line(aba + [aba[0]], fill=COR_BORDA_FOLHA, width=max(1, round(borda * s)), joint="curve")
    return imagem.resize((lado, lado), Image.LANCZOS)


def icone_grande(lado):
    """Versão detalhada (40 px ou mais): linhas de texto na folha e “PDF” em fonte negrito."""
    u = lado / 100
    imagem = desenhar_folha(lado, 17 * u, 4 * u, 83 * u, 96 * u, 20 * u, 1.2 * u)
    desenho = ImageDraw.Draw(imagem)
    for y, fim in ((20, 58), (29, 72), (38, 72)):
        desenho.rounded_rectangle((26 * u, y * u, fim * u, (y + 4) * u), radius=2 * u, fill=COR_LINHA_TEXTO)

    faixa = (6 * u, 50 * u, 80 * u, 82 * u)
    desenho.rounded_rectangle(faixa, radius=4 * u, fill=COR_VERMELHA)
    fonte = next((ImageFont.truetype(str(c), round(25 * u)) for c in FONTES_NEGRITO if c.exists()),
                 ImageFont.load_default(round(25 * u)))
    caixa = desenho.textbbox((0, 0), "PDF", font=fonte)
    x = (faixa[0] + faixa[2]) / 2 - (caixa[0] + caixa[2]) / 2
    y = (faixa[1] + faixa[3]) / 2 - (caixa[1] + caixa[3]) / 2
    desenho.text((x, y), "PDF", font=fonte, fill=COR_TEXTO)
    return imagem


def icone_pequeno(lado):
    """Versão para 16–32 px: folha, faixa vermelha em pixels inteiros e letras pixel a pixel."""
    escala, faixa_topo, faixa_base = PEQUENOS[lado]
    margem = 2 if lado <= 24 else 3
    imagem = desenhar_folha(lado, margem, 0, lado - margem, lado, lado * 0.28, 0.6 if lado <= 24 else 0.8)
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((0, faixa_topo, lado - 1 - (1 if lado <= 24 else 2), faixa_base), fill=COR_VERMELHA)

    largura_texto = (3 * 3 + 2) * escala
    altura_texto = 5 * escala
    x0 = (lado - 1 - (1 if lado <= 24 else 2) + 1 - largura_texto) // 2
    y0 = faixa_topo + (faixa_base - faixa_topo + 1 - altura_texto) // 2
    for indice, letra in enumerate("PDF"):
        for linha, bits in enumerate(LETRAS_PIXEL[letra]):
            for coluna, bit in enumerate(bits):
                if bit == "1":
                    x = x0 + (indice * 4 + coluna) * escala
                    y = y0 + linha * escala
                    desenho.rectangle((x, y, x + escala - 1, y + escala - 1), fill=COR_TEXTO)
    return imagem


def principal():
    mestre = icone_grande(TAMANHO_BASE)
    versoes = {t: icone_pequeno(t) if t in PEQUENOS else mestre.resize((t, t), Image.LANCZOS)
               for t in TAMANHOS_ICO}
    maior = versoes[max(TAMANHOS_ICO)]
    maior.save(CAMINHO_ICO, format="ICO", sizes=[(t, t) for t in TAMANHOS_ICO],
               append_images=[versoes[t] for t in TAMANHOS_ICO if t != max(TAMANHOS_ICO)])
    print(f"Gerado: {CAMINHO_ICO.relative_to(RAIZ_PROJETO)}")
    return versoes


if __name__ == "__main__":
    principal()
