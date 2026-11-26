"""Certificados digitais do Windows via ctypes (crypt32 e ncrypt), sem dependências externas.

Os certificados vêm do repositório “Pessoal” (CurrentUser\\My), onde o Windows registra os
certificados de tokens e cartões A3 (minidriver). A chave privada nunca sai do token: o hash é
enviado ao provedor (CNG), que pede o PIN na própria janela do Windows e devolve a assinatura.

Como no pdfcraft, a listagem abre as chaves em modo silencioso (sem pedir PIN) só para saber se
podem ser usadas; o PIN só é pedido na hora de assinar.
"""

import ctypes
import hashlib
from ctypes import wintypes
from dataclasses import dataclass

from pdf_leve.sistema.windows import NO_WINDOWS

# wincrypt.h
_CODIFICACAO = 0x00010001                    # X509_ASN_ENCODING | PKCS_7_ASN_ENCODING
_CERT_FIND_SHA1_HASH = 0x10000
_CRYPT_ACQUIRE_CACHE_FLAG = 0x1
_CRYPT_ACQUIRE_SILENT_FLAG = 0x40
_CRYPT_ACQUIRE_WINDOW_HANDLE_FLAG = 0x80
_CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG = 0x40000
_CERT_NCRYPT_KEY_SPEC = 0xFFFFFFFF
_CERT_CHAIN_REVOCATION_CHECK_CACHE_ONLY = 0x80000000

# ncrypt.h / bcrypt.h
_BCRYPT_PAD_PKCS1 = 0x2
_NCRYPT_ALGORITMO_GRUPO = "Algorithm Group"   # NCRYPT_ALGORITHM_GROUP_PROPERTY
_NCRYPT_JANELA = "HWND Handle"                # NCRYPT_WINDOW_HANDLE_PROPERTY

# Códigos de erro (HRESULT / SECURITY_STATUS) que interessam ao usuário.
NTE_SILENT_CONTEXT = 0x80090022
NTE_BAD_KEYSET = 0x80090016
NTE_NO_KEY = 0x8009000D
NTE_USER_CANCELLED = 0x80090036
NTE_INCORRECT_PASSWORD = 0x80090027
CRYPT_E_NO_KEY_PROPERTY = 0x8009200B
CRYPT_E_NOT_FOUND = 0x80092004
ERROR_CANCELLED = 0x800704C7
SCARD_W_WRONG_CHV = 0x8010006B
SCARD_W_CHV_BLOCKED = 0x8010006C
SCARD_W_CANCELLED_BY_USER = 0x8010006E
SCARD_E_NO_SMARTCARD = 0x8010000C
SCARD_W_REMOVED_CARD = 0x80100069
STATUS_NOT_FOUND = 0xC0000225  # o provedor de cartão inteligente não acha o token

MENSAGEM_TOKEN_AUSENTE = "o token não está conectado"

MENSAGENS_ERRO = {
    NTE_SILENT_CONTEXT: "o token precisa do PIN",
    NTE_BAD_KEYSET: "a chave privada não foi encontrada (o token está conectado?)",
    NTE_NO_KEY: "a chave privada não foi encontrada (o token está conectado?)",
    NTE_USER_CANCELLED: "operação cancelada",
    NTE_INCORRECT_PASSWORD: "PIN incorreto",
    CRYPT_E_NO_KEY_PROPERTY: "o certificado não tem chave privada neste computador",
    CRYPT_E_NOT_FOUND: "o certificado não está mais no repositório do Windows",
    ERROR_CANCELLED: "operação cancelada",
    SCARD_W_WRONG_CHV: "PIN incorreto",
    SCARD_W_CHV_BLOCKED: "o PIN do token está bloqueado",
    SCARD_W_CANCELLED_BY_USER: "operação cancelada",
    SCARD_E_NO_SMARTCARD: MENSAGEM_TOKEN_AUSENTE,
    SCARD_W_REMOVED_CARD: "o token foi removido",
    STATUS_NOT_FOUND: MENSAGEM_TOKEN_AUSENTE,
}
CODIGOS_CANCELAMENTO = {NTE_USER_CANCELLED, ERROR_CANCELLED, SCARD_W_CANCELLED_BY_USER}


class ErroCertificado(OSError):
    """Erro do Windows ao usar um certificado; `codigo` é o HRESULT (sem sinal)."""

    def __init__(self, codigo, operacao=""):
        self.codigo = codigo & 0xFFFFFFFF
        self.cancelado = self.codigo in CODIGOS_CANCELAMENTO
        super().__init__(descrever_erro(self.codigo, operacao))


