ejecuciones=3000 invalidas=0 tmp_sin_cerrar=0

# Informe del bloque estadistico-p2

Ejecuciones: 3000 (válidas: 3000; planificadas: 3000)

## Condiciones declaradas

- Versión del prompt en los registros: vera01-p2 (prevista para el bloque: `vera01-p2`).
- Motor de `gemma4:e4b`: ollama en http://127.0.0.1:11431.
- Motor de `llama3.1:8b`: ollama en http://127.0.0.1:11431.
- Motor de `ornith-1.5:9b`: ollama en http://127.0.0.1:11431.
- Motor de `qwen2.5-coder:7b`: ollama en http://127.0.0.1:11434.
- Motor de `qwen3:8b`: ollama en http://127.0.0.1:11434.
- Temperatura: 0.7.
- num_ctx: 8192.
- num_predict: 2048.
- keep_alive: 30m.
- La versión del servidor del motor no consta en los registros; la del entorno se documenta en docs/entorno-vera01.md.

## java

| Modelo | Condición | Tasa del runner | Tasa sustantiva (REAL) |
|---|---|---|---|
| gemma4:e4b | baseline | 172/300 (57%) | 172/300 (57%) |
| gemma4:e4b | repair | 236/300 (79%) | 236/300 (79%) |
| llama3.1:8b | baseline | 154/300 (51%) | 153/300 (51%) |
| llama3.1:8b | repair | 189/300 (63%) | 188/300 (63%) |
| ornith-1.5:9b | baseline | 129/300 (43%) | 129/300 (43%) |
| ornith-1.5:9b | repair | 235/300 (78%) | 233/300 (78%) |
| qwen2.5-coder:7b | baseline | 166/300 (55%) | 166/300 (55%) |
| qwen2.5-coder:7b | repair | 211/300 (70%) | 211/300 (70%) |
| qwen3:8b | baseline | 160/300 (53%) | 102/300 (34%) |
| qwen3:8b | repair | 207/300 (69%) | 125/300 (42%) |

| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens | Inválidas |
|---|---|---|---|---|
| gemma4:e4b | sí (+0.21 [+0.14, +0.28]) | 0% | 3.02 | 0 |
| llama3.1:8b | sí (+0.12 [+0.04, +0.19]) | 1% | 3.87 | 0 |
| ornith-1.5:9b | sí (+0.35 [+0.27, +0.42]) | 1% | 4.00 | 0 |
| qwen2.5-coder:7b | sí (+0.15 [+0.07, +0.22]) | 0% | 3.28 | 0 |
| qwen3:8b | no (+0.08 [-0.00, +0.15]) | 38% | 3.20 | 0 |

Ejecuciones inválidas (excluidas de toda tasa): 0

## Comparación con la tesis

Fuente: tesis de máster (UNED, 2026), citada en docs/research.md; resumen en docs/research.md. La tesis es de Java: no se comparan otros lenguajes. No se afirma coincidencia; una cifra que no consta publicada se marca "no verificable" y no se sustituye por ninguna estimación.

| Modelo | Tesis ingenua (base → rep.) | Tesis sustantiva (base → rep.) | Réplica, runner | Réplica, REAL |
|---|---|---|---|---|
| gemma4:e4b | 31.3 % → 66.7 % | 31.3 % → 65.3 % | 57.3% → 78.7% | 57.3% → 78.7% |
| llama3.1:8b | 17.7 % → 54.7 % | 17.7 % → 22.3 % | 51.3% → 63.0% | 51.0% → 62.7% |
| ornith-1.5:9b | no verificable | no verificable | 43.0% → 78.3% | 43.0% → 77.7% |
| qwen2.5-coder:7b | 25.7 % → 46.3 % | 25.0 % → 45.0 % | 55.3% → 70.3% | 55.3% → 70.3% |
| qwen3:8b | 42.7 % → 52.3 % | 42.7 % → 52.0 % | 53.3% → 69.0% | 34.0% → 41.7% |

## Límites de lectura

- **Cota de falsos REAL.** `REAL` procede de una auditoría estática (el test contiene `@Test`/aserciones y llama al método focal), no de una ejecución ni de un mutation score. Las auditorías estáticas son conservadoras frente a REAL en los casos que cierran (ante la duda no lo conceden), pero los casos que documentan como abiertos aún pueden inflar REAL; ese posible exceso de falsos REAL no está cuantificado.
  - Java: la auditoría es estructural; una aserción puede ser vacua (no mide el poder de detección).
- **No independencia.** Los intervalos de Newcombe tratan las ejecuciones como independientes, pero comparten método focal (mismos métodos en cada celda y repeticiones del mismo método), modelo y comando de validación, y las condiciones se emparejan por método. Los intervalos son por ello optimistas (más estrechos de lo debido); en el bloque determinista las repeticiones, además, no son independientes.
- Una sola máquina, un solo contexto (`num_ctx` 8192), prompts reconstruidos, sin mutation score. Las ejecuciones con `valid=False` quedan fuera de toda tasa.

