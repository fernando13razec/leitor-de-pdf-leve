"""Assinatura digital de PDF (PAdES) e verificação das assinaturas existentes, com o pyHanko.

A chave privada não passa por aqui: quem assina o hash é uma função recebida de fora
(`AssinanteExterno`). No programa, ela é `sistema.certificados.assinar_hash`, que usa o token pelo
Windows; nos testes, uma chave em memória. Por isso este módulo não depende do Windows nem do Tk.

A lógica segue a do pdfcraft: assinatura destacada CAdES (`/SubFilter /ETSI.CAdES.detached`),
SHA-256, campo novo com aparência visível no retângulo escolhido, salvamento incremental (o arquivo
original fica intacto dentro do assinado) e, opcionalmente, carimbo de tempo RFC 3161 (PAdES-B-T).
"""

import hashlib
import io
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import pymupdf
from asn1crypto import x509
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.sign.validation.settings import KeyUsageConstraints
from pyhanko.sign.validation.status import SignatureCoverageLevel
from pyhanko.sign.diff_analysis import ModificationLevel
from pyhanko.sign.timestamps.common_utils import TimestampRequestError as ErroCarimboTempo
from pyhanko.stamp import TextStampStyle
from pyhanko.pdf_utils.text import TextBoxStyle
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.registry import SimpleCertificateStore

from pdf_leve.configuracao.constantes import (
    ALGORITMO_HASH_ASSINATURA, PREFIXO_CAMPO_ASSINATURA, SUFIXO_ARQUIVO_ASSINADO, TAMANHO_FONTE_SELO,
    TEMPO_LIMITE_CARIMBO_TEMPO_S,
)

__all__ = [
    "AssinanteExterno", "ErroCarimboTempo", "OpcoesAssinatura", "ResultadoAssinatura", "Titular",
    "apto_para_assinar", "assinar_pdf", "converter_retangulo", "descrever_titular", "formatar_documento",
    "nome_arquivo_assinado", "possui_assinaturas", "texto_selo", "verificar_assinaturas",
]

FORMATO_DATA = "%d/%m/%Y %H:%M:%S"
# Uso de chave aceito na verificação: qualquer um dos dois (o pyHanko exige só “não repúdio”).
USO_CHAVE_ASSINATURA = KeyUsageConstraints(key_usage={"digital_signature", "non_repudiation"},
                                           match_all_key_usages=False)


# ------------------------------------------------------------------ titular do certificado
@dataclass
class Titular:
    nome: str
    documento: str        # CPF ou CNPJ formatado (vazio se o certificado não trouxer)
    emissor: str
    valido_de: datetime
    valido_ate: datetime

    def vencido(self, agora=None):
        agora = agora or datetime.now(timezone.utc)
        return not self.valido_de <= agora <= self.valido_ate

    @property
    def tipo_documento(self):
        return {11: "CPF", 14: "CNPJ"}.get(len(re.sub(r"\D", "", self.documento)), "")


def formatar_documento(numeros):
    """CPF (11 dígitos) ou CNPJ (14) com a pontuação usual; outros valores ficam como estão."""
    if re.fullmatch(r"\d{11}", numeros):
        return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"
    if re.fullmatch(r"\d{14}", numeros):
        return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
    return numeros


def descrever_titular(certificado):
    """Titular de um certificado (DER ou asn1crypto). Nos certificados ICP-Brasil o nome comum é
    “NOME:CPF” (e-CPF) ou “RAZÃO SOCIAL:CNPJ” (e-CNPJ)."""
    if isinstance(certificado, bytes):
        certificado = x509.Certificate.load(certificado)
    nome_comum = certificado.subject.native.get("common_name") or certificado.subject.human_friendly
    if isinstance(nome_comum, list):
        nome_comum = nome_comum[-1]
    nome, documento = nome_comum, ""
    partes = re.fullmatch(r"(.*?)\s*:\s*(\d{11}|\d{14})", nome_comum)
    if partes:
        nome, documento = partes.group(1), formatar_documento(partes.group(2))
    emissor = certificado.issuer.native.get("common_name") or certificado.issuer.human_friendly
    validade = certificado["tbs_certificate"]["validity"]
    return Titular(nome, documento, emissor, validade["not_before"].native, validade["not_after"].native)


def apto_para_assinar(der):
    """O certificado serve para assinar documentos: não é autoassinado (certificados internos do
    Windows) e, se declara o uso da chave, permite assinatura digital ou não repúdio."""
    certificado = x509.Certificate.load(der)
    if certificado.self_signed != "no":
        return False
    uso = certificado.key_usage_value
    return uso is None or bool(uso.native & {"digital_signature", "non_repudiation"})