def descrever_erro(codigo, operacao=""):
    """Mensagem em português para um código de erro do CNG/CryptoAPI/cartão inteligente."""
    codigo &= 0xFFFFFFFF
    mensagem = MENSAGENS_ERRO.get(codigo)
    if mensagem is None and 0x80100000 <= codigo <= 0x8010FFFF:
        mensagem = MENSAGEM_TOKEN_AUSENTE
    if mensagem is None:
        mensagem = f"erro 0x{codigo:08X}"
    return f"{operacao}: {mensagem}" if operacao else mensagem[0].upper() + mensagem[1:]


@dataclass
class CertificadoSistema:
    """Certificado do repositório do Windows. `utilizavel` diz se a chave privada pode ser usada
    agora (token conectado); senão, `motivo` explica por quê."""

    der: bytes
    impressao_digital: str  # SHA-1 em hexadecimal, como no Windows
    utilizavel: bool
    motivo: str = ""


class _Blob(ctypes.Structure):  # CRYPT_INTEGER_BLOB / CRYPT_HASH_BLOB
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


class _ContextoCertificado(ctypes.Structure):  # CERT_CONTEXT
    _fields_ = [
        ("dwCertEncodingType", wintypes.DWORD),
        ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
        ("cbCertEncoded", wintypes.DWORD),
        ("pCertInfo", ctypes.c_void_p),
        ("hCertStore", ctypes.c_void_p),
    ]


_PContexto = ctypes.POINTER(_ContextoCertificado)


class _UsoAprimorado(ctypes.Structure):  # CERT_ENHKEY_USAGE
    _fields_ = [("cUsageIdentifier", wintypes.DWORD), ("rgpszUsageIdentifier", ctypes.c_void_p)]


class _UsoCadeia(ctypes.Structure):  # CERT_USAGE_MATCH
    _fields_ = [("dwType", wintypes.DWORD), ("Usage", _UsoAprimorado)]


class _ParametrosCadeia(ctypes.Structure):  # CERT_CHAIN_PARA
    _fields_ = [("cbSize", wintypes.DWORD), ("RequestedUsage", _UsoCadeia)]


class _SituacaoConfianca(ctypes.Structure):  # CERT_TRUST_STATUS
    _fields_ = [("dwErrorStatus", wintypes.DWORD), ("dwInfoStatus", wintypes.DWORD)]


class _ElementoCadeia(ctypes.Structure):  # CERT_CHAIN_ELEMENT (só o começo)
    _fields_ = [("cbSize", wintypes.DWORD), ("pCertContext", _PContexto), ("TrustStatus", _SituacaoConfianca)]


class _CadeiaSimples(ctypes.Structure):  # CERT_SIMPLE_CHAIN (só o começo)
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("TrustStatus", _SituacaoConfianca),
        ("cElement", wintypes.DWORD),
        ("rgpElement", ctypes.POINTER(ctypes.POINTER(_ElementoCadeia))),
    ]


class _ContextoCadeia(ctypes.Structure):  # CERT_CHAIN_CONTEXT (só o começo)
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("TrustStatus", _SituacaoConfianca),
        ("cChain", wintypes.DWORD),
        ("rgpChain", ctypes.POINTER(ctypes.POINTER(_CadeiaSimples))),
    ]


class _InformacaoPreenchimento(ctypes.Structure):  # BCRYPT_PKCS1_PADDING_INFO
    _fields_ = [("pszAlgId", wintypes.LPCWSTR)]


ALGORITMOS_HASH = {"sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512"}

_bibliotecas = None


