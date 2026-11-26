ejecuciones=80 invalidas=0 tmp_sin_cerrar=0

# Informe del bloque determinista

Ejecuciones: 80 (válidas: 80; planificadas: 80)

## Condiciones declaradas

- Versión del prompt en los registros: vera01-p1 (prevista para el bloque: `vera01-p1`).
- Motor de `llama3.1:8b`: ollama en http://127.0.0.1:11431.
- Motor de `qwen2.5-coder:7b`: ollama en http://127.0.0.1:11434.
- Temperatura: 0.0.
- num_ctx: 8192.
- num_predict: 2048.
- keep_alive: 30m.
- La versión del servidor del motor no consta en los registros; la del entorno se documenta en docs/entorno-vera01.md.

Estabilidad entre repeticiones: 95%

## node

| Modelo | Condición | Tasa del runner | Tasa sustantiva (REAL) |
|---|---|---|---|
| llama3.1:8b | baseline | 11/20 (55%) | 11/20 (55%) |
| llama3.1:8b | repair | 13/20 (65%) | 13/20 (65%) |
| qwen2.5-coder:7b | baseline | 6/20 (30%) | 6/20 (30%) |
| qwen2.5-coder:7b | repair | 12/20 (60%) | 12/20 (60%) |

| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens | Inválidas |
|---|---|---|---|---|
| llama3.1:8b | no (+0.10 [-0.19, +0.37]) | 0% | 4.30 | 0 |
| qwen2.5-coder:7b | no (+0.30 [-0.01, +0.54]) | 0% | 6.24 | 0 |

Ejecuciones inválidas (excluidas de toda tasa): 0

## Comparación con la tesis

Fuente: tesis de máster (UNED, 2026), citada en docs/research.md; resumen en docs/research.md. La tesis es de Java: no se comparan otros lenguajes. No se afirma coincidencia; una cifra que no consta publicada se marca "no verificable" y no se sustituye por ninguna estimación.

No hay ejecuciones de Java: no hay cifra comparable.

## Límites de lectura

- **Cota de falsos REAL.** `REAL` procede de una auditoría estática (el test contiene `@Test`/aserciones y llama al método focal), no de una ejecución ni de un mutation score. Las auditorías estáticas son conservadoras frente a REAL en los casos que cierran (ante la duda no lo conceden), pero los casos que documentan como abiertos aún pueden inflar REAL; ese posible exceso de falsos REAL no está cuantificado.
  - Node: el análisis es textual; no cierra condiciones falsas en tiempo de ejecución, `.then(ok, err)` que traga, helpers importados ni alias dinámicos; véase "Known limits of the static Node audit" de docs/entorno-vera01.md.
- **No independencia.** Los intervalos de Newcombe tratan las ejecuciones como independientes, pero comparten método focal (mismos métodos en cada celda y repeticiones del mismo método), modelo y comando de validación, y las condiciones se emparejan por método. Los intervalos son por ello optimistas (más estrechos de lo debido); en el bloque determinista las repeticiones, además, no son independientes.
- Una sola máquina, un solo contexto (`num_ctx` 8192), prompts reconstruidos, sin mutation score. Las ejecuciones con `valid=False` quedan fuera de toda tasa.

