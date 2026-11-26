"""Testes da assinatura digital (sem token e sem Tk): chaves e certificados de teste gerados aqui."""

import datetime
import logging
import os
import tempfile
import unittest

import pymupdf
from asn1crypto import keys as chaves_asn1
from asn1crypto import x509 as x509_asn1
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper

from pdf_leve.servicos.assinatura import (
    AssinanteExterno, OpcoesAssinatura, apto_para_assinar, assinar_pdf, converter_retangulo, descrever_titular, formatar_documento,
    nome_arquivo_assinado, possui_assinaturas, texto_selo, verificar_assinaturas,
)

ALGORITMOS = {"sha256": hashes.SHA256(), "sha384": hashes.SHA384(), "sha512": hashes.SHA512()}
logging.getLogger("pyhanko").setLevel(logging.CRITICAL)  # falhas esperadas de validação poluem a saída


def _nome(texto):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, texto)])


def _certificado(sujeito, chave_publica, emissor, chave_emissor, ac=False, uso_estendido=None):
    agora = datetime.datetime.now(datetime.timezone.utc)
    construtor = (x509.CertificateBuilder().subject_name(_nome(sujeito)).issuer_name(_nome(emissor))
                  .public_key(chave_publica).serial_number(x509.random_serial_number())
                  .not_valid_before(agora - datetime.timedelta(days=1))
                  .not_valid_after(agora + datetime.timedelta(days=365))
                  .add_extension(x509.BasicConstraints(ca=ac, path_length=None), critical=True)
                  .add_extension(x509.KeyUsage(
                      digital_signature=not ac, content_commitment=not ac, key_encipherment=False,
                      data_encipherment=False, key_agreement=False, key_cert_sign=ac, crl_sign=ac,
                      encipher_only=False, decipher_only=False), critical=True))
    if uso_estendido:
        construtor = construtor.add_extension(x509.ExtendedKeyUsage(uso_estendido), critical=True)
    return construtor.sign(chave_emissor, hashes.SHA256())


def _der(certificado):
    return certificado.public_bytes(serialization.Encoding.DER)


class Infraestrutura:
    """AC de teste, certificado do signatário (“FULANO DE TAL:CPF”) e uma TSA de teste."""

    def __init__(self):
        self.chave_ac = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.ac = _certificado("AC DE TESTE", self.chave_ac.public_key(), "AC DE TESTE", self.chave_ac, ac=True)
        self.chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.certificado = _certificado("FULANO DE TAL:12345678909", self.chave.public_key(), "AC DE TESTE",
                                        self.chave_ac)
        chave_tsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tsa = _certificado("TSA DE TESTE", chave_tsa.public_key(), "AC DE TESTE", self.chave_ac,
                           uso_estendido=[ExtendedKeyUsageOID.TIME_STAMPING])
        self.carimbador = DummyTimeStamper(
            tsa_cert=x509_asn1.Certificate.load(_der(tsa)),
            tsa_key=chaves_asn1.PrivateKeyInfo.load(self.chave_tsa_der(chave_tsa)))
        self.hashes_assinados = []

    @staticmethod
    def chave_tsa_der(chave):
        return chave.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption())

    def assinar_hash(self, hash_, algoritmo):
        """Faz o papel do token: assina um hash pronto (PKCS#1 v1.5)."""
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
        self.hashes_assinados.append(hash_)
        return self.chave.sign(hash_, padding.PKCS1v15(), Prehashed(ALGORITMOS[algoritmo]))

    def assinante(self):
        return AssinanteExterno(_der(self.certificado), [_der(self.ac)], self.assinar_hash)


