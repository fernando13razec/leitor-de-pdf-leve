"""Assinatura digital: posicionar o selo na página, escolher o certificado, assinar com o token
(em segundo plano) e mostrar a faixa com a verificação das assinaturas do documento aberto.

Assinar e verificar rodam em threads (a assinatura espera o PIN, que o Windows pede na própria
janela; a verificação pode demorar). Nenhuma das duas toca no tkinter: os resultados voltam por
`executar_em_segundo_plano`. Não se usa processo auxiliar porque o diálogo do PIN precisa da
janela (HWND) deste processo como dona.
"""

import os
import tkinter as tk
from tkinter import filedialog

import pymupdf

from pdf_leve.configuracao.constantes import (
    INTERVALO_VERIFICACAO_ASSINATURA_MS, TAMANHO_MINIMO_SELO, TAMANHO_PADRAO_SELO,
)
from pdf_leve.configuracao.tema import (
    COR_CONTORNO_SELO, COR_DESTAQUE, COR_FAIXA_ASSINATURAS, COR_LINHA, COR_TEXTO, COR_TEXTO_SUAVE, fonte_icone,
    fontes, glifo,
)
from pdf_leve.interface.dialogos import DialogoAssinatura, DialogoAssinaturas
from pdf_leve.interface.dialogos.assinatura import APARENCIA_SITUACAO
from pdf_leve.interface.utilidades import executar_em_segundo_plano, plural
from pdf_leve.servicos.assinatura import (
    AssinanteExterno, ErroCarimboTempo, OpcoesAssinatura, assinar_pdf, converter_retangulo, nome_arquivo_assinado,
    possui_assinaturas, verificar_assinaturas,
)
from pdf_leve.sistema.certificados import (
    ErroCertificado, assinar_hash, cadeia_certificado, certificados_intermediarios, certificados_raiz,
)
from pdf_leve.sistema.windows import NO_WINDOWS, identificador_janela

TIPOS_PDF = [("Arquivos PDF", "*.pdf")]
DURACAO_AVISO_SELO_MS = 8000


