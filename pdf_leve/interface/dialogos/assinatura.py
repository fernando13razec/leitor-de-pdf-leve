"""Diálogos da assinatura digital: escolha do certificado (“Assinar digitalmente”) e detalhes das
assinaturas de um documento."""

import tkinter as tk
from tkinter import ttk

from pdf_leve.configuracao.constantes import INTERVALO_VERIFICACAO_ASSINATURA_MS, URL_CARIMBO_TEMPO_PADRAO
from pdf_leve.configuracao.tema import (
    COR_ALERTA, COR_ATIVO, COR_BARRA, COR_CAMPO, COR_DESTAQUE, COR_LINHA, COR_PERIGO, COR_SUCESSO, COR_TEXTO,
    COR_TEXTO_APAGADO, COR_TEXTO_SUAVE, fonte_icone, fontes, glifo,
)
from pdf_leve.interface.componentes import BotaoPlano
from pdf_leve.interface.utilidades import centralizar, executar_em_segundo_plano
from pdf_leve.servicos.assinatura import apto_para_assinar, descrever_titular
from pdf_leve.sistema.certificados import listar_certificados
from pdf_leve.sistema.windows import barra_titulo_escura

LARGURA_LISTA = 470
ALTURA_LISTA = 210
FORMATO_DIA = "%d/%m/%Y"
FORMATO_DATA_HORA = "%d/%m/%Y às %H:%M:%S"

# situação → (glifo, cor, descrição curta)
APARENCIA_SITUACAO = {
    "valida": ("assinatura_valida", COR_SUCESSO, "Assinatura válida"),
    "nao_confiavel": ("assinatura_alerta", COR_ALERTA,
                      "Assinatura íntegra, mas o certificado não é de uma autoridade confiável neste computador"),
    "alterada": ("assinatura_alerta", COR_ALERTA, "A assinatura confere, mas o documento foi alterado depois dela"),
    "invalida": ("assinatura_invalida", COR_PERIGO, "Assinatura inválida"),
}


def _preparar_janela(janela, mestre, titulo):
    janela.withdraw()
    janela.title(titulo)
    janela.transient(mestre)
    janela.resizable(False, False)


def _mostrar_modal(janela, mestre):
    centralizar(janela, mestre)
    barra_titulo_escura(janela)
    janela.deiconify()
    janela.grab_set()
    janela.focus_force()
    janela.wait_window()


def _campo(mestre, variavel):
    return tk.Entry(mestre, textvariable=variavel, font=fontes.interface, bg=COR_CAMPO, fg=COR_TEXTO,
                    insertbackground=COR_TEXTO, relief="flat", highlightthickness=1,
                    highlightbackground=COR_LINHA, highlightcolor=COR_DESTAQUE)


def _lista_rolavel(mestre, altura):
    """Moldura com barra de rolagem vertical; devolve (moldura, quadro interno, canvas)."""
    moldura = tk.Frame(mestre, bg=COR_CAMPO, highlightthickness=1, highlightbackground=COR_LINHA)
    tela = tk.Canvas(moldura, bg=COR_CAMPO, highlightthickness=0, width=LARGURA_LISTA, height=altura)
    rolagem = ttk.Scrollbar(moldura, orient="vertical", command=tela.yview, style="Escura.Vertical.TScrollbar")
    tela.config(yscrollcommand=rolagem.set)
    tela.pack(side="left", fill="both", expand=True)
    rolagem.pack(side="right", fill="y")
    quadro = tk.Frame(tela, bg=COR_CAMPO)
    tela.create_window(0, 0, window=quadro, anchor="nw", width=LARGURA_LISTA)
    quadro.bind("<Configure>", lambda e: tela.config(scrollregion=(0, 0, LARGURA_LISTA, quadro.winfo_reqheight())))
    tela.bind("<MouseWheel>", lambda e: tela.yview_scroll(-round(e.delta / 120) or 0, "units"))
    return moldura, quadro, tela


def _repassar_roda(widget, tela):
    """A roda do mouse sobre qualquer item da lista rola a lista."""
    widget.bind("<MouseWheel>", lambda e: tela.yview_scroll(-round(e.delta / 120) or 0, "units"))
    for filho in widget.winfo_children():
        _repassar_roda(filho, tela)


