"""Intervalos de páginas digitados pelo usuário (ex.: “1-5, 8, 11-13”)."""

import re


def interpretar_intervalos(texto, total):
    """Converte '1-5, 8, 11-13' em índices de página (base 0), na ordem digitada e sem repetições.

    Aceita também '10-' (da 10 até o fim) e '-3' (do início até a 3).
    Retorna (paginas, None) ou ([], mensagem_de_erro).
    """
    texto = texto.replace("–", "-").replace("—", "-")
    partes = [parte.strip() for parte in re.split(r"[,;]", texto) if parte.strip()]
    if not partes:
        return [], "Informe as páginas"
    paginas, vistas = [], set()
    for parte in partes:
        faixa = re.fullmatch(r"(\d*)\s*-\s*(\d*)", parte)
        if faixa and (faixa.group(1) or faixa.group(2)):
            inicio = int(faixa.group(1)) if faixa.group(1) else 1
            fim = int(faixa.group(2)) if faixa.group(2) else total
        elif parte.isdigit():
            inicio = fim = int(parte)
        else:
            return [], f"Intervalo inválido: “{parte}”"
        if inicio > fim:
            return [], f"Intervalo invertido: “{parte}”"
        if inicio < 1 or fim > total:
            return [], f"O documento tem páginas de 1 a {total}"
        for pagina in range(inicio - 1, fim):
            if pagina not in vistas:
                vistas.add(pagina)
                paginas.append(pagina)
    return paginas, None


def agrupar_sequencias(paginas):
    """[0, 1, 2, 7, 10, 11] -> [(0, 2), (7, 7), (10, 11)], para copiar páginas em blocos."""
    sequencias = []
    for pagina in paginas:
        if sequencias and pagina == sequencias[-1][1] + 1:
            sequencias[-1][1] = pagina
        else:
            sequencias.append([pagina, pagina])
    return [tuple(sequencia) for sequencia in sequencias]