# ------------------------------------------------------------------ assinar
class AssinanteExterno(signers.Signer):
    """Signer do pyHanko cuja chave fica fora do programa (no token).

    `assinar_hash(hash, algoritmo)` recebe o hash já calculado (ex.: 32 bytes de SHA-256) e devolve
    a assinatura bruta: PKCS#1 v1.5 para RSA, DER para ECDSA."""

    def __init__(self, certificado_der, cadeia_der, assinar_hash):
        certificado = x509.Certificate.load(certificado_der)
        cadeia = [x509.Certificate.load(der) for der in cadeia_der]
        super().__init__(signing_cert=certificado,
                         cert_registry=SimpleCertificateStore.from_certs([certificado] + cadeia))
        self.assinar_hash = assinar_hash

    async def async_sign_raw(self, data, digest_algorithm, dry_run=False):
        if dry_run:  # só para estimar o espaço reservado no PDF: não usa o token
            bytes_chave = (self.signing_cert.public_key.bit_size + 7) // 8
            return bytes(bytes_chave if self.signing_cert.public_key.algorithm == "rsa" else 2 * bytes_chave + 9)
        return self.assinar_hash(hashlib.new(digest_algorithm, data).digest(), digest_algorithm)


@dataclass
class OpcoesAssinatura:
    pagina: int
    retangulo: tuple       # (x0, y0, x1, y1) em coordenadas do PDF (origem embaixo), ver converter_retangulo
    motivo: str = ""
    local: str = ""
    url_carimbo_tempo: str | None = None
    senha: str | None = None


def nome_arquivo_assinado(caminho):
    """“contrato.pdf” → “contrato_assinado.pdf” (na mesma pasta)."""
    base, extensao = os.path.splitext(caminho)
    return base + SUFIXO_ARQUIVO_ASSINADO + (extensao or ".pdf")


def converter_retangulo(pagina, retangulo):
    """Retângulo como exibido pelo PyMuPDF (origem no topo, página já girada) convertido para o
    espaço do PDF, que o campo de assinatura usa. Volta (x0, y0, x1, y1) com x0 < x1 e y0 < y1."""
    convertido = pymupdf.Rect(retangulo) * pagina.derotation_matrix * ~pagina.transformation_matrix
    convertido.normalize()
    return (round(convertido.x0, 2), round(convertido.y0, 2), round(convertido.x1, 2), round(convertido.y1, 2))


def texto_selo(titular):
    """Texto do selo visível; `%(ts)s` vira a data e hora da assinatura."""
    linhas = ["Assinado digitalmente por", titular.nome.replace("%", "%%")]
    if titular.documento:
        linhas.append(f"{titular.tipo_documento}: {titular.documento}".strip(": "))
    linhas.append("Data: %(ts)s")
    return "\n".join(linhas)


def _nome_campo_livre(leitor):
    usados = {nome for nome, _, _ in fields.enumerate_sig_fields(leitor)}
    numero = 1
    while f"{PREFIXO_CAMPO_ASSINATURA}{numero}" in usados:
        numero += 1
    return f"{PREFIXO_CAMPO_ASSINATURA}{numero}"


def assinar_pdf(origem, destino, assinante, opcoes, carimbador=None):
    """Assina o PDF `origem` e grava o resultado em `destino` (que não pode ser a origem).

    `carimbador` substitui o servidor de carimbo de tempo (usado nos testes). Erros do token, da
    rede ou do PDF são repassados a quem chamou; nesse caso, `destino` não é criado."""
    if os.path.abspath(origem) == os.path.abspath(destino):
        raise ValueError("O arquivo assinado precisa ser diferente do original.")
    with open(origem, "rb") as arquivo:
        dados = arquivo.read()
    escritor = IncrementalPdfFileWriter(io.BytesIO(dados), strict=False)
    if escritor.prev.encrypted:
        escritor.encrypt(opcoes.senha or "")
        if not hasattr(escritor._encrypt, "idnum"):
            # O PyMuPDF grava /Encrypt como objeto direto no trailer, e o pyHanko só espera uma
            # referência (usa o número do objeto para não criptografá-lo): nenhum objeto novo é ele.
            escritor._encrypt.idnum = None
    nome_campo = _nome_campo_livre(escritor.prev)
    if carimbador is None and opcoes.url_carimbo_tempo:
        from pyhanko.sign.timestamps.requests_client import RequestsHTTPTimeStamper
        carimbador = RequestsHTTPTimeStamper(opcoes.url_carimbo_tempo, timeout=TEMPO_LIMITE_CARIMBO_TEMPO_S)
    metadados = signers.PdfSignatureMetadata(
        field_name=nome_campo, subfilter=fields.SigSeedSubFilter.PADES, md_algorithm=ALGORITMO_HASH_ASSINATURA,
        reason=opcoes.motivo or None, location=opcoes.local or None)
    estilo = TextStampStyle(stamp_text=texto_selo(descrever_titular(assinante.signing_cert)),
                            timestamp_format=FORMATO_DATA, border_width=1,
                            text_box_style=TextBoxStyle(font_size=TAMANHO_FONTE_SELO))
    assinador = signers.PdfSigner(
        metadados, assinante, timestamper=carimbador, stamp_style=estilo,
        new_field_spec=fields.SigFieldSpec(nome_campo, on_page=opcoes.pagina, box=opcoes.retangulo))
    temporario = destino + ".tmp"
    try:
        with open(temporario, "wb") as arquivo:
            assinador.sign_pdf(escritor, output=arquivo)
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)


