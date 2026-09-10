from dotenv import load_dotenv
import os

load_dotenv()


class AppSettings:
    """Centraliza as configuracoes e caminhos de execucao do sistema."""

    def __init__(self) -> None:
        self._ytdlp_bin = os.getenv("YTDLP_BIN", "yt-dlp")
        self._ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        self._ffprobe_bin = os.getenv("FFPROBE_BIN", "ffprobe")
        self._temp_dir = os.getenv("TEMP_STORAGE_DIR", "./tmp")
        self._max_clips = int(os.getenv("MAX_CLIPS", "3"))

    def get_ytdlp_bin(self) -> str:
        """Retorna o caminho ou comando do executavel do yt-dlp.

        Returns:
            String contendo o comando ou caminho absoluto configurado.
        """
        return self._ytdlp_bin

    def get_ffmpeg_bin(self) -> str:
        """Retorna o executavel configurado para FFmpeg.

        Returns:
            String com o comando ou caminho do FFmpeg.
        """
        return self._ffmpeg_bin

    def get_ffprobe_bin(self) -> str:
        """Retorna o executavel configurado para FFprobe.

        Returns:
            String com o comando ou caminho do FFprobe.
        """
        return self._ffprobe_bin

    def get_temp_dir(self) -> str:
        """Retorna o diretorio base para arquivos temporarios.

        Returns:
            Caminho do diretorio de armazenamento intermediario.
        """
        return self._temp_dir

    def get_max_clips(self) -> int:
        """Retorna a quantidade padrao de clipes a serem gerados.

        Returns:
            Numero inteiro configurado no ambiente.
        """
        return self._max_clips
