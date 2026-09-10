from typing import Any, Dict, List, Optional
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class VideoEditorService:
    """Executa o fatiamento, transformacao vertical (9:16) e queima de legendas via FFmpeg."""

    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920

    def __init__(self, ffmpeg_bin: Optional[str] = None) -> None:
        self._ffmpeg_bin = ffmpeg_bin or os.getenv("FFMPEG_BIN", "ffmpeg")

    def format_timestamp_ass(self, seconds: float) -> str:
        """Converte segundos para o formato de tempo padrao do ASS (H:MM:SS.cs).

        Args:
            seconds: Tempo em segundos.

        Returns:
            String no formato H:MM:SS.cs (centisegundos).
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int(round((seconds - int(seconds)) * 100))

        if centisecs >= 100:
            secs += 1
            centisecs = 0

        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def generate_ass_subtitles(
        self,
        words_in_clip: List[Dict[str, Any]],
        clip_start_time: float,
        output_ass_path: str,
    ) -> str:
        """Gera um arquivo de legendas estilizas no formato .ass com destaque palavra por palavra.

        Args:
            words_in_clip: Lista de palavras com timestamps globais.
            clip_start_time: Tempo inicial do corte para normalizacao relativa (t=0).
            output_ass_path: Caminho de destino do arquivo .ass.

        Returns:
            Caminho do arquivo de legenda gerado.
        """
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.TARGET_WIDTH}
PlayResY: {self.TARGET_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,40,40,320,1
Style: Highlight,Arial Black,70,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,105,105,0,0,1,6,3,2,40,40,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        # Agrupa palavras em pequenos blocos de 3 a 5 palavras para melhor leitura no formato vertical
        chunk_size = 4
        for i in range(0, len(words_in_clip), chunk_size):
            chunk = words_in_clip[i : i + chunk_size]
            if not chunk:
                continue

            chunk_start = max(0.0, chunk[0]["start"] - clip_start_time)
            chunk_end = max(chunk_start + 0.5, chunk[-1]["end"] - clip_start_time)

            start_str = self.format_timestamp_ass(chunk_start)
            end_str = self.format_timestamp_ass(chunk_end)

            chunk_text = " ".join([w["word"].upper() for w in chunk])
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{chunk_text}")

        content = header + "\n".join(events) + "\n"

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Legendas ASS geradas em: %s", output_ass_path)
        return output_ass_path

    def render_vertical_clip(
        self,
        source_video_path: str,
        source_audio_path: str,
        start_time: float,
        end_time: float,
        output_clip_path: str,
        ass_subtitles_path: Optional[str] = None,
    ) -> str:
        """Processa o corte de video, transformacao 9:16 com blur background e queima de legendas.

        Usa filtro complexo do FFmpeg para criar fundo desfocado (1080x1920) e sobrepor
        o video original mantendo a proporcao de aspecto intacta.

        Args:
            source_video_path: Caminho do arquivo de video original.
            source_audio_path: Caminho do arquivo de audio original.
            start_time: Inicio do corte em segundos.
            end_time: Fim do corte em segundos.
            output_clip_path: Destino do arquivo .mp4 final.
            ass_subtitles_path: Caminho opcional do arquivo de legenda .ass para queima direta.

        Returns:
            Caminho absoluto do video vertical renderizado.

        Raises:
            RuntimeError: Se o comando do FFmpeg falhar durante a renderizacao.
        """
        duration = end_time - start_time
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)

        # Filtro de video:
        # 1. Duplica stream [0:v] em [bg] e [fg]
        # 2. [bg] e escalado para preencher 1080x1920 e recebe blur forte (boxblur)
        # 3. [fg] e escalado proporcionalmente para caber na largura de 1080 sem distorcer
        # 4. [fg] e sobreposto centralizado sobre [bg]
        filter_complex = (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]scale={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={self.TARGET_WIDTH}:{self.TARGET_HEIGHT},boxblur=luma_radius=min(h\\,w)/20:luma_power=2[bg];"
            f"[fg_src]scale={self.TARGET_WIDTH}:-1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v_composed]"
        )

        final_v_label = "[v_composed]"

        if ass_subtitles_path and os.path.exists(ass_subtitles_path):
            # Escapa caminhos no Windows para a sintaxe de filtro do FFmpeg
            escaped_sub_path = ass_subtitles_path.replace("\\", "/").replace(":", "\\:")
            filter_complex += f";[v_composed]subtitles='{escaped_sub_path}'[v_final]"
            final_v_label = "[v_final]"

        cmd = [
            self._ffmpeg_bin,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            source_video_path,
            "-ss",
            f"{start_time:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            source_audio_path,
            "-filter_complex",
            filter_complex,
            "-map",
            final_v_label,
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_clip_path,
        ]

        logger.info("Iniciando renderizacao FFmpeg: %s -> %s", start_time, end_time)
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("Falha na renderizacao do FFmpeg: %s", result.stderr)
            raise RuntimeError(f"FFmpeg retornou codigo {result.returncode}: {result.stderr}")

        logger.info("Clipe vertical renderizado com sucesso: %s", output_clip_path)
        return os.path.abspath(output_clip_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    editor = VideoEditorService()
    logger.info("Modulo VideoEditorService pronto para integracao.")
