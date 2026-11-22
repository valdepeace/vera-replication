# Medición de la fase 1 con `num_ctx` 8192 y puerta de calidad

**Estado:** medición del 22 de noviembre de 2026 (Tarea 11). Muestras pequeñas por modelo (1 llamada en frío y 3 en caliente en la medición del motor; 10 llamadas en la puerta); orientan la planificación, no son tasas. No se ha ejecutado ningún bloque de la réplica.

## Entorno y método

- RTX 3060 Ti de 8 GB, Ollama 0.40.13; servidor 11434 (`qwen2.5-coder:7b`, `qwen3:8b`) y 11435 (`llama3.1:8b`, `gemma4:e4b`). Ningún otro modelo se cargó.
- Un único modelo cargado cada vez: antes y después de cada uno se descargó con `keep_alive` 0 y se esperó a que `/api/ps` dejara de listarlo; `nvidia-smi` marcó 11 MiB usados en todas las transiciones.
- Petición: `/api/chat` con el payload de `OllamaEngine.chat` (`think: false`, `format` = `OUTPUT_SCHEMA`), prompt real de generación (`vera.prompts.generation_messages`) de las tareas Java, `num_ctx` 8192, `num_predict` 2048, `keep_alive` "30m", temperatura 0,7.
- Scripts: `scripts/measure_engines.py`, `scripts/measure_maven.py`, `scripts/gate_model.py` (lógica en `src/vera/gate.py`). Los JSON en bruto quedan en `results/fase1/` (fuera del control de versiones).
- tok/s de la medición del motor: `eval_count / eval_duration` (solo generación). tok/s de la puerta: `completion_tokens / (total - carga)`, que incluye la evaluación del prompt y es, por tanto, algo conservadora.

## Motores (`scripts/measure_engines.py`)

| Modelo | Servidor | Carga en frío | tok/s en frío | tok/s en caliente (3 llamadas) | `/api/ps` size / size_vram | VRAM real (`nvidia-smi`) | VRAM tras descargar |
|---|---|---:|---:|---:|---:|---:|---:|
| qwen2.5-coder:7b | 11434 | 43,9 s | 76,3 | 77,6 – 78,0 | 5,15 / 5,15 GB | 5.070 MiB | 11 MiB |
| qwen3:8b | 11434 | 37,3 s | 70,0 | 70,4 – 71,1 | 6,19 / 6,19 GB | 6.082 MiB | 11 MiB |
| llama3.1:8b | 11435 | 65,7 s | 73,8 | 73,9 – 75,5 | 5,82 / 5,82 GB | 5.710 MiB | 11 MiB |
| gemma4:e4b | 11435 | 151,1 s | 146,9 | 134,3 – 161,0 | 0,37 / 0,37 GB | 4.772 MiB | 11 MiB |

Con `num_ctx` 8192 los cuatro modelos declaran `size_vram` = `size` (residencia completa en GPU según `/api/ps`) y `context_length` 8192; ninguno supera los 8 GB por sí solo. Ninguna respuesta de esta medición quedó truncada (`done_reason` = `stop`; máximo 564 tokens).

La carga en frío varía mucho entre corridas: en la puerta, ejecutada minutos después, las primeras cargas costaron 4,4–8,8 s. Lo más probable es la caché de ficheros del sistema operativo, pero no se ha verificado; la carga en frío real tras un reinicio puede ser la de la tabla.

## Maven (`scripts/measure_maven.py`)

Validación con el adaptador real (`JavaMavenAdapter`, Maven 3.9.9 sin red, `-Dtest` limitado al test generado) de un test correcto de `StringUtils.isEmpty`. Todas las validaciones pasaron.

| Comando | Validación | Segundos |
|---|---|---:|
| Completo (Tarea 7), medición de la Tarea 11 | 1.ª (en frío) / 2.ª – 6.ª (mediana; rango) | 21,7 / 19,3; 18,9 – 19,8 |
| Completo (Tarea 7), `measure_maven.py --full`, Tarea 7c | 1.ª / 2.ª – 6.ª | 20,2 / 19,8; 19,4 – 20,5 |
| **Rápido (Tarea 7c)**, `measure_maven.py` | 1.ª / 2.ª – 6.ª | 6,6 / **6,5**; 6,4 – 6,7 |

