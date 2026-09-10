from typing import Any, Dict, List, Optional
import json
import logging
import os
import yt_dlp

logger = logging.getLogger(__name__)


class DownloadService:
    """Executa a extracao de metadados, heatmap e download de fluxos de midia via yt-dlp."""

    MAX_VIDEO_HEIGHT = 1080

    def __init__(self, ytdlp_bin: Optional[str] = None) -> None:
        self._ytdlp_bin = ytdlp_bin or os.getenv("YTDLP_BIN", "yt-dlp")

    def extract_heatmap_data(self, url: str) -> List[Dict[str, float]]:
        """Extrai os pontos brutos do grafico de retencao/heatmap (Most Replayed).

        Le o array de marcadores de calor retornado pelo player do YouTube.

        Args:
            url: URL publica do video no YouTube.

        Returns:
            Lista de dicionarios com chaves 'start_time', 'end_time' e 'value'.

        Raises:
            ValueError: Se o heatmap nao estiver disponivel no video informado.
            yt_dlp.utils.DownloadError: Se houver falha na comunicacao ou extracao de metadados.
        """
        ydl_opts = {
            "extract_flat": False,
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

        raw_heatmap = info_dict.get("heatmap")
        if not raw_heatmap:
            logger.warning("Heatmap nao localizado nos metadados primarios para URL: %s", url)
            raise ValueError("O video nao possui dados publicos de heatmap disponiveis.")

        normalized_points = []
        for point in raw_heatmap:
            normalized_points.append(
                {
                    "start_time": float(point.get("start_time", 0.0)),
                    "end_time": float(point.get("end_time", 0.0)),
                    "value": float(point.get("value", 0.0)),
                }
            )

        logger.info("Heatmap extraido com sucesso: %d pontos temporais encontrados.", len(normalized_points))
        return normalized_points

    def download_media_streams(self, url: str, output_directory: str) -> Dict[str, Any]:
        """Baixa o fluxo de video (ate 1080p) e o fluxo isolado de audio.

        Garante o download dos componentes necessarios para analise e reprocessamento.

        Args:
            url: URL do video a ser baixado.
            output_directory: Diretorio de destino dos arquivos gerados.

        Returns:
            Dicionario com os caminhos absolutos 'video_path', 'audio_path', titulo e duracao.

        Raises:
            RuntimeError: Se os arquivos de video ou audio nao forem localizados apos o processo.
            yt_dlp.utils.DownloadError: Se o download falhar via yt-dlp.
        """
        os.makedirs(output_directory, exist_ok=True)
        video_template = os.path.join(output_directory, "%(id)s_video.%(ext)s")
        audio_template = os.path.join(output_directory, "%(id)s_audio.%(ext)s")

        video_opts = {
            "format": f"bestvideo[height<={self.MAX_VIDEO_HEIGHT}][ext=mp4]/bestvideo[height<={self.MAX_VIDEO_HEIGHT}]",
            "outtmpl": video_template,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(video_opts) as ydl_video:
            video_info = ydl_video.extract_info(url, download=True)
            video_filename = ydl_video.prepare_filename(video_info)

        audio_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": audio_template,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(audio_opts) as ydl_audio:
            audio_info = ydl_audio.extract_info(url, download=True)
            audio_filename = ydl_audio.prepare_filename(audio_info)

        if not os.path.exists(video_filename):
            raise RuntimeError(f"Arquivo de video nao gravado no destino: {video_filename}")

        if not os.path.exists(audio_filename):
            raise RuntimeError(f"Arquivo de audio nao gravado no destino: {audio_filename}")

        logger.info("Download concluido. Video: %s | Audio: %s", video_filename, audio_filename)
        return {
            "video_path": os.path.abspath(video_filename),
            "audio_path": os.path.abspath(audio_filename),
            "title": str(video_info.get("title", "video")),
            "duration": float(video_info.get("duration", 0.0)),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    service = DownloadService()

    logger.info("Testando extracao isolada de Heatmap...")
    try:
        heatmap_points = service.extract_heatmap_data(test_url)
        logger.info("Amostra dos 3 primeiros pontos do heatmap: %s", heatmap_points[:3])
    except Exception as exc:
        logger.error("Falha durante o teste de heatmap: %s", exc)