def _carregar():
    """crypt32 e ncrypt com os tipos declarados (carregadas na primeira chamada)."""
    global _bibliotecas
    if _bibliotecas:
        return _bibliotecas
    crypt32, ncrypt = ctypes.WinDLL("crypt32", use_last_error=True), ctypes.WinDLL("ncrypt")
    crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
    crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    crypt32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, _PContexto]
    crypt32.CertEnumCertificatesInStore.restype = _PContexto
    crypt32.CertFindCertificateInStore.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                                   ctypes.c_void_p, _PContexto]
    crypt32.CertFindCertificateInStore.restype = _PContexto
    crypt32.CertFreeCertificateContext.argtypes = [_PContexto]
    crypt32.CertCreateCertificateContext.argtypes = [wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD]
    crypt32.CertCreateCertificateContext.restype = _PContexto
    crypt32.CryptAcquireCertificatePrivateKey.argtypes = [
        _PContexto, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.BOOL)]
    crypt32.CryptAcquireCertificatePrivateKey.restype = wintypes.BOOL
    crypt32.CertGetCertificateChain.argtypes = [
        ctypes.c_void_p, _PContexto, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_ParametrosCadeia),
        wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(_ContextoCadeia))]
    crypt32.CertGetCertificateChain.restype = wintypes.BOOL
    crypt32.CertFreeCertificateChain.argtypes = [ctypes.POINTER(_ContextoCadeia)]
    ncrypt.NCryptSignHash.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    ncrypt.NCryptSignHash.restype = wintypes.LONG
    ncrypt.NCryptSetProperty.argtypes = [ctypes.c_size_t, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD,
                                         wintypes.DWORD]
    ncrypt.NCryptSetProperty.restype = wintypes.LONG
    ncrypt.NCryptGetProperty.argtypes = [ctypes.c_size_t, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    ncrypt.NCryptGetProperty.restype = wintypes.LONG
    ncrypt.NCryptFreeObject.argtypes = [ctypes.c_size_t]
    ncrypt.NCryptFreeObject.restype = wintypes.LONG
    _bibliotecas = crypt32, ncrypt
    return _bibliotecas


def _der(contexto):
    return ctypes.string_at(contexto.contents.pbCertEncoded, contexto.contents.cbCertEncoded)


def _ultimo_erro():
    return ctypes.get_last_error() & 0xFFFFFFFF


def _ler_repositorio(nome):
    """DER de todos os certificados de um repositório do usuário (“MY”, “ROOT”, “CA”)."""
    crypt32, _ = _carregar()
    repositorio = crypt32.CertOpenSystemStoreW(None, nome)
    if not repositorio:
        return []
    certificados, contexto = [], None
    try:
        while True:
            contexto = crypt32.CertEnumCertificatesInStore(repositorio, contexto)
            if not contexto:
                break
            certificados.append(_der(contexto))
    finally:
        crypt32.CertCloseStore(repositorio, 0)
    return certificados


def _abrir_chave(contexto, silencioso, hwnd=None):
    """Handle NCrypt da chave privada do certificado: (handle, liberar?). Lança ErroCertificado."""
    crypt32, _ = _carregar()
    opcoes = _CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG | _CRYPT_ACQUIRE_CACHE_FLAG
    parametro = None
    if silencioso:
        opcoes |= _CRYPT_ACQUIRE_SILENT_FLAG
    elif hwnd:
        opcoes |= _CRYPT_ACQUIRE_WINDOW_HANDLE_FLAG
        janela = ctypes.c_void_p(hwnd)
        parametro = ctypes.byref(janela)
    chave, tipo, liberar = ctypes.c_size_t(), wintypes.DWORD(), wintypes.BOOL()
    if not crypt32.CryptAcquireCertificatePrivateKey(contexto, opcoes, parametro, ctypes.byref(chave),
                                                     ctypes.byref(tipo), ctypes.byref(liberar)):
        raise ErroCertificado(_ultimo_erro())
    if tipo.value != _CERT_NCRYPT_KEY_SPEC:  # não deveria acontecer com ONLY_NCRYPT
        raise ErroCertificado(NTE_NO_KEY)
    return chave.value, bool(liberar.value)


def listar_certificados():
    """Certificados do repositório “Pessoal” com chave privada, informando se podem ser usados
    agora. Os que não têm chave privada neste computador ficam de fora."""
    if not NO_WINDOWS:
        return []
    crypt32, ncrypt = _carregar()
    repositorio = crypt32.CertOpenSystemStoreW(None, "MY")
    if not repositorio:
        return []
    certificados, contexto = [], None
    try:
        while True:
            contexto = crypt32.CertEnumCertificatesInStore(repositorio, contexto)
            if not contexto:
                break
            der = _der(contexto)
            impressao = hashlib.sha1(der).hexdigest().upper()
            try:
                chave, liberar = _abrir_chave(contexto, silencioso=True)
                if liberar:
                    ncrypt.NCryptFreeObject(chave)
                certificados.append(CertificadoSistema(der, impressao, True))
            except ErroCertificado as erro:
                if erro.codigo == CRYPT_E_NO_KEY_PROPERTY:
                    continue
                if erro.codigo == NTE_SILENT_CONTEXT:  # o PIN será pedido ao assinar
                    certificados.append(CertificadoSistema(der, impressao, True))
                else:
                    certificados.append(CertificadoSistema(der, impressao, False, descrever_erro(erro.codigo)))
    finally:
        crypt32.CertCloseStore(repositorio, 0)
    return certificados


def certificados_raiz():
    """Raízes confiáveis do Windows (inclui a ICP-Brasil, quando instalada)."""
    return _ler_repositorio("ROOT") if NO_WINDOWS else []


def certificados_intermediarios():
    """Autoridades intermediárias conhecidas pelo Windows (ajudam a montar as cadeias)."""
    return _ler_repositorio("CA") if NO_WINDOWS else []


def cadeia_certificado(der):
    """Cadeia do certificado montada pelo Windows, do emissor até a raiz (sem o próprio certificado)."""
    if not NO_WINDOWS:
        return []
    crypt32, _ = _carregar()
    contexto = crypt32.CertCreateCertificateContext(_CODIFICACAO, der, len(der))
    if not contexto:
        return []
    parametros = _ParametrosCadeia(cbSize=ctypes.sizeof(_ParametrosCadeia))
    cadeia = ctypes.POINTER(_ContextoCadeia)()
    try:
        if not crypt32.CertGetCertificateChain(None, contexto, None, None, ctypes.byref(parametros),
                                               _CERT_CHAIN_REVOCATION_CHECK_CACHE_ONLY, None,
                                               ctypes.byref(cadeia)):
            return []
        try:
            if not cadeia.contents.cChain:
                return []
            simples = cadeia.contents.rgpChain[0].contents
            return [_der(simples.rgpElement[i].contents.pCertContext) for i in range(1, simples.cElement)]
        finally:
            crypt32.CertFreeCertificateChain(cadeia)
    finally:
        crypt32.CertFreeCertificateContext(contexto)


def assinar_hash(impressao_digital, hash_, algoritmo, hwnd=None):
    """Assina `hash_` com a chave do certificado `impressao_digital` (SHA-1 hexadecimal).

    O provedor do token pede o PIN numa janela do Windows (com `hwnd` como dona). Chamar fora da
    thread do Tk: a chamada só volta depois que o usuário digita o PIN. RSA usa PKCS#1 v1.5;
    ECDSA devolve a assinatura em DER, como o CMS exige."""
    if not NO_WINDOWS:
        raise OSError("A assinatura com certificado do Windows só funciona no Windows.")
    crypt32, ncrypt = _carregar()
    repositorio = crypt32.CertOpenSystemStoreW(None, "MY")
    if not repositorio:
        raise ErroCertificado(_ultimo_erro(), "Repositório de certificados")
    try:
        sha1 = bytes.fromhex(impressao_digital)
        memoria = (ctypes.c_ubyte * len(sha1)).from_buffer_copy(sha1)
        blob = _Blob(len(sha1), memoria)
        contexto = crypt32.CertFindCertificateInStore(repositorio, _CODIFICACAO, 0, _CERT_FIND_SHA1_HASH,
                                                      ctypes.byref(blob), None)
        if not contexto:
            raise ErroCertificado(CRYPT_E_NOT_FOUND)
        try:
            chave, liberar = _abrir_chave(contexto, silencioso=False, hwnd=hwnd)
            try:
                return _assinar_com_chave(ncrypt, chave, hash_, algoritmo, hwnd)
            finally:
                if liberar:
                    ncrypt.NCryptFreeObject(chave)
        finally:
            crypt32.CertFreeCertificateContext(contexto)
    finally:
        crypt32.CertCloseStore(repositorio, 0)


def _grupo_algoritmo(ncrypt, chave):
    """“RSA” ou “ECDSA”."""
    memoria, tamanho = ctypes.create_string_buffer(64), wintypes.DWORD()
    if ncrypt.NCryptGetProperty(chave, _NCRYPT_ALGORITMO_GRUPO, memoria, 64, ctypes.byref(tamanho), 0):
        return "RSA"
    return memoria.raw[:tamanho.value].decode("utf-16-le").rstrip("\0")


def _assinar_com_chave(ncrypt, chave, hash_, algoritmo, hwnd):
    if hwnd:
        janela = ctypes.c_void_p(hwnd)
        ncrypt.NCryptSetProperty(chave, _NCRYPT_JANELA, ctypes.byref(janela), ctypes.sizeof(janela), 0)
    if _grupo_algoritmo(ncrypt, chave) == "RSA":
        preenchimento = _InformacaoPreenchimento(ALGORITMOS_HASH[algoritmo])
        informacao, opcoes = ctypes.byref(preenchimento), _BCRYPT_PAD_PKCS1
    else:
        informacao, opcoes = None, 0
    tamanho = wintypes.DWORD()
    situacao = ncrypt.NCryptSignHash(chave, informacao, hash_, len(hash_), None, 0, ctypes.byref(tamanho), opcoes)
    if situacao:
        raise ErroCertificado(situacao, "Assinatura")
    assinatura = ctypes.create_string_buffer(tamanho.value)
    situacao = ncrypt.NCryptSignHash(chave, informacao, hash_, len(hash_), assinatura, tamanho,
                                     ctypes.byref(tamanho), opcoes)
    if situacao:
        raise ErroCertificado(situacao, "Assinatura")
    bruta = assinatura.raw[:tamanho.value]
    return bruta if informacao is not None else _ecdsa_para_der(bruta)


def _ecdsa_para_der(bruta):
    """Assinatura ECDSA do CNG (r‖s) convertida para a sequência DER usada no CMS."""
    from asn1crypto.algos import DSASignature  # dependência do pyHanko
    return DSASignature.from_p1363(bruta).dump()
