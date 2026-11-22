# Entorno de VERA-01

## Versiones verificadas

| Componente | Versión |
|---|---|
| Python | 3.12.10 (`.venv` del proyecto) |
| Java | Temurin 11.0.23 |
| Maven | 3.9.9, portátil en `E:\vera-data\maven` |
| Commons Lang | commit `89bb30909bf873d75f5e06d144f9b2e72d74c076` (3.20.0-SNAPSHOT), en `E:\vera-data\commons-lang` |
| Ollama | 0.40.13 (puertos 11434 y 11435) |
| GPU | NVIDIA GeForce RTX 3060 Ti, 8192 MiB, controlador 610.88 |

Construye con JDK 11 sin necesidad de otro JDK.

## Pasos

1. Descargar `apache-maven-3.9.9-bin.zip` y su `.sha512` de `archive.apache.org`; comprobar el SHA-512 con `sha512sum` antes de descomprimir; extraer en `E:\vera-data\maven`.
2. `git clone https://github.com/apache/commons-lang E:\vera-data\commons-lang` y `git checkout 89bb30909bf873d75f5e06d144f9b2e72d74c076`.
3. Con red, una sola vez, desde el clon: `mvn -B -Dmaven.repo.local=E:/vera-data/m2 dependency:go-offline` (unos 2 min) y `mvn -B -Dmaven.repo.local=E:/vera-data/m2 -DskipTests test-compile` (unos 35 s).
4. Verificar: `.venv/Scripts/python scripts/env/check_env.py` (código 0 si el commit es el fijado, `mvn -o -B -q test-compile` funciona sin red, ambos servidores contestan y están los 4 modelos).

No se toca el `PATH` global ni `%USERPROFILE%\.m2`. La lógica vive en `src/vera/envinfo.py`; `scripts/env/check_env.py` es un envoltorio fino.

## Limpieza final

Previa confirmación expresa: detener el servidor 11435 y borrar `E:\ollama-vera` y `E:\vera-data`. Inventario completo en `docs/ollama-vera-models.md`.
