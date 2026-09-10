from typing import Any, Dict, List, Optional
import json
import logging
import os
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class ClipHighlight(BaseModel):
    """Schema para cada corte de destaque retornado pelo LLM."""

    start_time: float = Field(
        description="Tempo inicial em segundos. DEVE coincidir EXATAMENTE com o valor de 'start' do primeiro segmento de fala escolhido."
    )
    end_time: float = Field(
        description="Tempo final em segundos. DEVE coincidir EXATAMENTE com o valor de 'end' do ultimo segmento onde a frase e o pensamento foram 100% concluidos."
    )
    title: str = Field(description="Titulo atrativo e impactante para o Short/Reel.")
    viral_score: float = Field(description="Pontuacao de 0.0 a 10.0 baseada no gancho e retencao.")
    hook_summary: str = Field(description="Breve explicacao do gancho presente nos primeiros 3 segundos.")
    reasoning: str = Field(
        description="Transcreva aqui as ultimas 5 palavras ditas pelo orador para comprovar que a frase terminou de forma completa (com ponto final) e sem corte abrupto."
    )


class HighlightCuratorResponse(BaseModel):
    """Container para a lista de clipes selecionados pelo LLM."""

    clips: List[ClipHighlight]


class CurationService:
    """Executa a curadoria semantica de clipes via LLM estruturado com Gemini API."""

    MODEL_NAME = "gemini-3.6-flash"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None

    def get_client(self) -> genai.Client:
        """Obtem ou instancia o cliente da API do Gemini sob demanda.

        Returns:
            Cliente autenticado do SDK google-genai.

        Raises:
            ValueError: Se a chave de API nao for informada ou localizada no ambiente.
        """
        if self._client is not None:
            return self._client

        if not self._api_key:
            raise ValueError("GEMINI_API_KEY nao foi configurada no ambiente ou .env.")

        self._client = genai.Client(api_key=self._api_key)
        return self._client

    def curate_highlights(
        self,
        enriched_segments: List[Dict[str, Any]],
        peak_windows: List[Dict[str, Any]],
        max_clips: int = 3,
        min_clip_duration: float = 30.0,
        max_clip_duration: float = 60.0,
    ) -> List[Dict[str, Any]]:
        """Seleciona os melhores clipes correlacionando dados de retencao e analise semantica.

        Avalia criterios estritos: gancho forte no inicio, conclusao gramatical completa da frase
        sem cortar palavras ao meio e duracao alvo para formatos curtos.

        Args:
            enriched_segments: Segmentos transcritos enriquecidos com score de retencao.
            peak_windows: Janelas candidatas detectadas estatisticamente pelo scipy.
            max_clips: Quantidade maxima de clipes solicitada.
            min_clip_duration: Duracao minima de cada clipe em segundos.
            max_clip_duration: Duracao maxima de cada clipe em segundos.

        Returns:
            Lista de dicionarios com start_time, end_time, title, viral_score e hook_summary.

        Raises:
            RuntimeError: Se houver falha na chamada estruturada do LLM.
        """
        client = self.get_client()

        transcript_context = []
        for s in enriched_segments:
            transcript_context.append(
                {
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"],
                    "avg_retention": s.get("average_engagement", 0.0),
                }
            )

        system_instruction = (
            "Voce e um Editor Senior e Estrategista de Videos Virais especializado em YouTube Shorts, "
            "TikTok e Instagram Reels. Sua principal prioridade e a EXPERIENCIA AUDITIVA DO ESPECTADOR: "
            "um corte que termina no meio de uma frase ou no meio de um pensamento DESTROI o video.\n\n"
            "Regras Estritas de Alinhamento e Conclusao:\n"
            "1. INICIO PERFEITO: 'start_time' DEVE ser exatamente o 'start' do segmento onde uma nova frase ou ideia comeca.\n"
            "2. FIM PERFEITO (INVIOLAVEL): 'end_time' DEVE ser exatamente o 'end' de um segmento onde a pessoa conclui "
            "completamente o raciocinio (pontos finais como '.', '!', '?'). NUNCA termine em conectivos ('mas', 'porque', 'e', 'que', 'quando', 'entao') "
            "ou no meio de uma explicacao inacabada.\n"
            "3. Se necessario estender em 2 a 5 segundos para que a pessoa termine a frase inteira, estenda o 'end_time' ate o encerramento do pensamento.\n"
            f"4. A duracao total (end_time - start_time) deve ficar entre {min_clip_duration} e {max_clip_duration} segundos.\n"
            "5. Gancho forte nos primeiros 3 segundos.\n"
            f"6. Retorne no maximo {max_clips} clipes de altissima qualidade narrativa."
        )

        user_content = {
            "peak_retention_windows": peak_windows,
            "target_max_clips": max_clips,
            "duration_constraints": {"min_seconds": min_clip_duration, "max_seconds": max_clip_duration},
            "transcript_timeline": transcript_context,
        }

        logger.info("Enviando contexto estruturado para curadoria com modelo %s...", self.MODEL_NAME)

        try:
            response = client.models.generate_content(
                model=self.MODEL_NAME,
                contents=json.dumps(user_content, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=HighlightCuratorResponse,
                    temperature=0.1,
                ),
            )

            response_data = json.loads(response.text)
            parsed_response = HighlightCuratorResponse.model_validate(response_data)

            selected_clips = []
            for clip in parsed_response.clips:
                selected_clips.append(
                    {
                        "start_time": clip.start_time,
                        "end_time": clip.end_time,
                        "duration": round(clip.end_time - clip.start_time, 2),
                        "title": clip.title,
                        "viral_score": clip.viral_score,
                        "hook_summary": clip.hook_summary,
                        "reasoning": clip.reasoning,
                    }
                )

            logger.info("Curadoria concluida: %d clipes selecionados com sucesso.", len(selected_clips))
            return selected_clips
        except Exception as exc:
            logger.error("Erro na geracao estruturada de clipes via LLM: %s", exc)
            raise RuntimeError(f"Falha na curadoria semantica: {exc}") from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    curator = CurationService(api_key="mock_key")
    logger.info("Modulo de curadoria carregado para validacao de estrutura.")
