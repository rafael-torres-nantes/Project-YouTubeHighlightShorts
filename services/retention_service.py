from typing import Any, Dict, List, Tuple
import logging
import numpy as np
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)


class RetentionService:
    """Processa curvas de retencao do YouTube e detecta janelas temporais de pico com scipy."""

    DEFAULT_WINDOW_MIN_SECONDS = 30.0
    DEFAULT_WINDOW_MAX_SECONDS = 60.0

    def normalize_heatmap_points(self, raw_points: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """Normaliza os valores de engajamento do heatmap em uma escala de 0.0 a 1.0.

        Args:
            raw_points: Lista de pontos contendo 'start_time', 'end_time' e 'value'.

        Returns:
            Lista com os mesmos pontos, onde 'value' esta mapeado entre 0.0 e 1.0.

        Raises:
            ValueError: Se a lista de pontos estiver vazia.
        """
        if not raw_points:
            raise ValueError("A lista de pontos brutos do heatmap nao pode ser vazia.")

        values = np.array([p["value"] for p in raw_points], dtype=np.float64)
        min_val = np.min(values)
        max_val = np.max(values)

        range_val = max_val - min_val
        if range_val == 0.0:
            return [{"start_time": p["start_time"], "end_time": p["end_time"], "value": 1.0} for p in raw_points]

        normalized_points = []
        for p in raw_points:
            norm_val = (p["value"] - min_val) / range_val
            normalized_points.append(
                {
                    "start_time": float(p["start_time"]),
                    "end_time": float(p["end_time"]),
                    "value": round(float(norm_val), 4),
                }
            )

        logger.info("Curva de retencao normalizada com sucesso para %d pontos.", len(normalized_points))
        return normalized_points

    def detect_peak_windows(
        self,
        normalized_points: List[Dict[str, float]],
        min_duration: float = DEFAULT_WINDOW_MIN_SECONDS,
        max_duration: float = DEFAULT_WINDOW_MAX_SECONDS,
        prominence_threshold: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """Aplica scipy.signal.find_peaks para isolar intervalos temporais com maior engajamento.

        Args:
            normalized_points: Pontos normalizados do heatmap.
            min_duration: Duracao minima alvo da janela em segundos.
            max_duration: Duracao maxima alvo da janela em segundos.
            prominence_threshold: Proeminencia minima do pico para deteccao estatistica.

        Returns:
            Lista de dicionarios ordenados por score de pico decrescente contendo start_time, end_time e peak_score.
        """
        if not normalized_points:
            return []

        values = np.array([p["value"] for p in normalized_points])
        times = np.array([0.5 * (p["start_time"] + p["end_time"]) for p in normalized_points])

        # Encontra picos com proeminencia relativa
        peaks_indices, properties = find_peaks(
            values,
            prominence=prominence_threshold,
            distance=max(1, int(len(values) * 0.03)),
        )

        # Se nenhum pico passar no threshold rigoroso, seleciona os maiores valores relativos
        if len(peaks_indices) == 0:
            logger.warning("Nenhum pico detectado com proeminencia %.2f. Fazendo fallback para percentis superiores.", prominence_threshold)
            p90 = np.percentile(values, 90)
            peaks_indices = np.where(values >= p90)[0]

        total_video_duration = normalized_points[-1]["end_time"]
        candidate_windows = []

        for idx in peaks_indices:
            peak_time = times[idx]
            peak_score = float(values[idx])

            # A janela abrange uma introducao e o climax do pico detectado (1/3 antes, 2/3 depois)
            window_duration = (min_duration + max_duration) / 2.0
            start_candidate = max(0.0, peak_time - (window_duration * 0.35))
            end_candidate = min(total_video_duration, start_candidate + window_duration)

            # Ajuste de borda final
            if end_candidate >= total_video_duration:
                start_candidate = max(0.0, total_video_duration - window_duration)

            candidate_windows.append(
                {
                    "start_time": round(float(start_candidate), 2),
                    "end_time": round(float(end_candidate), 2),
                    "duration": round(float(end_candidate - start_candidate), 2),
                    "peak_time": round(float(peak_time), 2),
                    "peak_score": round(peak_score, 4),
                }
            )

        # Remove sobreposicoes excessivas entre janelas candidatas
        filtered_windows = self.filter_overlapping_windows(candidate_windows)
        logger.info("Identificadas %d janelas candidatas de retencao apos filtragem de sobreposicao.", len(filtered_windows))
        return filtered_windows

    def filter_overlapping_windows(
        self,
        windows: List[Dict[str, Any]],
        max_overlap_ratio: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """Remove janelas com alta sobreposicao priorizando as de maior pontuacao de pico.

        Args:
            windows: Lista de janelas candidatas.
            max_overlap_ratio: Proporcao maxima de intersecao permitida entre duas janelas.

        Returns:
            Lista de janelas unicas desduplicadas.
        """
        sorted_windows = sorted(windows, key=lambda w: w["peak_score"], reverse=True)
        selected_windows: List[Dict[str, Any]] = []

        for candidate in sorted_windows:
            overlaps = False
            for selected in selected_windows:
                intersection_start = max(candidate["start_time"], selected["start_time"])
                intersection_end = min(candidate["end_time"], selected["end_time"])
                intersection_duration = max(0.0, intersection_end - intersection_start)

                min_dur = min(candidate["duration"], selected["duration"])
                if min_dur > 0 and (intersection_duration / min_dur) > max_overlap_ratio:
                    overlaps = True
                    break

            if not overlaps:
                selected_windows.append(candidate)

        return sorted(selected_windows, key=lambda w: w["start_time"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    retention = RetentionService()
    sample_data = [
        {"start_time": 0.0, "end_time": 10.0, "value": 0.2},
        {"start_time": 10.0, "end_time": 20.0, "value": 0.85},
        {"start_time": 20.0, "end_time": 30.0, "value": 0.3},
        {"start_time": 30.0, "end_time": 40.0, "value": 0.95},
        {"start_time": 40.0, "end_time": 50.0, "value": 0.4},
    ]
    norm = retention.normalize_heatmap_points(sample_data)
    windows = retention.detect_peak_windows(norm, min_duration=15.0, max_duration=25.0)
    logger.info("Janelas de pico detectadas no teste: %s", windows)