class TesteFuncoesAuxiliares(unittest.TestCase):

    def test_formatar_documento(self):
        self.assertEqual(formatar_documento("12345678909"), "123.456.789-09")
        self.assertEqual(formatar_documento("14281806000100"), "14.281.806/0001-00")
        self.assertEqual(formatar_documento("123"), "123")

    def test_descrever_titular_icp_brasil(self):
        infra = Infraestrutura()
        titular = descrever_titular(_der(infra.certificado))
        self.assertEqual(titular.nome, "FULANO DE TAL")
        self.assertEqual(titular.documento, "123.456.789-09")
        self.assertEqual(titular.tipo_documento, "CPF")
        self.assertEqual(titular.emissor, "AC DE TESTE")
        self.assertFalse(titular.vencido())

    def test_apto_para_assinar(self):
        infra = Infraestrutura()
        self.assertTrue(apto_para_assinar(_der(infra.certificado)))
        self.assertFalse(apto_para_assinar(_der(infra.ac)))  # autoassinado e só para emitir certificados

    def test_texto_selo(self):
        titular = descrever_titular(_der(Infraestrutura().certificado))
        self.assertEqual(texto_selo(titular),
                         "Assinado digitalmente por\nFULANO DE TAL\nCPF: 123.456.789-09\nData: %(ts)s")

    def test_nome_arquivo_assinado(self):
        self.assertEqual(nome_arquivo_assinado(os.path.join("pasta", "contrato.pdf")),
                         os.path.join("pasta", "contrato_assinado.pdf"))

    def test_converter_retangulo(self):
        documento = pymupdf.open()
        pagina = documento.new_page(width=600, height=800)
        self.assertEqual(converter_retangulo(pagina, pymupdf.Rect(10, 20, 110, 70)), (10, 730, 110, 780))
        pagina.set_rotation(90)  # exibida deitada: 800 × 600
        x0, y0, x1, y1 = converter_retangulo(pagina, pymupdf.Rect(0, 0, 100, 50))
        self.assertAlmostEqual(x1 - x0, 50)  # largura e altura trocam de lugar
        self.assertAlmostEqual(y1 - y0, 100)
        volta = pymupdf.Rect(x0, y0, x1, y1) * pagina.transformation_matrix * pagina.rotation_matrix
        volta.normalize()
        self.assertEqual(tuple(round(v) for v in volta), (0, 0, 100, 50))
        documento.close()


