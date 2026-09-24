"""Gera o ícone do aplicativo "PDF Leve".

Desenha, com Pillow, uma superelipse grafite escuro contendo uma folha de
documento com o canto superior direito dobrado, linhas de texto estilizadas
(uma azul de destaque e as demais cinza claro) e, nos tamanhos maiores, uma
pequena pena azul que remete a "leve".

Como rodar (a partir da raiz do projeto):

    python ferramentas/gerar_icone.py

Arquivos gerados (relativos à raiz do projeto):

    recursos/icone.ico      -> ICO multi-resolução (16, 20, 24, 32, 40, 48, 64, 128, 256 px)
    recursos/icone.png      -> PNG 256x256 com transparência (ícone das janelas Tk)
    recursos/icone-512.png  -> PNG 512x512 para o README

Os tamanhos de 16 a 32 px usam uma versão simplificada do desenho (menos
linhas, formas mais grossas e sem a pena) para continuar legível.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

# --- Caminhos -----------------------------------------------------------------
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_RECURSOS = RAIZ_PROJETO / "recursos"
CAMINHO_ICO = PASTA_RECURSOS / "icone.ico"
CAMINHO_PNG = PASTA_RECURSOS / "icone.png"
CAMINHO_PNG_512 = PASTA_RECURSOS / "icone-512.png"

# --- Parâmetros de desenho ----------------------------------------------------
TAMANHO_BASE = 1024          # resolução de trabalho antes das reduções
SUPERAMOSTRAGEM = 2          # fator extra para antialiasing das bordas
TAMANHOS_ICO = [16, 20, 24, 32, 40, 48, 64, 128, 256]
LIMITE_SIMPLIFICADO = 32     # tamanhos <= este usam o desenho simplificado

# --- Paleta (combina com o tema escuro do app) -------------------------------
COR_FUNDO_TOPO = (0x25, 0x26, 0x2A)
COR_FUNDO_BASE = (0x1B, 0x1C, 0x1F)
COR_FOLHA = (0xEC, 0xEE, 0xF3)
COR_DOBRA = (0xC3, 0xC8, 0xD4)
COR_DESTAQUE = (0x7A, 0xA2, 0xF7)
COR_LINHA = (0xB4, 0xBA, 0xC8)
COR_LINHA_PEQUENA = (0x8C, 0x93, 0xA6)  # mais escura: contraste em 16-32 px
COR_BORDA_SUPERELIPSE = (0x34, 0x36, 0x3C)


def pontos_superelipse(x0: float, y0: float, x1: float, y1: float,
                    expoente: float = 5.0, passos: int = 720) -> list[tuple[float, float]]:
    """Retorna os pontos de uma superelipse (squircle) inscrita no retângulo."""
    centro_x, centro_y = (x0 + x1) / 2, (y0 + y1) / 2
    raio_x, raio_y = (x1 - x0) / 2, (y1 - y0) / 2
    pontos = []
    for i in range(passos):
        angulo = 2 * math.pi * i / passos
        cosseno, seno = math.cos(angulo), math.sin(angulo)
        px = abs(cosseno) ** (2 / expoente) * math.copysign(1, cosseno)
        py = abs(seno) ** (2 / expoente) * math.copysign(1, seno)
        pontos.append((centro_x + raio_x * px, centro_y + raio_y * py))
    return pontos


def gradiente_vertical(tamanho: int, cor_topo, cor_base) -> Image.Image:
    """Cria uma imagem RGBA com gradiente vertical entre duas cores."""
    faixa = Image.new("RGBA", (1, tamanho))
    for y in range(tamanho):
        t = y / max(1, tamanho - 1)
        cor = tuple(round(a + (b - a) * t) for a, b in zip(cor_topo, cor_base))
        faixa.putpixel((0, y), cor + (255,))
    return faixa.resize((tamanho, tamanho))


def pontos_pena(centro_x: float, centro_y: float, comprimento: float,
                largura: float, angulo_graus: float) -> tuple[list, list]:
    """Retorna (contorno, nervura) de uma pena estilizada, já rotacionados."""
    passos = 80
    lado_a, lado_b = [], []
    for i in range(passos + 1):
        t = i / passos
        # Perfil assimétrico: mais largo perto da base, afinando na ponta.
        meia_largura = largura / 2 * (math.sin(math.pi * t) ** 0.9) * (1 - 0.35 * t)
        x = (t - 0.5) * comprimento
        lado_a.append((x, -meia_largura))
        lado_b.append((x, meia_largura * 0.8))
    contorno = lado_a + lado_b[::-1]
    nervura = [(-0.62 * comprimento, 0.0), (0.42 * comprimento, 0.0)]

    angulo = math.radians(angulo_graus)
    cos_a, sin_a = math.cos(angulo), math.sin(angulo)

    def girar(pontos):
        return [(centro_x + x * cos_a - y * sin_a, centro_y + x * sin_a + y * cos_a)
                for x, y in pontos]

    return girar(contorno), girar(nervura)


def desenhar_icone(tamanho: int, simplificado: bool = False) -> Image.Image:
    """Desenha o ícone em `tamanho` px, com supersampling e antialiasing."""
    lado = tamanho * SUPERAMOSTRAGEM
    u = lado / 100  # unidade: 1% do lado

    # Máscara da superelipse (margem pequena; nos tamanhos pequenos ocupa quase tudo).
    margem = 1.0 * u if simplificado else 3.0 * u
    mascara = Image.new("L", (lado, lado), 0)
    contorno_superelipse = pontos_superelipse(margem, margem, lado - margem, lado - margem)
    ImageDraw.Draw(mascara).polygon(contorno_superelipse, fill=255)

    icone = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    icone.paste(gradiente_vertical(lado, COR_FUNDO_TOPO, COR_FUNDO_BASE), (0, 0), mascara)
    desenho = ImageDraw.Draw(icone)

    # Contorno sutil da superelipse, ajuda a destacá-lo sobre fundos escuros.
    if not simplificado:
        desenho.line(contorno_superelipse + [contorno_superelipse[0]],
                     fill=COR_BORDA_SUPERELIPSE, width=max(1, round(0.5 * u)))

    # --- Folha do documento --------------------------------------------------
    if simplificado:
        esquerda, topo, direita, base = 21 * u, 13 * u, 79 * u, 87 * u
        dobra = 20 * u
        raio_folha = 4 * u
    else:
        esquerda, topo, direita, base = 26 * u, 17 * u, 74 * u, 83 * u
        dobra = 15 * u
        raio_folha = 3.5 * u

    # Folha com cantos arredondados e o canto superior direito cortado.
    folha = Image.new("L", (lado, lado), 0)
    desenho_folha = ImageDraw.Draw(folha)
    desenho_folha.rounded_rectangle((esquerda, topo, direita, base), radius=raio_folha, fill=255)
    desenho_folha.polygon([(direita - dobra, topo - 1), (direita + 1, topo - 1),
                           (direita + 1, topo + dobra)], fill=0)
    icone.paste(Image.new("RGBA", (lado, lado), COR_FOLHA + (255,)), (0, 0), folha)

    # Aba dobrada (triângulo com o ângulo reto voltado para dentro da folha).
    desenho.polygon([(direita - dobra, topo), (direita - dobra, topo + dobra),
                     (direita, topo + dobra)], fill=COR_DOBRA)

    # --- Linhas de texto -----------------------------------------------------
    margem_texto = 7 * u
    x_inicio = esquerda + margem_texto
    x_fim = direita - margem_texto
    if simplificado:
        espessura = 11 * u
        linhas = [
            (topo + 31 * u, x_fim, COR_DESTAQUE),
            (topo + 53 * u, x_fim - 10 * u, COR_LINHA_PEQUENA),
        ]
    else:
        espessura = 5 * u
        linhas = [
            (topo + 26 * u, x_fim, COR_DESTAQUE),
            (topo + 37 * u, x_fim, COR_LINHA),
            (topo + 48 * u, x_fim - 8 * u, COR_LINHA),
            (topo + 59 * u, x_fim - 20 * u, COR_LINHA),
        ]
    for y, x_final, cor in linhas:
        desenho.rounded_rectangle((x_inicio, y - espessura / 2, x_final, y + espessura / 2),
                                  radius=espessura / 2, fill=cor)

    # --- Pena (detalhe "leve"), apenas nos tamanhos maiores -----------------
    if not simplificado:
        contorno_pena, nervura = pontos_pena(
            centro_x=direita - 4 * u, centro_y=base - 6 * u,
            comprimento=26 * u, largura=10 * u, angulo_graus=-50)
        # Anel da cor do fundo em volta da pena para separá-la da folha.
        desenho.line(contorno_pena + [contorno_pena[0]], fill=COR_FUNDO_BASE,
                     width=round(3 * u), joint="curve")
        desenho.polygon(contorno_pena, fill=COR_DESTAQUE)
        desenho.line(nervura, fill=COR_FUNDO_TOPO, width=max(1, round(1.0 * u)))

    # Recorta tudo pela superelipse e reduz com antialiasing.
    alfa = Image.composite(icone.getchannel("A"), Image.new("L", (lado, lado), 0), mascara)
    icone.putalpha(alfa)
    return icone.resize((tamanho, tamanho), Image.LANCZOS)


def gerar_versao(tamanho: int, mestre_completo: Image.Image,
                 mestre_simplificado: Image.Image) -> Image.Image:
    """Reduz o desenho mestre adequado (completo ou simplificado) para `tamanho`."""
    mestre = mestre_simplificado if tamanho <= LIMITE_SIMPLIFICADO else mestre_completo
    return mestre.resize((tamanho, tamanho), Image.LANCZOS)


def principal() -> None:
    PASTA_RECURSOS.mkdir(parents=True, exist_ok=True)

    mestre_completo = desenhar_icone(TAMANHO_BASE, simplificado=False)
    mestre_simplificado = desenhar_icone(TAMANHO_BASE, simplificado=True)

    versoes = {t: gerar_versao(t, mestre_completo, mestre_simplificado)
               for t in TAMANHOS_ICO + [512]}

    # ICO: a maior imagem é a base; as demais entram via append_images para
    # que cada tamanho use sua própria versão (incluindo as simplificadas).
    maior = versoes[max(TAMANHOS_ICO)]
    demais = [versoes[t] for t in TAMANHOS_ICO if t != max(TAMANHOS_ICO)]
    maior.save(CAMINHO_ICO, format="ICO",
               sizes=[(t, t) for t in TAMANHOS_ICO], append_images=demais)

    versoes[256].save(CAMINHO_PNG, format="PNG", optimize=True)
    versoes[512].save(CAMINHO_PNG_512, format="PNG", optimize=True)

    for caminho in (CAMINHO_ICO, CAMINHO_PNG, CAMINHO_PNG_512):
        print(f"Gerado: {caminho.relative_to(RAIZ_PROJETO)}")


if __name__ == "__main__":
    principal()
