from typing import Any, Dict, List, Optional
import logging
import os
import sys

# Configura caminhos para bibliotecas CUDA no Windows
site_packages_dir = os.path.join(os.path.dirname(os.path.dirname(os.__file__)), "Lib", "site-packages")
for sub in ["cublas", "cudnn"]:
    bin_dir = os.path.join(site_packages_dir, "nvidia", sub, "bin")
    if os.path.exists(bin_dir):
        try:
            os.add_dll_directory(bin_dir)
            os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")
        except Exception:
            pass

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Realiza a transcricao de audio com timestamps por palavra e correlaciona com metricas de retencao."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        download_root: Optional[str] = None,
    ) -> None:
        self._model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "base")
        self._device = device or os.getenv("WHISPER_DEVICE", "cuda")
        self._compute_type = compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "float16")
        self._download_root = download_root or os.getenv("WHISPER_DOWNLOAD_ROOT", "F:\\AI-Models\\whisper")

        self._model = None

    def load_model(self) -> WhisperModel:
        """Carrega e instancia o modelo faster-whisper sob demanda.

        Returns:
            Instancia ativa do WhisperModel.

        Raises:
            RuntimeError: Se o carregamento do modelo no dispositivo configurado falhar.
        """
        if self._model is not None:
            return self._model

        logger.info(
            "Carregando faster-whisper (modelo: %s, device: %s, compute_type: %s)...",
            self._model_size,
            self._device,
            self._compute_type,
        )

        try:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=self._download_root,
            )
            return self._model
        except Exception as exc:
            if self._device == "cuda":
                logger.warning("Falha ao carregar no CUDA (%s). Tentando fallback para CPU (int8)...", exc)
                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=self._download_root,
                )
                return self._model
            raise RuntimeError(f"Erro critico ao inicializar faster-whisper: {exc}") from exc

    def transcribe_audio_word_level(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcreve o arquivo de audio retornando segmentos com timestamps em nivel de palavra.

        Args:
            audio_path: Caminho do arquivo de audio a ser transcrito.

        Returns:
            Lista de segmentos transcritos contendo texto, inicio, fim e array detalhado de palavras.

        Raises:
            FileNotFoundError: Se o arquivo de audio informado nao existir.
            RuntimeError: Se houver falha no processo de inferencia.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo de audio nao encontrado: {audio_path}")

        model = self.load_model()
        logger.info("Iniciando transcricao word-level para: %s", audio_path)

        try:
            segments_generator, info = model.transcribe(
                audio_path,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
            )

            logger.info("Idioma detectado: %s com probabilidade %.2f%%", info.language, info.language_probability * 100)

            transcription_results = []
            for segment in segments_generator:
                words_list = []
                if segment.words:
                    for word in segment.words:
                        words_list.append(
                            {
                                "word": word.word.strip(),
                                "start": float(word.start),
                                "end": float(word.end),
                                "probability": float(word.probability),
                            }
                        )

                transcription_results.append(
                    {
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": segment.text.strip(),
                        "words": words_list,
                    }
                )

            logger.info("Transcricao concluida: %d segmentos identificados.", len(transcription_results))
            return transcription_results

        except Exception as exc:
            if "cublas" in str(exc).lower() and self._device == "cuda":
                logger.warning("Falha durante inferencia em CUDA (%s). Executando com CPU fallback...", exc)
                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=self._download_root,
                )
                segments_generator, info = self._model.transcribe(
                    audio_path,
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=True,
                )
                transcription_results = []
                for segment in segments_generator:
                    words_list = []
                    if segment.words:
                        for word in segment.words:
                            words_list.append(
                                {
                                    "word": word.word.strip(),
                                    "start": float(word.start),
                                    "end": float(word.end),
                                    "probability": float(word.probability),
                                }
                            )
                    transcription_results.append(
                        {
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "text": segment.text.strip(),
                            "words": words_list,
                        }
                    )
                return transcription_results
            raise RuntimeError(f"Falha na inferencia de transcricao: {exc}") from exc

    def map_transcription_to_engagement(
        self,
        transcription_segments: List[Dict[str, Any]],
        engagement_curve: List[Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Correlaciona cada palavra e segmento transcrito ao indice de engajamento temporal.

        Args:
            transcription_segments: Segmentos com palavras e timestamps gerados pelo Whisper.
            engagement_curve: Lista de pontos normalizados {start_time, end_time, value}.

        Returns:
            Segmentos enriquecidos com engagement_score ponderado do trecho e pontuacao por palavra.
        """
        enriched_segments = []

        for segment in transcription_segments:
            seg_start = segment["start"]
            seg_end = segment["end"]

            matching_scores = []
            for point in engagement_curve:
                if point["end_time"] >= seg_start and point["start_time"] <= seg_end:
                    matching_scores.append(point["value"])

            average_engagement = 0.0
            if matching_scores:
                average_engagement = sum(matching_scores) / len(matching_scores)

            enriched_words = []
            for word_item in segment.get("words", []):
                w_start = word_item["start"]
                w_end = word_item["end"]
                w_scores = [
                    p["value"]
                    for p in engagement_curve
                    if p["end_time"] >= w_start and p["start_time"] <= w_end
                ]
                w_score = (sum(w_scores) / len(w_scores)) if w_scores else average_engagement

                enriched_words.append(
                    {
                        "word": word_item["word"],
                        "start": w_start,
                        "end": w_end,
                        "engagement_score": round(float(w_score), 4),
                    }
                )

            enriched_segments.append(
                {
                    "start": seg_start,
                    "end": seg_end,
                    "text": segment["text"],
                    "average_engagement": round(float(average_engagement), 4),
                    "words": enriched_words,
                }
            )

        return enriched_segments


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = TranscriptionService()
    logger.info("Modulo de transcricao carregado para validacao estrutural.")