class TesteAssinatura(unittest.TestCase):

    def setUp(self):
        self.infra = Infraestrutura()
        self.pasta = tempfile.TemporaryDirectory()
        self.origem = os.path.join(self.pasta.name, "contrato.pdf")
        documento = pymupdf.open()
        for _ in range(2):
            documento.new_page(width=595, height=842).insert_text((72, 72), "Contrato de teste")
        documento.save(self.origem)
        documento.close()
        self.destino = nome_arquivo_assinado(self.origem)

    def tearDown(self):
        self.pasta.cleanup()

    def _assinar(self, origem=None, destino=None, carimbador=None, **opcoes):
        opcoes = OpcoesAssinatura(pagina=opcoes.pop("pagina", 1), retangulo=opcoes.pop("retangulo", (50, 50, 250, 110)),
                                  **opcoes)
        assinar_pdf(origem or self.origem, destino or self.destino, self.infra.assinante(), opcoes, carimbador)

    def _verificar(self, caminho=None, senha=None, raizes=None):
        with open(caminho or self.destino, "rb") as arquivo:
            dados = arquivo.read()
        raizes = [_der(self.infra.ac)] if raizes is None else raizes
        return verificar_assinaturas(dados, senha=senha, raizes=raizes)

    def test_assina_e_verifica(self):
        self._assinar(motivo="Concordo com os termos", local="Belo Horizonte")
        self.assertEqual(len(self.infra.hashes_assinados), 1)  # o “token” foi usado uma só vez
        [resultado] = self._verificar()
        self.assertEqual(resultado.situacao, "valida")
        self.assertEqual(resultado.campo, "Assinatura1")
        self.assertEqual(resultado.titular.nome, "FULANO DE TAL")
        self.assertFalse(resultado.data_do_carimbo)
        self.assertEqual(resultado.alteracoes, "")

        documento = pymupdf.open(self.destino)
        self.assertTrue(possui_assinaturas(documento))
        [widget] = list(documento[1].widgets())
        self.assertEqual(widget.field_type, pymupdf.PDF_WIDGET_TYPE_SIGNATURE)
        self.assertEqual(tuple(round(v) for v in widget.rect), (50, 842 - 110, 250, 842 - 50))
        dicionario = documento.xref_get_key(widget.xref, "V")[1]
        self.assertIn("ETSI.CAdES.detached", documento.xref_object(int(dicionario.split()[0])))
        documento.close()

    def test_origem_fica_intacta_e_nao_assinada(self):
        with open(self.origem, "rb") as arquivo:
            antes = arquivo.read()
        self._assinar()
        with open(self.origem, "rb") as arquivo:
            self.assertEqual(arquivo.read(), antes)
        with open(self.destino, "rb") as arquivo:
            self.assertTrue(arquivo.read().startswith(antes))  # salvamento incremental
        documento = pymupdf.open(self.origem)
        self.assertFalse(possui_assinaturas(documento))
        documento.close()

    def test_recusa_destino_igual_a_origem(self):
        with self.assertRaises(ValueError):
            self._assinar(destino=self.origem)

    def test_erro_do_token_nao_cria_arquivo(self):
        def falhar(hash_, algoritmo):
            raise OSError("PIN incorreto")
        self.infra.assinar_hash = falhar
        with self.assertRaises(OSError):
            self._assinar()
        self.assertFalse(os.path.exists(self.destino))
        self.assertFalse(os.path.exists(self.destino + ".tmp"))

    def test_alteracao_invalida_a_assinatura(self):
        self._assinar()
        with open(self.destino, "rb") as arquivo:
            dados = bytearray(arquivo.read())
        posicao = dados.index(b"Contrato de teste") if b"Contrato de teste" in dados else 200
        dados[posicao] ^= 0x01
        with open(self.destino, "wb") as arquivo:
            arquivo.write(dados)
        resultados = self._verificar()
        self.assertTrue(all(resultado.situacao == "invalida" for resultado in resultados))

    def test_anotacao_posterior_e_informada(self):
        self._assinar()
        documento = pymupdf.open(self.destino)
        documento[0].add_freetext_annot(pymupdf.Rect(100, 100, 300, 140), "Observação")
        documento.saveIncr()
        documento.close()
        [resultado] = self._verificar()
        self.assertTrue(resultado.integra)  # a parte assinada continua intacta…
        self.assertEqual(resultado.situacao, "alterada")  # …mas o documento mudou depois
        self.assertIn("depois", resultado.alteracoes)

    def test_emissor_desconhecido(self):
        self._assinar()
        [resultado] = self._verificar(raizes=[])
        self.assertEqual(resultado.situacao, "nao_confiavel")

    def test_duas_assinaturas(self):
        self._assinar()
        segundo = os.path.join(self.pasta.name, "contrato_assinado2.pdf")
        self._assinar(origem=self.destino, destino=segundo, pagina=0)
        resultados = self._verificar(segundo)
        self.assertEqual([r.campo for r in resultados], ["Assinatura1", "Assinatura2"])
        self.assertTrue(all(r.situacao == "valida" for r in resultados))

    def test_carimbo_de_tempo(self):
        self._assinar(carimbador=self.infra.carimbador)
        [resultado] = self._verificar()
        self.assertEqual(resultado.situacao, "valida")
        self.assertTrue(resultado.data_do_carimbo)
        self.assertIsNotNone(resultado.data)

    def test_pdf_com_senha(self):
        protegido = os.path.join(self.pasta.name, "protegido.pdf")
        documento = pymupdf.open(self.origem)
        documento.save(protegido, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="segredo", owner_pw="dono")
        documento.close()
        destino = nome_arquivo_assinado(protegido)
        self._assinar(origem=protegido, destino=destino, senha="segredo")
        [resultado] = self._verificar(destino, senha="segredo")
        self.assertEqual(resultado.situacao, "valida")

    def test_selo_com_acentos(self):
        self.infra.certificado = _certificado("JOÃO CONCEIÇÃO:12345678909", self.infra.chave.public_key(),
                                              "AC DE TESTE", self.infra.chave_ac)
        self._assinar()
        documento = pymupdf.open(self.destino)
        [widget] = list(documento[1].widgets())
        xref_aparencia = documento.xref_get_key(widget.xref, "AP/N")[1].split()[0]
        self.assertTrue(documento.xref_stream(int(xref_aparencia)))
        documento.close()
        [resultado] = self._verificar()
        self.assertEqual(resultado.titular.nome, "JOÃO CONCEIÇÃO")


if __name__ == "__main__":
    unittest.main()