def _buscar_certificados():
    """Certificados aptos a assinar, com o titular; os utilizáveis e válidos primeiro."""
    certificados = []
    for certificado in listar_certificados():
        try:
            if not apto_para_assinar(certificado.der):
                continue
            titular = descrever_titular(certificado.der)
        except ValueError:
            continue
        certificados.append((certificado, titular))
    certificados.sort(key=lambda par: (not (par[0].utilizavel and not par[1].vencido()), par[1].nome))
    return certificados


class DialogoAssinatura(tk.Toplevel):
    """Escolha do certificado, motivo, local e carimbo de tempo. Modal. Ao confirmar, `resultado`
    é um dicionário com `certificado` (CertificadoSistema), `motivo`, `local` e
    `url_carimbo_tempo` (None sem carimbo). As escolhas ficam guardadas em `preferencias`."""

    def __init__(self, mestre, preferencias):
        super().__init__(mestre, bg=COR_BARRA)
        _preparar_janela(self, mestre, "Assinar digitalmente")
        self.preferencias = preferencias
        self.resultado = None
        self.certificados, self.linhas, self.escolhido = [], [], None

        corpo = tk.Frame(self, bg=COR_BARRA, padx=22, pady=18)
        corpo.pack(fill="both", expand=True)
        cabecalho = tk.Frame(corpo, bg=COR_BARRA)
        cabecalho.pack(fill="x")
        tk.Label(cabecalho, text="Assinar digitalmente", font=(fontes.interface[0], 14), bg=COR_BARRA,
                 fg=COR_TEXTO).pack(side="left")
        atualizar = tk.Label(cabecalho, text="Atualizar lista", font=fontes.pequena, bg=COR_BARRA, fg=COR_DESTAQUE,
                             cursor="hand2")
        atualizar.pack(side="right")
        atualizar.bind("<Button-1>", lambda e: self.buscar())

        tk.Label(corpo, text="Certificado", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE).pack(
            anchor="w", pady=(16, 6))
        moldura, self.quadro_lista, self.tela_lista = _lista_rolavel(corpo, ALTURA_LISTA)
        moldura.pack(fill="x")

        self.var_motivo = tk.StringVar(value=preferencias.get("assinatura_motivo", ""))
        self.var_local = tk.StringVar(value=preferencias.get("assinatura_local", ""))
        for rotulo, variavel in (("Motivo (opcional)", self.var_motivo), ("Local (opcional)", self.var_local)):
            tk.Label(corpo, text=rotulo, font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE).pack(
                anchor="w", pady=(12, 4))
            _campo(corpo, variavel).pack(fill="x", ipady=5)

        self.var_carimbo = tk.BooleanVar(value=preferencias.get("assinatura_carimbo_tempo", True))
        tk.Checkbutton(corpo, text="Incluir carimbo de tempo (data e hora certificadas; requer internet)",
                       variable=self.var_carimbo, font=fontes.interface, bg=COR_BARRA, fg=COR_TEXTO,
                       activebackground=COR_BARRA, activeforeground=COR_TEXTO, selectcolor=COR_CAMPO,
                       highlightthickness=0, bd=0, command=self._ao_marcar_carimbo).pack(anchor="w", pady=(14, 4))
        self.var_url = tk.StringVar(value=preferencias.get("url_carimbo_tempo", URL_CARIMBO_TEMPO_PADRAO))
        self.campo_url = _campo(corpo, self.var_url)
        self.campo_url.config(font=fontes.pequena)
        self.campo_url.pack(fill="x", ipady=3, padx=(24, 0))
        self._ao_marcar_carimbo()

        self.rotulo_dica = tk.Label(corpo, text="", font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE,
                                    wraplength=LARGURA_LISTA, justify="left")
        self.rotulo_dica.pack(anchor="w", pady=(12, 0))

        botoes = tk.Frame(corpo, bg=COR_BARRA)
        botoes.pack(fill="x", pady=(14, 0))
        BotaoPlano(botoes, "Assinar", self.confirmar, principal=True).pack(side="right")
        BotaoPlano(botoes, "Cancelar", self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda e: self.confirmar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.buscar()
        _mostrar_modal(self, mestre)

    # ------------------------------------------------------------------ lista de certificados
    def _mensagem_na_lista(self, texto):
        for filho in self.quadro_lista.winfo_children():
            filho.destroy()
        tk.Label(self.quadro_lista, text=texto, font=fontes.interface, bg=COR_CAMPO, fg=COR_TEXTO_SUAVE,
                 wraplength=LARGURA_LISTA - 40, justify="left", padx=14, pady=14).pack(anchor="w")

    def buscar(self):
        """Lê os certificados em segundo plano (abrir as chaves de cada token leva alguns segundos)."""
        self.escolhido = None
        self._mensagem_na_lista("Procurando certificados… (conecte o token, se ainda não conectou)")
        executar_em_segundo_plano(self, _buscar_certificados, self._ao_receber_certificados,
                                  INTERVALO_VERIFICACAO_ASSINATURA_MS)

    def _ao_receber_certificados(self, certificados, erro):
        if erro:
            self._mensagem_na_lista(f"Não foi possível ler os certificados do Windows:\n{erro}")
            return
        if not certificados:
            self._mensagem_na_lista("Nenhum certificado digital encontrado. Conecte o token e clique em "
                                    "“Atualizar lista”.")
            return
        for filho in self.quadro_lista.winfo_children():
            filho.destroy()
        self.certificados, self.linhas = certificados, []
        for indice, (certificado, titular) in enumerate(certificados):
            self.linhas.append(self._criar_linha(indice, certificado, titular))
        _repassar_roda(self.quadro_lista, self.tela_lista)
        preferido = self.preferencias.get("assinatura_certificado")
        utilizaveis = [i for i, (c, t) in enumerate(certificados) if c.utilizavel and not t.vencido()]
        escolha = next((i for i in utilizaveis if certificados[i][0].impressao_digital == preferido),
                       utilizaveis[0] if utilizaveis else None)
        if escolha is not None:
            self.escolher(escolha)
        else:
            self.rotulo_dica.config(text="Nenhum certificado pode ser usado agora. Conecte o token e clique em "
                                         "“Atualizar lista”.", fg=COR_PERIGO)

    def _criar_linha(self, indice, certificado, titular):
        disponivel = certificado.utilizavel and not titular.vencido()
        linha = tk.Frame(self.quadro_lista, bg=COR_CAMPO, padx=12, pady=7, cursor="hand2" if disponivel else "")
        linha.pack(fill="x")
        nome = titular.nome + (f"  ·  {titular.tipo_documento} {titular.documento}".rstrip() if titular.documento else "")
        if titular.vencido():
            situacao = f"vencido em {titular.valido_ate.strftime(FORMATO_DIA)}"
        elif not certificado.utilizavel:
            situacao = certificado.motivo
        else:
            situacao = f"válido até {titular.valido_ate.strftime(FORMATO_DIA)}"
        detalhe = f"{titular.emissor}  ·  {situacao}"
        cor_nome = COR_TEXTO if disponivel else COR_TEXTO_APAGADO
        cor_detalhe = COR_TEXTO_SUAVE if disponivel else COR_TEXTO_APAGADO
        tk.Label(linha, text=nome, font=(fontes.interface[0], 10, "bold"), bg=COR_CAMPO, fg=cor_nome,
                 anchor="w").pack(fill="x")
        tk.Label(linha, text=detalhe, font=fontes.pequena, bg=COR_CAMPO, fg=cor_detalhe, anchor="w").pack(fill="x")
        if disponivel:
            for widget in (linha, *linha.winfo_children()):
                widget.bind("<Button-1>", lambda e, i=indice: self.escolher(i))
                widget.bind("<Double-Button-1>", lambda e, i=indice: (self.escolher(i), self.confirmar()))
        return linha

    def escolher(self, indice):
        self.escolhido = indice
        for i, linha in enumerate(self.linhas):
            cor = COR_ATIVO if i == indice else COR_CAMPO
            for widget in (linha, *linha.winfo_children()):
                widget.config(bg=cor)
        self.rotulo_dica.config(text="Ao assinar, o Windows pedirá o PIN do token.", fg=COR_TEXTO_SUAVE)

    # ------------------------------------------------------------------ opções
    def _ao_marcar_carimbo(self):
        self.campo_url.config(state="normal" if self.var_carimbo.get() else "disabled",
                              disabledbackground=COR_BARRA, disabledforeground=COR_TEXTO_APAGADO)

    def confirmar(self):
        if self.escolhido is None:
            self.rotulo_dica.config(text="Escolha um certificado.", fg=COR_PERIGO)
            return
        url = self.var_url.get().strip()
        if self.var_carimbo.get() and not url.lower().startswith(("http://", "https://")):
            self.rotulo_dica.config(text="Informe o endereço (http://…) do servidor de carimbo de tempo.",
                                    fg=COR_PERIGO)
            self.campo_url.focus_set()
            return
        certificado = self.certificados[self.escolhido][0]
        motivo, local = self.var_motivo.get().strip(), self.var_local.get().strip()
        self.preferencias.update(assinatura_certificado=certificado.impressao_digital, assinatura_motivo=motivo,
                                 assinatura_local=local, assinatura_carimbo_tempo=self.var_carimbo.get(),
                                 url_carimbo_tempo=url or URL_CARIMBO_TEMPO_PADRAO)
        self.resultado = {"certificado": certificado, "motivo": motivo, "local": local,
                          "url_carimbo_tempo": url if self.var_carimbo.get() else None}
        self.destroy()


class DialogoAssinaturas(tk.Toplevel):
    """Detalhes das assinaturas do documento (lista de ResultadoAssinatura). Modal."""

    def __init__(self, mestre, resultados, erro=None):
        super().__init__(mestre, bg=COR_BARRA)
        _preparar_janela(self, mestre, "Assinaturas do documento")
        corpo = tk.Frame(self, bg=COR_BARRA, padx=22, pady=18)
        corpo.pack(fill="both", expand=True)
        tk.Label(corpo, text="Assinaturas do documento", font=(fontes.interface[0], 14), bg=COR_BARRA,
                 fg=COR_TEXTO).pack(anchor="w")
        if erro:
            tk.Label(corpo, text=f"Não foi possível verificar as assinaturas:\n{erro}", font=fontes.interface,
                     bg=COR_BARRA, fg=COR_PERIGO, wraplength=LARGURA_LISTA, justify="left").pack(anchor="w", pady=12)
        else:
            altura = min(ALTURA_LISTA * 2, 110 * len(resultados))
            moldura, quadro, tela = _lista_rolavel(corpo, altura)
            moldura.pack(fill="x", pady=(14, 0))
            for resultado in resultados:
                self._criar_item(quadro, resultado)
            _repassar_roda(quadro, tela)
            tk.Label(corpo, text="A confiança é verificada com as autoridades certificadoras instaladas no Windows; "
                                 "a revogação dos certificados não é consultada.",
                     font=fontes.pequena, bg=COR_BARRA, fg=COR_TEXTO_SUAVE, wraplength=LARGURA_LISTA,
                     justify="left").pack(anchor="w", pady=(10, 0))
        botoes = tk.Frame(corpo, bg=COR_BARRA)
        botoes.pack(fill="x", pady=(16, 0))
        BotaoPlano(botoes, "Fechar", self.destroy, principal=True).pack(side="right")
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _mostrar_modal(self, mestre)

    @staticmethod
    def _criar_item(quadro, resultado):
        nome_glifo, cor, descricao = APARENCIA_SITUACAO[resultado.situacao]
        item = tk.Frame(quadro, bg=COR_CAMPO, padx=12, pady=10)
        item.pack(fill="x")
        tk.Label(item, text=glifo(nome_glifo), font=fonte_icone(16), bg=COR_CAMPO, fg=cor).pack(
            side="left", anchor="n", padx=(0, 10))
        textos = tk.Frame(item, bg=COR_CAMPO)
        textos.pack(side="left", fill="x", expand=True)
        titular = resultado.titular
        nome = titular.nome if titular else resultado.campo
        if titular and titular.documento:
            nome += f"  ·  {titular.tipo_documento} {titular.documento}"
        tk.Label(textos, text=nome, font=(fontes.interface[0], 10, "bold"), bg=COR_CAMPO, fg=COR_TEXTO,
                 anchor="w", justify="left", wraplength=LARGURA_LISTA - 70).pack(fill="x")
        linhas = [descricao]
        if resultado.data:
            origem = "carimbo de tempo" if resultado.data_do_carimbo else "relógio do computador de quem assinou"
            linhas.append(f"Assinado em {resultado.data.astimezone().strftime(FORMATO_DATA_HORA)} ({origem})")
        if titular:
            linhas.append(f"Certificado emitido por {titular.emissor}")
        if resultado.alteracoes:
            linhas.append(resultado.alteracoes[0].upper() + resultado.alteracoes[1:])
        if resultado.erro:
            linhas.append(resultado.erro)
        tk.Label(textos, text="\n".join(linhas), font=fontes.pequena, bg=COR_CAMPO, fg=COR_TEXTO_SUAVE,
                 anchor="w", justify="left", wraplength=LARGURA_LISTA - 70).pack(fill="x", pady=(2, 0))
