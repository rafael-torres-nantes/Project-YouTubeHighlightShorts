# App Architecture - Project-YouTubeHighlightShorts

## Visao Geral
Pipeline de extracao de melhores momentos de videos longos do YouTube e reformatacao em cortes verticais de alta conversao (9:16) com legendas dinamicas.

## Modulos e Responsabilidades
- `config/settings.py`: Leitura de variaveis de ambiente via dotenv (caminhos de binarios do yt-dlp, ffmpeg, ffprobe, chaves de API e diretorios de temp).
- `services/download_service.py`: Obtencao do JSON bruto de heatmap e download desacoplado de audio/video.
- `services/retention_service.py`: Analise estatistica e extracao de janelas temporais de interesse.
- `services/transcription_service.py`: Geracao de texto e timestamps precisos por palavra.
- `services/curation_service.py`: Avaliacao de gancho, duracao e coerencia semantica via LLM.
- `services/video_editor_service.py`: Montagem audiovisual em 9:16 com background blur e legendas estilizadas .ass.
- `controllers/pipeline_controller.py`: Orquestrador de alto nivel desacoplado da CLI.
