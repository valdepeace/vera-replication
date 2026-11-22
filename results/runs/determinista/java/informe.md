# Informe del bloque determinista

Ejecuciones: 80 (válidas: 80)

Estabilidad entre repeticiones: 90%

## java

| Modelo | Condición | Tasa del runner | Tasa sustantiva (REAL) |
|---|---|---|---|
| llama3.1:8b | baseline | 6/20 (30%) | 6/20 (30%) |
| llama3.1:8b | repair | 17/20 (85%) | 17/20 (85%) |
| qwen2.5-coder:7b | baseline | 8/20 (40%) | 8/20 (40%) |
| qwen2.5-coder:7b | repair | 17/20 (85%) | 17/20 (85%) |

| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens | Inválidas |
|---|---|---|---|---|
| llama3.1:8b | sí (+0.55 [+0.25, +0.73]) | 0% | 3.63 | 0 |
| qwen2.5-coder:7b | sí (+0.45 [+0.15, +0.66]) | 0% | 2.92 | 0 |

Ejecuciones inválidas (excluidas de toda tasa): 0

