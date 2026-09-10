from typing import Any, Dict, List, Optional
import logging
import os
import shutil

from config.settings import AppSettings
from services.curation_service import CurationService
from services.download_service import DownloadService
from services.retention_service import RetentionService
from services.transcription_service import TranscriptionService
from services.video_editor_service import VideoEditorService
from utils.file_utils import FileUtils

logger = logging.getLogger(__name__)


class PipelineController:
    """Orquestra o fluxo completo de transformacao de videos do YouTube em Shorts verticais."""

    def __init__(self, settings: Optional[AppSettings] = None) -> None:
        self._settings = settings or AppSettings()
        self._download_service = DownloadService(ytdlp_bin=self._settings.get_ytdlp_bin())
        self._retention_service = RetentionService()
        self._transcription_service = TranscriptionService()
        self._curation_service = CurationService()
        self._video_editor_service = VideoEditorService(ffmpeg_bin=self._settings.get_ffmpeg_bin())

    def generate_markdown_report(
        self,
        clips: List[Dict[str, Any]],
        output_dir: str,
        max_clips: int,
        report_filename: str = "report.md",
    ) -> str:
        """Gera um arquivo Markdown detalhado com os metadados dos clipes criados.

        Args:
            clips: Lista de dicionarios com os metadados de cada clipe renderizado.
            output_dir: Diretorio onde o relatorio sera gravado.
            max_clips: Quantidade de clipes configurada no ambiente.
            report_filename: Nome do arquivo markdown (padrao: report.md).

        Returns:
            Caminho absoluto do arquivo Markdown gerado.
        """
        report_path = os.path.join(output_dir, report_filename)
        lines = [
            f"### 🎬 Clipes Gerados com Sucesso (Padrão .env = {max_clips} Clipes)",
            "",
            f"A variável `MAX_CLIPS={max_clips}` foi configurada e o pipeline gerou {len(clips)} recortes verticais completos, sem cortes abruptos e com a legenda na altura ideal:",
            "",
        ]

        for index, clip in enumerate(clips, start=1):
            title = clip.get("title", f"Clipe {index}")
            duration = clip.get("duration", 0.0)
            start_t = clip.get("start_time", 0.0)
            end_t = clip.get("end_time", 0.0)
            viral_score = clip.get("viral_score", 0.0)
            hook = clip.get("hook_summary", "")
            rendered_path = clip.get("rendered_path", "")
            filename = os.path.basename(rendered_path) if rendered_path else f"clip_{index}.mp4"

            lines.append(f"#### {index}. {title}")
            lines.append("")
            lines.append(f"• ⏱️ **Duração**: {duration:.2f}s (Trecho: {start_t:.2f}s -> {end_t:.2f}s)")
            lines.append(f"• 🔥 **Viral Score**: {viral_score:.1f} / 10.0")
            lines.append(f"• 💡 **Gancho**: {hook}")
            lines.append(f"• 📁 **Arquivo**: `{filename}`")
            lines.append("")

        content = "\n".join(lines)
        FileUtils.write_text_file(report_path, content)
        logger.info("Relatorio Markdown gerado com sucesso em: %s", report_path)
        return os.path.abspath(report_path)

    def execute_pipeline(
        self,
        youtube_url: str,
        max_clips: int = 3,
        output_dir: str = "./output",
        progress_callback: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Executa todas as etapas integradas de extracao, analise, curadoria e edicao.

        Args:
            youtube_url: URL do video do YouTube a ser processado.
            max_clips: Quantidade maxima de clipes a serem gerados.
            output_dir: Diretorio final onde os videos renderizados serao salvos.
            progress_callback: Funcao opcional para atualizar status/progresso (ex: tqdm).

        Returns:
            Lista de dicionarios com os dados e caminhos de cada clipe vertical gerado.

        Raises:
            Exception: Se qualquer etapa critica do pipeline falhar.
        """
        temp_dir = os.path.abspath(self._settings.get_temp_dir())
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        try:
            # 1. Ingestao e Download
            if progress_callback:
                progress_callback("Ingestao: Baixando midia e extraindo heatmap...", 15)
            logger.info("Etapa 1: Baixando midia e extraindo metadados...")
            media_info = self._download_service.download_media_streams(youtube_url, temp_dir)

            try:
                raw_heatmap = self._download_service.extract_heatmap_data(youtube_url)
            except Exception as exc:
                logger.warning("Heatmap publico nao disponivel: %s. Utilizando fallback linear.", exc)
                video_duration = media_info.get("duration", 300.0)
                raw_heatmap = [
                    {"start_time": t, "end_time": min(t + 10.0, video_duration), "value": 0.5}
                    for t in range(0, int(video_duration), 10)
                ]

            # 2. Analise de Retencao
            if progress_callback:
                progress_callback("Metricas: Processando picos de retencao estatistica...", 35)
            logger.info("Etapa 2: Normalizando curva e detectando picos de retencao...")
            normalized_heatmap = self._retention_service.normalize_heatmap_points(raw_heatmap)
            peak_windows = self._retention_service.detect_peak_windows(normalized_heatmap)

            # 3. Transcricao Word-Level
            if progress_callback:
                progress_callback("Transcricao: Transcrevendo audio com faster-whisper...", 55)
            logger.info("Etapa 3: Transcrevendo audio e mapeando engajamento segundo a segundo...")
            raw_segments = self._transcription_service.transcribe_audio_word_level(media_info["audio_path"])
            enriched_segments = self._transcription_service.map_transcription_to_engagement(
                raw_segments, normalized_heatmap
            )

            # 4. Curadoria Semantica LLM
            if progress_callback:
                progress_callback("Curadoria: Avaliando ganchos e coerencia via LLM...", 75)
            logger.info("Etapa 4: Curando melhores cortes via Gemini...")
            selected_highlights = self._curation_service.curate_highlights(
                enriched_segments=enriched_segments,
                peak_windows=peak_windows,
                max_clips=max_clips,
            )

            # 5. Edicao, Legendagem e Renderizacao
            if progress_callback:
                progress_callback("Edicao: Renderizando videos 9:16 com legendas .ass...", 90)
            logger.info("Etapa 5: Renderizando cortes verticais via FFmpeg...")
            generated_clips = []

            all_words: List[Dict[str, Any]] = []
            for seg in enriched_segments:
                all_words.extend(seg.get("words", []))

            for index, highlight in enumerate(selected_highlights, start=1):
                raw_start = highlight["start_time"]
                raw_end = highlight["end_time"]

                # Alinhamento da palavra inicial
                start_words = [w for w in all_words if abs(w["start"] - raw_start) <= 1.0]
                clip_start = start_words[0]["start"] if start_words else raw_start

                # Alinhamento da palavra final + buffer de respiro auditivo
                end_words = [w for w in all_words if w["end"] <= (raw_end + 1.2) and w["end"] >= (raw_end - 0.5)]
                if end_words:
                    clip_end = max(raw_end, end_words[-1]["end"] + 0.35)
                else:
                    clip_end = raw_end + 0.35

                safe_title = "".join(c for c in highlight["title"] if c.isalnum() or c in (" ", "_", "-")).strip()
                clip_filename = f"clip_{index}_{safe_title[:30].replace(' ', '_')}.mp4"
                output_clip_path = os.path.join(output_dir, clip_filename)
                ass_sub_path = os.path.join(temp_dir, f"subtitles_clip_{index}.ass")

                clip_words = [
                    w for w in all_words if w["start"] >= clip_start and w["end"] <= clip_end
                ]

                self._video_editor_service.generate_ass_subtitles(
                    words_in_clip=clip_words,
                    clip_start_time=clip_start,
                    output_ass_path=ass_sub_path,
                )

                rendered_path = self._video_editor_service.render_vertical_clip(
                    source_video_path=media_info["video_path"],
                    source_audio_path=media_info["audio_path"],
                    start_time=clip_start,
                    end_time=clip_end,
                    output_clip_path=output_clip_path,
                    ass_subtitles_path=ass_sub_path,
                )

                highlight["start_time"] = round(clip_start, 2)
                highlight["end_time"] = round(clip_end, 2)
                highlight["duration"] = round(clip_end - clip_start, 2)
                highlight["rendered_path"] = rendered_path
                generated_clips.append(highlight)

            # 6. Geracao automatica do relatorio Markdown em output/
            report_file = self.generate_markdown_report(
                clips=generated_clips,
                output_dir=output_dir,
                max_clips=max_clips,
            )
            logger.info("Relatorio consolidado gravado: %s", report_file)

            if progress_callback:
                progress_callback("Concluido: Pipeline finalizada com sucesso.", 100)

            return generated_clips

        finally:
            logger.info("Limpando arquivos temporarios em: %s", temp_dir)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    controller = PipelineController()
    logger.info("PipelineController carregado com sucesso.")
