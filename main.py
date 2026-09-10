import argparse
import logging
import os
import sys
from tqdm import tqdm

from controllers.pipeline_controller import PipelineController

# Configuracao de encoding para Windows CLI
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("YouTubeHighlightShorts")


def parse_arguments() -> argparse.Namespace:
    """Configura e valida os argumentos da linha de comando.

    Returns:
        Namespace com os argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Transforma videos do YouTube em Shorts verticais (9:16) com analise hibrida de retencao e IA."
    )
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL do video no YouTube (ex: https://www.youtube.com/watch?v=...)",
    )
    parser.add_argument(
        "--max-clips",
        type=int,
        default=3,
        help="Numero maximo de cortes verticais a serem gerados (padrao: 3).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Diretorio final onde os clipes renderizados serao salvos (padrao: ./output).",
    )
    return parser.parse_args()


def main() -> None:
    """Entrypoint principal da aplicacao CLI."""
    args = parse_arguments()

    print("\n" + "=" * 60)
    print("🎬 YouTube Highlight Shorts - Pipeline Hibrido de Cortes Verticais")
    print("=" * 60)
    print(f"📌 URL Alvo: {args.url}")
    print(f"🎯 Meta de Cortes: {args.max_clips}")
    print(f"📁 Diretorio de Saida: {os.path.abspath(args.output_dir)}\n")

    controller = PipelineController()

    with tqdm(total=100, desc="Progresso Geral", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}% [{elapsed}]") as pbar:
        last_val = 0

        def update_progress(message: str, current_percentage: int) -> None:
            nonlocal last_val
            diff = current_percentage - last_val
            if diff > 0:
                pbar.update(diff)
                last_val = current_percentage
            pbar.set_description(f"Etapa: {message[:40]}")

        try:
            results = controller.execute_pipeline(
                youtube_url=args.url,
                max_clips=args.max_clips,
                output_dir=args.output_dir,
                progress_callback=update_progress,
            )

            print("\n" + "✨" * 30)
            print("🚀 Processamento Concluido com Sucesso!\n")
            print(f"Foram gerados {len(results)} clipes verticais:")
            for idx, clip in enumerate(results, start=1):
                print(f"\n[{idx}] {clip.get('title')}")
                print(f"    ⏱️  Duracao: {clip.get('duration')}s ({clip.get('start_time')}s -> {clip.get('end_time')}s)")
                print(f"    🔥 Viral Score: {clip.get('viral_score')}/10.0")
                print(f"    💡 Gancho: {clip.get('hook_summary')}")
                print(f"    📁 Arquivo: {clip.get('rendered_path')}")
            print("\n" + "=" * 60 + "\n")

        except Exception as exc:
            logger.error("Falha critica na execucao da pipeline: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
