# Informe del bloque estadistico + ampliacion

Ejecuciones: 3000 (válidas: 3000; planificadas: 3000)

## Condiciones declaradas

- Versión del prompt en los registros: vera01-p1 (vigente en el código: `vera01-p1`).
- Motor de `gemma4:e4b`: ollama en http://127.0.0.1:11435.
- Motor de `llama3.1:8b`: ollama en http://127.0.0.1:11435.
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
| gemma4:e4b | baseline | 19/300 (6%) | 18/300 (6%) |
| gemma4:e4b | repair | 55/300 (18%) | 55/300 (18%) |
| llama3.1:8b | baseline | 25/300 (8%) | 25/300 (8%) |
| llama3.1:8b | repair | 160/300 (53%) | 160/300 (53%) |
| ornith-1.5:9b | baseline | 78/300 (26%) | 75/300 (25%) |
| ornith-1.5:9b | repair | 201/300 (67%) | 192/300 (64%) |
| qwen2.5-coder:7b | baseline | 97/300 (32%) | 97/300 (32%) |
| qwen2.5-coder:7b | repair | 176/300 (59%) | 176/300 (59%) |
| qwen3:8b | baseline | 0/300 (0%) | 0/300 (0%) |
| qwen3:8b | repair | 224/300 (75%) | 224/300 (75%) |

| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens | Inválidas |
|---|---|---|---|---|
| gemma4:e4b | sí (+0.12 [+0.07, +0.18]) | 1% | 6.99 | 0 |
| llama3.1:8b | sí (+0.45 [+0.38, +0.51]) | 0% | 5.49 | 0 |
| ornith-1.5:9b | sí (+0.39 [+0.31, +0.46]) | 4% | 4.38 | 0 |
| qwen2.5-coder:7b | sí (+0.26 [+0.18, +0.34]) | 0% | 4.19 | 0 |
| qwen3:8b | sí (+0.75 [+0.69, +0.79]) | 0% | 4.48 | 0 |

Ejecuciones inválidas (excluidas de toda tasa): 0

## Comparación con la tesis

Fuente: tesis de González Sánchez (UNED, 2026), citada en docs/research.md; resumen en docs/research.md. La tesis es de Java: no se comparan otros lenguajes. No se afirma coincidencia; una cifra que no consta publicada se marca "no verificable" y no se sustituye por ninguna estimación.

| Modelo | Tesis ingenua (base → rep.) | Tesis sustantiva (base → rep.) | Réplica, runner | Réplica, REAL |
|---|---|---|---|---|
| gemma4:e4b | 31.3 % → 66.7 % | 31.3 % → 65.3 % | 6.3% → 18.3% | 6.0% → 18.3% |
| llama3.1:8b | 17.7 % → 54.7 % | 17.7 % → 22.3 % | 8.3% → 53.3% | 8.3% → 53.3% |
| ornith-1.5:9b | no verificable | no verificable | 26.0% → 67.0% | 25.0% → 64.0% |
| qwen2.5-coder:7b | 25.7 % → 46.3 % | 25.0 % → 45.0 % | 32.3% → 58.7% | 32.3% → 58.7% |
| qwen3:8b | 42.7 % → 52.3 % | 42.7 % → 52.0 % | 0.0% → 74.7% | 0.0% → 74.7% |

## Límites de lectura

- **Cota de falsos REAL.** `REAL` procede de una auditoría estática (el test contiene `@Test`/aserciones y llama al método focal), no de una ejecución ni de un mutation score. Las auditorías estáticas son conservadoras frente a REAL en los casos que cierran (ante la duda no lo conceden), pero los casos que documentan como abiertos aún pueden inflar REAL; ese posible exceso de falsos REAL no está cuantificado.
  - Java: la auditoría es estructural; una aserción puede ser vacua (no mide el poder de detección).
- **Prompt sin el paquete de la clase (Java).** El prompt reconstruido exige `package org.generated;` e indica la clase bajo prueba solo por su nombre (por ejemplo `BooleanUtils`), sin su paquete `org.apache.commons.lang3`. El modelo debe deducirlo por sí mismo: buena parte de los fallos del primer intento son errores de compilación por una importación equivocada y no de calidad de los tests, de modo que la tasa mide también si el modelo conoce Commons Lang. Afecta de forma muy desigual a los modelos (véase docs/findings.md) y las tasas absolutas, en particular el 0 % de baseline de qwen3:8b, deben leerse con esta salvedad.
- **No independencia.** Los intervalos de Newcombe tratan las ejecuciones como independientes, pero comparten método focal (mismos métodos en cada celda y repeticiones del mismo método), modelo y comando de validación, y las condiciones se emparejan por método. Los intervalos son por ello optimistas (más estrechos de lo debido); en el bloque determinista las repeticiones, además, no son independientes.
- Una sola máquina, un solo contexto (`num_ctx` 8192), prompts reconstruidos, sin mutation score. Las ejecuciones con `valid=False` quedan fuera de toda tasa.