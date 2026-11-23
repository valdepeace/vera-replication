# vera-replication

Réplica, con modelos locales, del efecto de un bucle de **reparación** sobre la generación de tests unitarios Java.
VERA es el acrónimo del proyecto: *Validation · Execution · Repair · Audit*.

> English summary: a local-LLM replication of a validate-and-repair loop for Java unit-test generation
> (Apache Commons Lang). Each model writes JUnit 5 tests; in the `repair` condition it may fix its own
> test up to three times from the compiler or test diagnostic. A static audit separates tests that merely
> pass from tests that actually assert something (`REAL`). Code and analysis are MIT-licensed; the
> documentation is in Spanish.

## Qué se mide

Para cada modelo, método de Commons Lang y repetición se ejecutan dos condiciones con el mismo prompt, los mismos
parámetros y el mismo comando de validación; solo cambia el presupuesto de reparación:

- **baseline**: un intento.
- **repair**: el intento inicial y hasta tres reparaciones, devolviendo al modelo su código y el diagnóstico.

El flujo es de tres nodos (generar o reparar, parsear, validar) con presupuesto acotado, y lo aceptado pasa por una
auditoría estática que decide si el test cuenta como `REAL` (tiene aserciones y llama al método focal).
La referencia es la tesis de máster de María Isabel González Sánchez (UNED, 2026), *Agentic Validate–Repair Workflows
for Local Large Language Models: A Controlled Empirical Evaluation on Automated Unit Test Generation*. Este repositorio
no la redistribuye; véase [docs/research.md](docs/research.md) para la referencia y el resumen metodológico.

## Resultados y lectura

- [docs/findings.md](docs/findings.md): resultados, desviaciones respecto de la tesis y límites.
- [results/runs/](results/runs/): manifiesto e informe de cada bloque.

Conviene leer antes la limitación del prompt: el prompt `vera01-p1` no indica el paquete de la clase bajo prueba, lo que
afecta de forma muy desigual a los modelos y condiciona las tasas absolutas (sección *Limitación del prompt* de
[docs/findings.md](docs/findings.md)).

## Reproducir

Desarrollado y probado en **Windows 11** con una RTX 3060 Ti de 8 GB, Python 3.12, JDK 11, Maven 3.9.9 y Ollama 0.40.13.
No se ha probado en otros sistemas. Las rutas del entorno (`E:\vera-data`, `E:\ollama-vera`) están fijadas en
[src/vera/envinfo.py](src/vera/envinfo.py) y [src/vera/models.py](src/vera/models.py): en otra máquina hay que adaptarlas.
Los pasos de preparación están en [docs/entorno-vera01.md](docs/entorno-vera01.md).

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev,analysis]"
.venv/Scripts/python -m pytest                                   # pruebas unitarias
.venv/Scripts/python scripts/env/check_env.py                    # comprueba el entorno
python -m vera run    --block estadistico --language java        # 2400 ejecuciones, reanudable
python -m vera run    --block ampliacion  --language java        # 600 ejecuciones más (Ornith 1.5 9B)
python -m vera report --block estadistico --with ampliacion --language java
python -m vera run    --block estadistico-p2 --language java     # 3000 ejecuciones con el prompt vera01-p2
```

Los registros crudos (`results/runs/*/*/records/`) **no se versionan**: ocupan decenas de megabytes y se regeneran
ejecutando los bloques. Sí se versionan el `manifest.json` y el informe de cada bloque. El informe se niega a presentar
tasas si faltan ejecuciones del plan o si se mezclan versiones del prompt.

## Modelos

`llama3.1:8b`, `qwen2.5-coder:7b`, `qwen3:8b` y `gemma4:e4b` (bloque estadístico) y `ornith-1.5:9b` (ampliación),
todos en cuantización Q4_K_M, con `num_ctx` 8192 y temperatura 0,7. Los modelos `qwen3-coder:30b` y `qwen3:30b-a3b`
quedaron fuera por no superar la puerta de velocidad de la máquina.

## Licencia

[MIT](LICENSE). La tesis citada y los modelos tienen sus propias licencias.
