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

## Artefactos de Java descargados en E:\vera-data (Tarea 6)

Autorizados expresamente por la persona responsable. Ninguno está bajo control de versiones.

| Ruta | Tamaño | Contenido |
|---|---|---|
| `E:\vera-data\dl\apache-maven-3.9.9-bin.zip` (y `.sha512`) | 8,8 MiB | Archivo original de Maven, de `archive.apache.org/dist/maven/maven-3/3.9.9/binaries/` |
| `E:\vera-data\maven` | 11 MiB | Apache Maven 3.9.9, portátil |
| `E:\vera-data\m2` | 354 MiB | Repositorio local de Maven (`-Dmaven.repo.local`) |
| `E:\vera-data\commons-lang` | 56 MiB | Clon de `https://github.com/apache/commons-lang` en el commit `89bb30909bf873d75f5e06d144f9b2e72d74c076` |
| `E:\vera-data\go-offline.log`, `test-compile.log` | pequeño | Registros del calentamiento |

Checksum SHA-512 de `apache-maven-3.9.9-bin.zip` (coincide con el publicado por Apache):
`8beac8d11ef208f1e2a8df0682b9448a9a363d2ad13ca74af43705549e72e74c9378823bf689287801cbbfc2f6ea9596201d19ccacfdfb682ee8a2ff4c4418ba`

## Limpieza al terminar el experimento

1. Detener el servidor del puerto 11435.
2. Borrar `E:\ollama-vera` y `E:\vera-data` por completo.
3. Confirmar con `Get-PSDrive E` que se recupera el espacio.

Esta limpieza se realiza solo previa confirmación expresa de la persona responsable.
