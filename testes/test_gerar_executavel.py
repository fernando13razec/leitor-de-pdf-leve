"""Testes da conferência da versão do Python feita antes de gerar o executável."""

import platform
import unittest
from unittest import mock

from ferramentas import gerar_executavel


def versao_fixada():
    return gerar_executavel.ARQUIVO_VERSAO_PYTHON.read_text(encoding="utf-8").strip()


class TesteConferirVersaoDoPython(unittest.TestCase):

    def test_arquivo_fixa_a_versao_completa(self):
        # Com só "3.14", o GitHub Actions escolheria a versão mais recente e a conferência não passaria.
        self.assertRegex(versao_fixada(), r"^\d+\.\d+\.\d+$")

    def test_mesma_versao_continua(self):
        with (mock.patch.object(platform, "python_version", return_value=versao_fixada()),
              mock.patch("builtins.print")):
            gerar_executavel.conferir_versao_do_python()

    def test_outra_versao_para_com_erro(self):
        with (mock.patch.object(platform, "python_version", return_value="3.0.0"),
              mock.patch("builtins.print"),
              self.assertRaises(SystemExit) as erro):
            gerar_executavel.conferir_versao_do_python()
        mensagem = str(erro.exception.code)
        self.assertIn("3.0.0", mensagem)
        self.assertIn(versao_fixada(), mensagem)


if __name__ == "__main__":
    unittest.main()
