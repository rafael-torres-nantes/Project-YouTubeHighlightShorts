from typing import Optional
import os
import shutil


class FileUtils:
    """Utilitarios para manipulacao segura de arquivos e diretorios no sistema de arquivos."""

    @staticmethod
    def ensure_directory(directory_path: str) -> str:
        """Garante a existencia de um diretorio no sistema de arquivos.

        Args:
            directory_path: Caminho da pasta a ser criada.

        Returns:
            Caminho absoluto da pasta.
        """
        abs_path = os.path.abspath(directory_path)
        os.makedirs(abs_path, exist_ok=True)
        return abs_path

    @staticmethod
    def cleanup_directory(directory_path: str) -> None:
        """Remove com seguranca um diretorio e todo seu conteudo.

        Args:
            directory_path: Caminho da pasta a ser limpa.
        """
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path, ignore_errors=True)
