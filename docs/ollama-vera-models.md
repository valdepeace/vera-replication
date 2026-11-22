# Inventario de modelos Ollama descargados para VERA

Registro de lo que VERA ha descargado, para poder retirarlo al terminar. Nada de lo que figura aquí debe quedar en disco sin uso.

## Servidor secundario

- Puerto: `127.0.0.1:11435`.
- Directorio de modelos: `E:\ollama-vera\models` (no se modifica la variable global `OLLAMA_MODELS=G:\ollama\models`).
- Arranque: `OLLAMA_HOST=127.0.0.1:11435` y `OLLAMA_MODELS=E:\ollama-vera\models`, con `ollama serve`.

## Modelos descargados por VERA (en E:)

| Modelo | Origen | Fecha | Motivo |
|---|---|---|---|
| `llama3.1:8b` (8,0 B, Q4_K_M, 4,9 GB) | registro de Ollama | 2026-11-22 | Modelo del bloque estadístico de la tesis |
| `gemma4:e4b` (7,5 B con embeddings, Q4_K_M, 6,6 GB) | registro de Ollama | 2026-11-22 | Modelo del bloque estadístico de la tesis |

Ocupación total en `E:\ollama-vera\models`: unos 10,7 GB (10.972 MiB). Espacio libre en `E:` tras la descarga: 68,7 GB.

## Modelos preexistentes que VERA reutiliza (en G:, servidor 11434)

`qwen2.5-coder:7b`, `qwen3:8b`. No se duplican. VERA no los descargó y no debe borrarlos.

## Limpieza al terminar el experimento

1. Detener el servidor del puerto 11435.
2. Borrar `E:\ollama-vera` por completo.
3. Confirmar con `Get-PSDrive E` que se recupera el espacio.

Esta limpieza se realiza solo previa confirmación expresa de la persona responsable.
