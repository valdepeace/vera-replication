# Registro de corridas VERA

- `vera01-real-2026-11-21T17-21-17.724Z-E9Hig2`: corrida con cuatro métodos copiados de `poc-ante`; la auditoría manual descarta dos pases Node que ocultaban fallos de aserción. Véase [findings.md](../docs/findings.md) y el manifiesto de fuentes.
- `vera01-2026-11-21T14-05-08.057Z-aBzg7a`: primera corrida completa con `qwen3.5:4b`, resumida en [findings.md](../docs/findings.md).
- `vera01-2026-11-21T16-15-12.346Z-BLv52y`: segundo piloto completo con el alias local `local-coding-task-lab-qwen2.5-coder-7b:4k`; también resumido y auditado en [findings.md](../docs/findings.md).
- `vera01-2026-11-21T13-57-56.013Z-6dKPRJ`: intento parcial con `/api/generate`, interrumpido cuando algunas respuestas llegaron vacías. Excluido.
- `vera01-2026-11-21T13-56-50.417Z-J2jiQA` y `vera01-2026-11-21T13-57-36.269Z-yTlXkq`: intentos con `qwen2.5-coder:7b` que fallaron al cargar por falta de memoria. No contienen corridas válidas.

Una corrida está completa cuando contiene `summary.json`. Las carpetas sin ese archivo son intentos fallidos o interrumpidos y no deben agregarse a las métricas.
