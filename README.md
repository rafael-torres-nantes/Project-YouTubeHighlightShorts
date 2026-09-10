# Project-YouTubeHighlightShorts

## 👨‍💻 Projeto desenvolvido por:
[Rafael Torres Nantes](https://github.com/rafael-torres-nantes)

## Índice

* [📚 Contextualização do projeto](#-contextualização-do-projeto)
* [🛠️ Tecnologias/Ferramentas utilizadas](#%EF%B8%8F-tecnologiasferramentas-utilizadas)
* [🖥️ Funcionamento do sistema](#%EF%B8%8F-funcionamento-do-sistema)
   * [🧩 Parte 1 - Backend](#parte-1---backend)
* [🔀 Arquitetura da aplicação](#arquitetura-da-aplicação)
* [📁 Estrutura do projeto](#estrutura-do-projeto)
* [📌 Como executar o projeto](#como-executar-o-projeto)
* [🕵️ Dificuldades Encontradas](#%EF%B8%8F-dificuldades-encontradas)

## 📚 Contextualização do projeto

O **Project-YouTubeHighlightShorts** é um pipeline inteligente projetado para automatizar a extração e transformação de vídeos longos do YouTube em cortes verticais de alto engajamento (Shorts, Reels, TikTok). O sistema combina a **análise da curva de retenção bruta (heatmap Most Replayed)** com **análise semântica por LLM** e transcrição refinada word-level, gerando vídeos 9:16 com fundo desfocado e legendas dinâmicas perfeitamente sincronizadas.

## 🛠️ Tecnologias/Ferramentas utilizadas

[<img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white">](https://www.python.org/)
[<img src="https://img.shields.io/badge/FFmpeg-007808?logo=ffmpeg&logoColor=white">](https://ffmpeg.org/)
[<img src="https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white">](https://github.com/)

## 🖥️ Funcionamento do sistema

### 🧩 Parte 1 - Backend

O backend foi estruturado em módulos orientados a serviços e classes especializadas:

* **Configurações**: `config/settings.py` — Carrega dinamicamente caminhos de binários e diretórios de trabalho sem hardcoding.
* **Download e Heatmap**: `services/download_service.py` — Extrai os pontos brutos do gráfico de retenção do player do YouTube e baixa os fluxos de áudio e vídeo via `yt-dlp`.
* **Retenção**: `services/retention_service.py` — Normaliza curvas de engajamento e detecta picos estatísticos com `scipy.signal.find_peaks`.
* **Transcrição**: `services/transcription_service.py` — Gera timestamps por palavra via `faster-whisper`.
* **Curadoria**: `services/curation_service.py` — Avalia ganchos e coerência narrativa usando LLM estruturado (JSON mode).
* **Edição de Vídeo**: `services/video_editor_service.py` — Corta sem perda de sincronia, aplica enquadramento 9:16 e queima legendas estilizadas `.ass`.
* **Controlador**: `controllers/pipeline_controller.py` — Orquestra a execução completa do pipeline.

## 🔀 Arquitetura da aplicação

1. O usuário submete uma URL do YouTube através da interface CLI (`main.py`).
2. O `DownloadService` extrai os dados brutos de retenção pública (Most Replayed) e faz o download dos fluxos de vídeo (1080p) e áudio isolado.
3. O `RetentionService` filtra e detecta janelas temporais de alto impacto.
4. O áudio é transcrito em nível de palavra pelo `TranscriptionService` e correlacionado à retenção temporal.
5. O `CurationService` envia o contexto estruturado para o LLM selecionar trechos coerentes (30 a 60 segundos) com ganchos fortes nos primeiros 3 segundos.
6. O `VideoEditorService` processa os cortes via FFmpeg, aplicando padding com desfoque e renderizando as legendas.

## 📁 Estrutura do projeto

```
.
├── config/
│   ├── __init__.py
│   └── settings.py
├── controllers/
│   ├── __init__.py
│   └── pipeline_controller.py
├── services/
│   ├── __init__.py
│   ├── download_service.py
│   ├── retention_service.py
│   ├── transcription_service.py
│   ├── curation_service.py
│   └── video_editor_service.py
├── utils/
│   ├── __init__.py
│   └── file_utils.py
├── docs/
│   ├── current-state/
│   │   └── app-architecture.md
│   ├── planning/
│   │   ├── risks.md
│   │   └── open-questions.md
│   └── implementation/
│       └── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py
└── README.md
```

## 📌 Como executar o projeto

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/rafael-torres-nantes/Project-YouTubeHighlightShorts.git
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   ```

5. **Execute a pipeline:**
   ```bash
   python main.py --url "<URL_DO_YOUTUBE>" --max-clips 3 --output-dir "./output"
   ```

## 🕵️ Dificuldades Encontradas

- **Disponibilidade do Gráfico de Calor:** Nem todos os vídeos do YouTube possuem o array de heatmap consolidado publicamente (especialmente vídeos muito recentes ou com poucas visualizações). Foi necessário estruturar fallback semântico robusto no módulo de retenção e curadoria.
- **Sincronia Estrita em Recortes FFmpeg:** Cortar vídeos com base apenas em timestamps pode causar travamento de vídeo se os keyframes (I-frames) não forem reencodados adequadamente. A solução foi aplicar reconstrução precisa de frames mantendo desfoque vertical adaptativo.
