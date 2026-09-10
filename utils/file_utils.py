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

    @staticmethod
    def write_text_file(file_path: str, content: str) -> str:
        """Grava conteudo textual em formato UTF-8 no arquivo especificado.

        Args:
            file_path: Caminho de destino do arquivo.
            content: Conteudo textual a ser gravado.

        Returns:
            Caminho absoluto do arquivo gravado.
        """
        abs_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_path