class MixinAssinatura:

    # ------------------------------------------------------------------ assinar
    def assinar(self):
        """Começa a assinatura: o usuário desenha o retângulo do selo na página."""
        if not self.documento:
            return
        if self.assinando:
            self.avisar("Uma assinatura deste documento já está em andamento")
            return
        if not NO_WINDOWS:
            self.mostrar_erro("A assinatura com certificado digital só está disponível no Windows.")
            return
        if not self.documento.permissions & pymupdf.PDF_PERM_ANNOTATE:
            self.mostrar_erro("O autor deste PDF não permite que ele receba assinaturas.")
            return
        if self.modificado:
            resposta = self.perguntar(
                "Assinar digitalmente", "O documento tem alterações não salvas. A assinatura vale para o arquivo "
                "salvo; salve-o antes de assinar.",
                [("Cancelar", None, False), ("Salvar e continuar", "sim", True)], "sim")
            if resposta != "sim" or not self.salvar():
                return
        if self.modo_texto:
            self.alternar_modo_texto()
        self.posicionando_selo = {}
        self.tela.config(cursor="crosshair")
        self.avisar("Arraste na página para posicionar a assinatura · Esc cancela", DURACAO_AVISO_SELO_MS)

    def cancelar_posicionamento_selo(self):
        self.posicionando_selo = None
        self.tela.delete("selo")
        self.tela.config(cursor="")
        self.rotulo_aviso.place_forget()

    def _ponto_do_selo(self, evento, pagina):
        """Ponto do mouse em coordenadas da página `pagina`, trazido para dentro dela."""
        x_tela, y_tela = self._posicao_na_tela(evento)
        x, y, largura, altura = self.disposicao[pagina]
        escala = self.zoom * self.escala_base
        return pymupdf.Point((min(max(x_tela, x), x + largura) - x) / escala,
                             (min(max(y_tela, y), y + altura) - y) / escala)

    def iniciar_selo(self, evento):
        local = self.ponto_na_pagina(*self._posicao_na_tela(evento))
        if local:
            self.posicionando_selo = {"pagina": local[0], "inicio": local[1], "fim": local[1]}

    def arrastar_selo(self, evento):
        if "pagina" not in self.posicionando_selo:
            return
        self.posicionando_selo["fim"] = self._ponto_do_selo(evento, self.posicionando_selo["pagina"])
        self._desenhar_selo(self.posicionando_selo["pagina"], self._retangulo_do_selo())

    def concluir_selo(self, evento):
        if "pagina" not in self.posicionando_selo:
            return
        self.posicionando_selo["fim"] = self._ponto_do_selo(evento, self.posicionando_selo["pagina"])
        pagina, retangulo = self.posicionando_selo["pagina"], self._retangulo_do_selo(completar=True)
        self.posicionando_selo = None
        self.tela.config(cursor="")
        self.rotulo_aviso.place_forget()
        self._desenhar_selo(pagina, retangulo)
        try:
            self._escolher_certificado(pagina, retangulo)
        finally:
            self.tela.delete("selo")

    def _retangulo_do_selo(self, completar=False):
        """Retângulo arrastado (coordenadas exibidas). Com `completar`, um simples clique ganha o
        tamanho padrão, e um retângulo pequeno demais, o tamanho mínimo, sem sair da página."""
        selo = self.posicionando_selo
        retangulo = pymupdf.Rect(selo["inicio"], selo["fim"])
        retangulo.normalize()
        if not completar:
            return retangulo
        limites = self.retangulos_paginas[selo["pagina"]]
        largura_minima, altura_minima = TAMANHO_MINIMO_SELO
        if retangulo.width < largura_minima and retangulo.height < altura_minima:
            largura_minima, altura_minima = TAMANHO_PADRAO_SELO  # foi só um clique
        largura = min(max(retangulo.width, largura_minima), limites.width)
        altura = min(max(retangulo.height, altura_minima), limites.height)
        x0 = min(retangulo.x0, limites.width - largura)
        y0 = min(retangulo.y0, limites.height - altura)
        return pymupdf.Rect(x0, y0, x0 + largura, y0 + altura)

    def _desenhar_selo(self, pagina, retangulo):
        self.tela.delete("selo")
        self.tela.create_rectangle(*self.retangulo_na_tela(pagina, retangulo), tags="selo",
                                   outline=COR_CONTORNO_SELO, width=2, dash=(6, 3))

    def _escolher_certificado(self, pagina, retangulo):
        dialogo = DialogoAssinatura(self, self.preferencias)
        self.tela.focus_set()
        if not dialogo.resultado:
            return
        escolha = dialogo.resultado
        destino = filedialog.asksaveasfilename(
            parent=self, title="Salvar PDF assinado", defaultextension=".pdf",
            initialdir=os.path.dirname(self.caminho),
            initialfile=os.path.basename(nome_arquivo_assinado(self.caminho)), filetypes=TIPOS_PDF)
        if not destino:
            return
        destino = os.path.abspath(destino)
        if os.path.normcase(destino) == os.path.normcase(self.caminho):
            self.mostrar_erro("Escolha outro nome: o PDF assinado é salvo como uma cópia do original.")
            return
        if self.aplicativo.documento_do_arquivo(destino):
            self.mostrar_erro(f"“{os.path.basename(destino)}” está aberto no PDF Leve. Feche-o ou escolha outro nome.")
            return
        opcoes = OpcoesAssinatura(
            pagina=pagina, retangulo=converter_retangulo(self.documento[pagina], retangulo),
            motivo=escolha["motivo"], local=escolha["local"], url_carimbo_tempo=escolha["url_carimbo_tempo"],
            senha=self.senha)
        self._executar_assinatura(self.caminho, destino, escolha["certificado"], opcoes)

    def _executar_assinatura(self, origem, destino, certificado, opcoes):
        hwnd = identificador_janela(self)  # lido aqui: a thread não pode chamar o Tk

        def tarefa():
            assinante = AssinanteExterno(
                certificado.der, cadeia_certificado(certificado.der),
                lambda hash_, algoritmo: assinar_hash(certificado.impressao_digital, hash_, algoritmo, hwnd))
            assinar_pdf(origem, destino, assinante, opcoes)

        def ao_concluir(_resultado, erro):
            self.assinando = False
            if erro is None:
                self.aplicativo.abrir_arquivos([destino], origem=self)
            elif isinstance(erro, ErroCertificado) and erro.cancelado:
                self.avisar("Assinatura cancelada")
            elif isinstance(erro, ErroCarimboTempo) and opcoes.url_carimbo_tempo:
                resposta = self.perguntar(
                    "Assinar digitalmente",
                    f"Não foi possível obter o carimbo de tempo de {opcoes.url_carimbo_tempo}:\n{erro}\n\n"
                    "Sem o carimbo, a data da assinatura será a do relógio deste computador.",
                    [("Cancelar", None, False), ("Assinar sem carimbo", "sim", True)], "sim")
                if resposta == "sim":
                    opcoes.url_carimbo_tempo = None
                    self._executar_assinatura(origem, destino, certificado, opcoes)
            else:
                self.mostrar_erro(f"Não foi possível assinar o documento:\n{erro}")

        self.assinando = True
        self.avisar("Assinando… digite o PIN do token quando o Windows pedir", DURACAO_AVISO_SELO_MS)
        executar_em_segundo_plano(self, tarefa, ao_concluir, INTERVALO_VERIFICACAO_ASSINATURA_MS)

    # ------------------------------------------------------------------ faixa de verificação
    def _montar_faixa_assinaturas(self):
        self.faixa_assinaturas = faixa = tk.Frame(self, bg=COR_FAIXA_ASSINATURAS, padx=10, pady=5)
        self.icone_faixa = tk.Label(faixa, text=glifo("certificado"), font=fonte_icone(12),
                                    bg=COR_FAIXA_ASSINATURAS, fg=COR_TEXTO_SUAVE)
        self.icone_faixa.pack(side="left", padx=(2, 8))
        self.texto_faixa = tk.Label(faixa, text="", font=fontes.interface, bg=COR_FAIXA_ASSINATURAS, fg=COR_TEXTO,
                                    anchor="w")
        self.texto_faixa.pack(side="left", fill="x", expand=True)
        self.detalhes_faixa = tk.Label(faixa, text="Ver assinaturas", font=fontes.interface,
                                       bg=COR_FAIXA_ASSINATURAS, fg=COR_DESTAQUE, cursor="hand2")
        self.detalhes_faixa.pack(side="right")
        self.detalhes_faixa.bind("<Button-1>", lambda e: self.mostrar_assinaturas())
        self.linha_faixa = tk.Frame(self, bg=COR_LINHA, height=1)

    def atualizar_faixa_assinaturas(self):
        """Mostra (ou esconde) a faixa conforme as assinaturas do documento; começa a verificação
        quando ela ainda não foi feita para o arquivo atual."""
        aberto = self.aberto
        if not aberto or not aberto.documento or not possui_assinaturas(aberto.documento):
            self._esconder_faixa()
            return
        if aberto.assinaturas is None and aberto.erro_assinaturas is None:
            self._verificar_assinaturas(aberto)
            self._mostrar_faixa("certificado", COR_TEXTO_SUAVE, "Documento assinado digitalmente · verificando…")
            return
        if aberto.erro_assinaturas is not None:
            self._mostrar_faixa("assinatura_alerta", APARENCIA_SITUACAO["nao_confiavel"][1],
                                "Não foi possível verificar as assinaturas deste documento")
            return
        resultados = aberto.assinaturas
        if not resultados:
            self._esconder_faixa()
            return
        for situacao in ("invalida", "alterada", "nao_confiavel"):
            afetadas = [r for r in resultados if r.situacao == situacao]
            if afetadas:
                nome_glifo, cor, descricao = APARENCIA_SITUACAO[situacao]
                if len(resultados) > 1:
                    descricao += f" ({len(afetadas)} de {len(resultados)} assinaturas)"
                self._mostrar_faixa(nome_glifo, cor, descricao)
                return
        nomes = ", ".join(r.titular.nome for r in resultados if r.titular)
        self._mostrar_faixa("assinatura_valida", APARENCIA_SITUACAO["valida"][1],
                            f"{plural(len(resultados), 'assinatura válida', 'assinaturas válidas')} · {nomes}")

    def _mostrar_faixa(self, nome_glifo, cor, texto):
        self.icone_faixa.config(text=glifo(nome_glifo), fg=cor)
        self.texto_faixa.config(text=texto)
        if not self.faixa_assinaturas.winfo_ismapped():
            self.faixa_assinaturas.pack(side="top", fill="x", before=self.area)
            self.linha_faixa.pack(side="top", fill="x", before=self.area)

    def _esconder_faixa(self):
        self.faixa_assinaturas.pack_forget()
        self.linha_faixa.pack_forget()

    def _verificar_assinaturas(self, aberto):
        """Verifica o arquivo em disco numa thread; o resultado vai para o DocumentoAberto e para
        todas as janelas que o exibem."""
        if aberto.verificando_assinaturas:
            return
        aberto.verificando_assinaturas = marcador = object()  # outra verificação (após salvar) o substitui
        caminho, senha = aberto.caminho, aberto.senha

        def tarefa():
            with open(caminho, "rb") as arquivo:
                dados = arquivo.read()
            return verificar_assinaturas(dados, senha, certificados_raiz(), certificados_intermediarios())

        def ao_concluir(resultados, erro):
            if aberto.verificando_assinaturas is not marcador or not aberto.documento:
                return  # o arquivo foi salvo ou fechado durante a verificação
            aberto.verificando_assinaturas = None
            aberto.assinaturas, aberto.erro_assinaturas = resultados, (str(erro) or repr(erro)) if erro else None
            for janela in aberto.janelas:
                janela.atualizar_faixa_assinaturas()

        executar_em_segundo_plano(self.aplicativo, tarefa, ao_concluir, INTERVALO_VERIFICACAO_ASSINATURA_MS)

    def mostrar_assinaturas(self):
        if self.aberto and (self.aberto.assinaturas or self.aberto.erro_assinaturas):
            DialogoAssinaturas(self, self.aberto.assinaturas or [], self.aberto.erro_assinaturas)
            self.tela.focus_set()

    def confirmar_salvar_assinado(self):
        """Salvar alterações num PDF assinado faz as assinaturas acusarem a alteração. Retorna
        False se o usuário desistir."""
        if not (self.aberto and self.aberto.assinaturas):
            return True
        resposta = self.perguntar(
            "Documento assinado",
            "Este PDF está assinado digitalmente. Se as alterações forem salvas nele, as assinaturas passarão "
            "a indicar que o documento foi alterado depois de assinado.\n\nPara manter o original intacto, use "
            "“Salvar como” (Ctrl+Shift+S).",
            [("Cancelar", None, False), ("Salvar mesmo assim", "sim", False)], None)
        return resposta == "sim"