# ------------------------------------------------------------------ verificar
@dataclass
class ResultadoAssinatura:
    campo: str
    titular: Titular | None
    data: datetime | None
    data_do_carimbo: bool       # a data vem de um carimbo de tempo (e não do relógio de quem assinou)
    integra: bool               # o conteúdo assinado não foi alterado e a assinatura confere
    confiavel: bool             # a cadeia chega a uma raiz confiável
    alteracoes: str = ""        # o que mudou no arquivo depois desta assinatura (vazio: nada)
    alterado_depois: bool = False  # mudanças posteriores que uma assinatura não admite
    erro: str = ""

    @property
    def situacao(self):
        """“valida”; “nao_confiavel” (íntegra, mas o emissor não é reconhecido); “alterada” (a
        assinatura confere, mas o documento foi modificado depois dela) ou “invalida”."""
        if not self.integra:
            return "invalida"
        if self.alterado_depois:
            return "alterada"
        return "valida" if self.confiavel else "nao_confiavel"


def possui_assinaturas(documento):
    """Verificação rápida (PyMuPDF): o PDF declara ter assinaturas (/SigFlags)."""
    try:
        return documento.get_sigflags() > 0
    except Exception:
        return False


def _descrever_alteracoes(status):
    if status.coverage == SignatureCoverageLevel.ENTIRE_FILE:
        return ""
    nivel = status.modification_level
    if nivel in (None, ModificationLevel.NONE, ModificationLevel.LTA_UPDATES):
        return ""
    if nivel == ModificationLevel.FORM_FILLING:
        return "o documento recebeu outras assinaturas ou preenchimento de formulário depois desta"
    if nivel == ModificationLevel.ANNOTATIONS:
        return "o documento recebeu anotações depois desta assinatura"
    return "o documento foi alterado depois desta assinatura"


def verificar_assinaturas(dados, senha=None, raizes=(), intermediarios=(), consultar_revogacao=False):
    """Verifica todas as assinaturas do PDF (bytes). `raizes` e `intermediarios` são certificados
    DER (no programa, os do Windows). Sem `consultar_revogacao`, não acessa a internet."""
    leitor = PdfFileReader(io.BytesIO(dados), strict=False)
    if leitor.encrypted:
        leitor.decrypt(senha or "")
    contexto = ValidationContext(
        trust_roots=[x509.Certificate.load(der) for der in raizes],
        other_certs=[x509.Certificate.load(der) for der in intermediarios],
        allow_fetching=consultar_revogacao, revocation_mode="soft-fail")
    resultados = []
    for assinatura in leitor.embedded_signatures:
        try:
            status = validate_pdf_signature(assinatura, contexto, key_usage_settings=USO_CHAVE_ASSINATURA)
        except Exception as erro:
            resultados.append(ResultadoAssinatura(assinatura.field_name, None, None, False, False, False,
                                                  erro=str(erro) or erro.__class__.__name__))
            continue
        carimbo = status.timestamp_validity
        data_do_carimbo = carimbo is not None and carimbo.intact and carimbo.valid
        data = carimbo.timestamp if data_do_carimbo else status.signer_reported_dt
        alteracoes = _descrever_alteracoes(status)
        integra = status.intact and status.valid
        resultados.append(ResultadoAssinatura(
            campo=assinatura.field_name, titular=descrever_titular(status.signing_cert), data=data,
            data_do_carimbo=data_do_carimbo, integra=integra, confiavel=integra and status.trusted,
            alteracoes=alteracoes,
            alterado_depois=status.docmdp_ok is False or status.modification_level == ModificationLevel.OTHER))
    return resultados
