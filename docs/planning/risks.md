# Riscos Identificados

| Risco | Impacto | Status | Mitigacao |
|---|---|---|---|
| Ausencia de heatmap no video | Alto | ⚠️ Parcial | Implementar fallback automatico baseado puramente em densidade semantica e picos de audio. |
| Incompatibilidade de codificacao FFmpeg no Windows | Medio | ✅ Resolvido | Parametrizar caminhos de binarios via settings.py lendo variaveis de ambiente padronizadas. |
| Perda de sincronia em cortes por timestamp | Alto | ⚠️ Parcial | Aplicar recodificacao de stream em vez de copia crua de stream (`-c copy`) nos pontos de corte. |
