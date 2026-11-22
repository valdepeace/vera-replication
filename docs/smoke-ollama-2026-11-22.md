# Prueba de humo de Ollama con los cuatro modelos de la tesis

**Estado:** medición puntual del 22 de noviembre de 2026. Una muestra por celda; no son tasas ni un benchmark.

## Entorno

- Ryzen 7 5700G, 47,3 GB de RAM, RTX 3060 Ti de 8 GB (driver 610.88).
- Ollama 0.40.13. Servidor 11434 (modelos en `G:`) y servidor 11435 (modelos en `E:\ollama-vera\models`).
- Petición idéntica: generar un fichero pytest para una función `chunk_text` de siete líneas. `/api/chat`, `think: false`, `num_ctx` 4096, `num_predict` 512, temperatura 0,7, semilla 1.
- Cada modelo se midió en frío (primera carga) y en caliente (segunda petición).

## Resultados

| Modelo | Servidor | En memoria de GPU (`ollama ps`) | Carga en frío | tok/s en caliente | Respuesta en caliente |
|---|---|---:|---:|---:|---:|
| qwen2.5-coder:7b | 11434 | 4,8 GB | 44,9 s | 77,6 | 4,0 s |
| qwen3:8b | 11434 | 5,6 GB | 47,3 s | 71,3 | 4,9 s |
| llama3.1:8b | 11435 | 5,3 GB | 3,4 s | 76,1 | 5,0 s |
| gemma4:e4b | 11435 | 0,4 GB (sin explicar) | 85,0 s | 161,2 | 4,2 s |

## Anomalías sin resolver

- `gemma4:e4b` declara 0,4 GB residentes pese a pesar 6,6 GB en disco, y generó el tope de 512 tokens en ambas peticiones, por lo que su salida quedó truncada. No se ha investigado la causa; no se usa como dato fiable hasta hacerlo.
- La carga en frío de los modelos de `G:` (unos 45 s) es muy superior a la del modelo de `E:` (3,4 s). Hipótesis no verificada: el disco `G:` es más lento. En frío, `qwen3:8b` generó a 20,7 tok/s frente a 71,3 en caliente.

## Estimación gruesa

Con unos 4-5 s por generación en caliente, las llamadas al modelo de las 2.400 ejecuciones del bloque estadístico suponen del orden de 7 a 10 horas. No incluye Maven ni los reintentos de reparación con prompts más largos, y se basa en una única muestra.
