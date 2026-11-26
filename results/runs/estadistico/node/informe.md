ejecuciones=2400 invalidas=0 tmp_sin_cerrar=0

# Informe del bloque estadistico

Ejecuciones: 2400 (válidas: 2400; planificadas: 2400)

## Condiciones declaradas

- Versión del prompt en los registros: vera01-p1 (prevista para el bloque: `vera01-p1`).
- Motor de `gemma4:e4b`: ollama en http://127.0.0.1:11431.
- Motor de `llama3.1:8b`: ollama en http://127.0.0.1:11431.
- Motor de `qwen2.5-coder:7b`: ollama en http://127.0.0.1:11434.
- Motor de `qwen3:8b`: ollama en http://127.0.0.1:11434.
- Temperatura: 0.7.
- num_ctx: 8192.
- num_predict: 2048.
- keep_alive: 30m.
- La versión del servidor del motor no consta en los registros; la del entorno se documenta en docs/entorno-vera01.md.

## node

| Modelo | Condición | Tasa del runner | Tasa sustantiva (REAL) |
|---|---|---|---|
| gemma4:e4b | baseline | 96/300 (32%) | 89/300 (30%) |
| gemma4:e4b | repair | 194/300 (65%) | 173/300 (58%) |
| llama3.1:8b | baseline | 105/300 (35%) | 105/300 (35%) |
| llama3.1:8b | repair | 142/300 (47%) | 141/300 (47%) |
| qwen2.5-coder:7b | baseline | 53/300 (18%) | 53/300 (18%) |
| qwen2.5-coder:7b | repair | 92/300 (31%) | 87/300 (29%) |
| qwen3:8b | baseline | 149/300 (50%) | 149/300 (50%) |
| qwen3:8b | repair | 195/300 (65%) | 195/300 (65%) |

| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens | Inválidas |
|---|---|---|---|---|
| gemma4:e4b | sí (+0.28 [+0.20, +0.35]) | 10% | 4.61 | 0 |
| llama3.1:8b | sí (+0.12 [+0.04, +0.20]) | 0% | 4.89 | 0 |
| qwen2.5-coder:7b | sí (+0.11 [+0.05, +0.18]) | 3% | 5.87 | 0 |
| qwen3:8b | sí (+0.15 [+0.07, +0.23]) | 0% | 3.61 | 0 |

Ejecuciones inválidas (excluidas de toda tasa): 0

## Comparación con la tesis

Fuente: tesis de máster (UNED, 2026), citada en docs/research.md; resumen en docs/research.md. La tesis es de Java: no se comparan otros lenguajes. No se afirma coincidencia; una cifra que no consta publicada se marca "no verificable" y no se sustituye por ninguna estimación.

No hay ejecuciones de Java: no hay cifra comparable.

## Límites de lectura

- **Cota de falsos REAL.** `REAL` procede de una auditoría estática (el test contiene `@Test`/aserciones y llama al método focal), no de una ejecución ni de un mutation score. Las auditorías estáticas son conservadoras frente a REAL en los casos que cierran (ante la duda no lo conceden), pero los casos que documentan como abiertos aún pueden inflar REAL; ese posible exceso de falsos REAL no está cuantificado.
  - Node: el análisis es textual; no cierra condiciones falsas en tiempo de ejecución, `.then(ok, err)` que traga, helpers importados ni alias dinámicos; véase "Known limits of the static Node audit" de docs/entorno-vera01.md.
- **No independencia.** Los intervalos de Newcombe tratan las ejecuciones como independientes, pero comparten método focal (mismos métodos en cada celda y repeticiones del mismo método), modelo y comando de validación, y las condiciones se emparejan por método. Los intervalos son por ello optimistas (más estrechos de lo debido); en el bloque determinista las repeticiones, además, no son independientes.
- Una sola máquina, un solo contexto (`num_ctx` 8192), prompts reconstruidos, sin mutation score. Las ejecuciones con `valid=False` quedan fuera de toda tasa.