Desglose del comando completo (registro de Maven con marcas de tiempo, test correcto): arranque de Maven y lectura del POM unos 2 s; `enforcer`, `rat` (omitido), `artifact:check-buildplan` y `build-helper` unos 2,5 s; `antrun`, `remote-resources` y `buildnumber` unos 2,4 s; `compile` principal 0,4 s ("Nothing to compile"); `bundle:manifest` unos 4 s; **`testCompile` unos 14 s**, porque al cambiar una fuente el compilador recompila las 268 fuentes de test del módulo; `jacoco:prepare-agent` 0,5 s; `surefire:test` unos 4,5 s (bifurcación de la JVM incluida). Un `mvn -o validate` cuesta unos 4 s.

Variantes probadas una a una sobre el mismo test (3 validaciones cada una, en caliente):

| Variante | Segundos | Decisión |
|---|---:|---|
| V0, comando completo | 19,8 – 20,1 | referencia |
| V1, V0 + `-Denforcer.skip -Dmaven.antrun.skip -Dremoteresources.skip -Dmaven.buildNumber.skip -Dbundle.skip -Djacoco.skip` | 16,8 – 16,9 | se conserva sin `jacoco.skip` |
| V2, V0 + `-Dmaven.compiler.useIncrementalCompilation=false` (solo se compilan las fuentes obsoletas: "Compiling 1 source file") | 8,6 – 9,0 | se conserva |
| V3, V1 + V2 | 6,6 – 6,8 | se conserva sin `jacoco.skip` (6,4 – 6,7) |
| V4, V2 con los goals directos `resources:testResources compiler:testCompile surefire:test` | 5,2 – 5,5 | descartada: se salta la fase `compile` de las clases principales y la configuración por ejecución de los plugins; no compensa 1,3 s |

`-Djacoco.skip` se descartó porque el agente de JaCoCo aparece en la línea "Command was" del diagnóstico de `System.exit` y el diagnóstico debía quedar idéntico. Comprobación diferencial (`tests/test_java_adapter.py::test_integration_fast_command_matches_full_command`): siete casos (test correcto, aserción falsa, error de compilación, fichero sin `@Test`, `System.exit`, import ausente, nombre de clase distinto del fichero) dan el mismo `passed`, el mismo `infra_failure` y el mismo diagnóstico filtrado (salvo tiempos y nombres temporales de Surefire) con ambos comandos. El suelo queda en unos 6,5 s, por debajo de 8 s.

## Puerta de calidad (`scripts/gate_model.py`)

Diez tareas de `StringUtils` (las del bloque determinista), prompt real de generación, temperatura 0,7, semilla 1. Criterio: al menos 9 de 10 respuestas parseadas por `parse_model_output` y no truncadas, y mediana de velocidad en caliente (sin la primera llamada) de al menos 20 tok/s.

| Modelo | Respuestas válidas | Truncadas | tok/s en caliente (mediana) | Tokens por respuesta (media / máx.) | Segundos por llamada en caliente (media / máx.) | Veredicto |
|---|---:|---:|---:|---:|---:|---|
| qwen2.5-coder:7b | 10/10 | 0 | 74,4 | 202 / 278 | 2,73 / 3,7 | PASA |
| qwen3:8b | 10/10 | 0 | 67,4 | 249 / 313 | 3,68 / 4,6 | PASA |
| llama3.1:8b | 10/10 | 0 | 73,1 | 273 / 450 | 3,74 / 6,1 | PASA |
| gemma4:e4b | 10/10 | 0 | 145,1 | 497 / 736 | 3,54 / 5,6 | PASA |

Los cuatro modelos pasan; no procede ninguna observación de frontera por la puerta. La puerta comprueba formato y velocidad, no la calidad de los tests.

## El caso de `gemma4:e4b`

Evidencia reunida:

- `/api/tags` (11435): 6.583.656.505 bytes en disco; `parent_model` `gemma4-validation-20260929:e4b-imatrix-attention-q6-q8-draft2`; Q4_K_M; 7,5 B de parámetros.
- `ollama show gemma4:e4b` (contra 11435): capacidades `completion`, `vision`, `audio`, `tools`, `thinking` (razonamiento activado por omisión; el experimento envía `think: false`); proyector CLIP de 478 M de parámetros; parámetros `top_k` 64, `top_p` 0,95, `temperature` 1 y `draft_num_predict` 3.
- `/api/ps` con el modelo cargado: `size` = `size_vram` = 373.565.684 bytes (0,37 GB), `context_length` 8192.
- `nvidia-smi` con el modelo cargado: 4.772 MiB usados, frente a 11 MiB antes y después.
- Velocidad de generación de unos 145 tok/s, aproximadamente el doble que los otros tres modelos de tamaño parecido.
- Longitud de las respuestas: 420–736 tokens con el prompt real (media 497 en la puerta), todas con `done_reason` = `stop`.

