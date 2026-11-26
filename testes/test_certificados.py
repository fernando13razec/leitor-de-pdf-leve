"""Testes da camada de certificados do Windows (sem depender de um token conectado)."""

import unittest

from pdf_leve.sistema.certificados import (
    CRYPT_E_NO_KEY_PROPERTY, SCARD_W_WRONG_CHV, STATUS_NOT_FOUND, ErroCertificado, certificados_raiz,
    descrever_erro, listar_certificados,
)
from pdf_leve.sistema.windows import NO_WINDOWS


class TesteMensagensDeErro(unittest.TestCase):

    def test_codigos_conhecidos(self):
        self.assertEqual(descrever_erro(SCARD_W_WRONG_CHV), "PIN incorreto")
        self.assertEqual(descrever_erro(STATUS_NOT_FOUND), "O token não está conectado")
        self.assertIn("chave privada", descrever_erro(CRYPT_E_NO_KEY_PROPERTY))

    def test_faixa_de_cartao_inteligente_e_codigo_negativo(self):
        self.assertEqual(descrever_erro(0x80100099 - 2**32), "O token não está conectado")  # HRESULT com sinal

    def test_codigo_desconhecido_e_operacao(self):
        self.assertEqual(descrever_erro(0x1234, "Assinatura"), "Assinatura: erro 0x00001234")

    def test_cancelamento(self):
        self.assertTrue(ErroCertificado(0x8010006E).cancelado)
        self.assertFalse(ErroCertificado(SCARD_W_WRONG_CHV).cancelado)


@unittest.skipUnless(NO_WINDOWS, "só no Windows")
class TesteRepositorioDoWindows(unittest.TestCase):

    def test_listar_nao_falha(self):
        for certificado in listar_certificados():  # pode ser vazio (CI sem token)
            self.assertEqual(len(certificado.impressao_digital), 40)
            self.assertTrue(certificado.der)

    def test_raizes(self):
        self.assertTrue(certificados_raiz())  # o Windows sempre traz raízes confiáveis


if __name__ == "__main__":
    unittest.main()