Lo que la evidencia sostiene:

1. Los 0,4 GB de `/api/ps` no reflejan la memoria real ocupada: la GPU tiene unos 4,7 GB en uso mientras el modelo está cargado y solo entonces. No hay indicio de desalojo a la CPU en esta medición (velocidad alta y estable). Por qué `/api/ps` informa ese tamaño no queda explicado; `draft_num_predict` y el nombre `...-draft2` sugieren decodificación especulativa con un modelo borrador, lo que sería compatible con la velocidad, pero no se ha comprobado y no se afirma.
2. El truncamiento de la prueba de humo se explica por el tope: `gemma4:e4b` produce respuestas más largas que los demás (hasta 736 tokens) y la prueba de humo cortaba a 512. Con `num_predict` 2048 no se truncó ninguna de las 14 respuestas observadas (4 de la medición, 10 de la puerta).
3. Para la contabilidad de memoria del experimento debe usarse `nvidia-smi`, no `/api/ps`, en el caso de este modelo.

## Estimación de duración del bloque estadístico

2.400 ejecuciones: 4 modelos × 20 métodos × 15 repeticiones × 2 condiciones, es decir 1.200 de *baseline* y 1.200 de reparación.

Supuestos:

- Generación en caliente: 3,42 s por llamada (media de las medias de la puerta). Una llamada de reparación lleva un prompt más largo (código anterior más diagnóstico de hasta 4.000 caracteres); se le suma 1 s, supuesto no medido.
Mismos supuestos que la estimación original de la Tarea 11; solo cambia el tiempo de Maven (Tarea 7c).

- Maven: 6,5 s por validación (mediana en caliente del comando rápido; antes 19,3 s). Toda respuesta parseada se valida; en la puerta lo fueron 40 de 40.
- *Baseline*: exactamente 1 llamada y 1 validación por ejecución: 9,9 s (antes 22,7 s).
- Reparación: entre 1 y 4 llamadas. **Se supone una media de 3,5 llamadas (2,5 reparaciones por candidato)**, porque en el piloto Java del 21 de noviembre (`docs/findings.md`; excluido de toda métrica, aquí solo como referencia de planificación) 12 candidatos consumieron 30 reparaciones, 2,5 por candidato, con 1 de 12 pases directos. Con 3,5 llamadas: 3,42 + 2,5 × 4,42 + 3,5 × 6,5 ≈ 37 s por ejecución (antes 82 s).

| Escenario (llamadas medias en reparación) | *Baseline* | Reparación | Total | Total con el comando completo (19,3 s) |
|---|---:|---:|---:|---:|
| Mínimo (1 llamada, 0 reparaciones) | 3,3 h | 3,3 h | 6,6 h | 15,2 h |
| Intermedio (2,5 llamadas, 1,5 reparaciones) | 3,3 h | 8,8 h | 12,1 h | 27,0 h |
| **Supuesto (3,5 llamadas, 2,5 reparaciones, piloto)** | 3,3 h | 12,4 h | **15,7 h** | 34,9 h |
| Máximo (4 llamadas, 3 reparaciones) | 3,3 h | 14,2 h | 17,5 h | 38,9 h |

La fila que antes se rotulaba "Central (2,5)" usaba 2,5 llamadas, no las 2,5 reparaciones del piloto (que son 3,5 llamadas, la fila del supuesto); se rotula ahora como intermedia. Maven supone en torno al 65 % del tiempo de cada llamada validada (antes, el 85 %), de modo que la estimación sigue siendo más sensible al número de validaciones que a la velocidad de los modelos. Las cargas de modelo (cuatro, una por modelo gracias a la descarga entre modelos; hasta 2,5 min cada una) son despreciables.

Incertidumbre: muestras de 10 llamadas por modelo; la tasa de éxito del Java real con estos modelos y 20 métodos es desconocida y es la que fija el número de reparaciones; los reintentos por fallos de infraestructura (hasta 2 por ejecución) no están incluidos; el tiempo de Maven puede variar con tests que fallan, que compilan con errores o que agotan el tiempo (300 s de tope); el +1 s por llamada de reparación no se ha medido. Una cifra prudente para reservar la máquina es de 16 a 20 horas (antes, de 35 a 40).
