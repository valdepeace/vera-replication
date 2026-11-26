# Resultados del piloto VERA-01

**Estado:** pilotos exploratorios ejecutados el 21 de noviembre de 2026. Incluyen fixtures sintéticos y métodos reales copiados a un harness aislado; no son una evaluación end-to-end de repositorios ni permiten concluir que reparar mejore el rendimiento en general.

## Diseño y entorno

- Cuatro funciones sintéticas: `normalize_whitespace` y `chunk_text` en Python; `normalizeWhitespace` y `chunkText` en JavaScript.
- Tres candidatos iniciales por función: 12 candidatos, cada uno bifurcado en una rama directa y otra con hasta tres reparaciones. Ambas ramas parten de la misma salida inicial.
- Una rama se cuenta como aprobada si pasa el test generado y la suite completa. Los tests aceptados se auditaron además para confirmar ejecución, aserciones y llamada a la función focal.
- Modelo: `qwen3.5:4b`, Q4_K_M, SHA-256 `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7572f6d2e92e38c04`.
- Ollama 0.40.13, API `/api/chat` con `think: false`, temperatura 0.7, contexto 4096 y máximo de 2048 tokens de salida. Se registran semillas por candidato.
- Python 3.12.10 con pytest 9.1.1; Node.js 24.8.0.

La tesis que inspira la comparación y la auditoría es una tesis de máster (UNED, 2026) sobre generación de tests Java. Este piloto conserva la comparación generate–validate–repair y la auditoría de falsos éxitos, pero usa fixtures sintéticos en Python y JavaScript; no reproduce el experimento de la tesis. Véase [research.md](research.md).

## Resultados

| Lenguaje | Casos emparejados | Directo | Con reparación | Solo reparación mejora | Ambas ramas pasan | Ambas fallan | Reparaciones usadas |
|---|---:|---:|---:|---:|---:|---:|---:|
| Python | 6 | 1/6 | 4/6 | 3 | 1 | 2 | 11 |
| JavaScript/Node | 6 | 1/6 | 2/6 | 1 | 1 | 4 | 15 |
| **Total** | **12** | **2/12** | **6/12** | **4** | **2** | **6** | **26** |

La tasa de aprobación del runner pasó de 16,7 % en directo a 50 % con reparación: diferencia exploratoria de 33,3 puntos porcentuales en estos fixtures. Las ocho ramas aprobadas cumplieron la auditoría básica de ejecución, aserción y llamada a la función. Corresponden a seis artefactos distintos, porque en dos casos ambas ramas conservaron el mismo test inicial sin reparaciones.

## Lectura y límites

- La reparación recuperó cuatro casos que fallaban en la rama directa; seis pares fallaron en ambas ramas y ninguno pasó solo en directo.
- La auditoría estructural de las corridas sintéticas evita contar un archivo vacío o un test que no invoque el objetivo como éxito sustantivo. No mide si las aserciones detectan errores relevantes ni calcula mutation score; la tercera corrida añadió la comprobación de registro y propagación de fallos tras detectar wrappers Node que ocultaban excepciones.
- Uno de los tests aceptados para `chunk_text` comprobó el número de fragmentos y varios contenidos, pero omitió verificar el último fragmento. Por tanto, pasar esta auditoría estructural no equivale a tener un test de alta calidad.
- Cada corrida usa un único modelo; las dos primeras usan fixtures sintéticos y la tercera solo cuatro métodos aislados. No se calculó significación estadística y las diferencias observadas no deben interpretarse como evidencia general.
- `qwen2.5-coder:7b` no pudo cargarse por errores de asignación de memoria. Un intento inicial de `qwen3.5:4b` mediante `/api/generate` produjo respuestas vacías en algunos casos y se interrumpió; esos datos parciales están excluidos del resumen. La corrida informada usa `/api/chat` con razonamiento desactivado.

## Segunda corrida: Qwen2.5-Coder 7B

Después se repitió exactamente el mismo piloto con el alias local `local-coding-task-lab-qwen2.5-coder-7b:4k`, que sí respondió a una prueba mínima. Es Qwen2.5-Coder 7.6B Q4_K_M, contexto 4096, digest `58fd7933c0e7db5ed1fd96ca8677b0fb561ef03c42cb33edeaac345d56e31943`. El alias lleva un system prompt genérico de Qwen; el resultado representa ese alias y runtime.

| Lenguaje | Casos emparejados | Directo | Con reparación | Solo reparación mejora | Ambas ramas pasan | Ambas fallan | Reparaciones usadas |
|---|---:|---:|---:|---:|---:|---:|---:|
| Python | 6 | 2/6 | 2/6 | 0 | 2 | 4 | 12 |
| JavaScript/Node | 6 | 0/6 | 1/6 | 1 | 0 | 5 | 16 |
| **Total** | **12** | **2/12** | **3/12** | **1** | **2** | **9** | **28** |

Las cinco ramas aprobadas pasaron la auditoría estructural; son tres artefactos distintos, ya que en dos pares no hizo falta reparar el test. Junto con Qwen3.5, esta corrida confirma que el runner puede comparar modelos instalados, pero las diferencias observadas siguen siendo exploratorias por usar los mismos cuatro fixtures sintéticos.

## Tercera corrida: métodos reales de `poc-ante`

Se probó el mismo flujo con cuatro métodos de un checkout local de `poc-ante`, fijado en el commit `4b3e9902b409858abb96f646a7f540eaa875592b`: `truncate` y `to_wsl_path` en Python; `nodeDir` y `bestByRound` en TypeScript ejecutado por Node. Se copiaron los módulos y tipos mínimos al fixture de VERA y se registraron sus hashes en [manifest.json](../benchmarks/vera01/real/manifest.json). No se modificó el checkout original ni se ejecutó su suite completa.

La corrida usó el alias local `local-coding-task-lab-qwen2.5-coder-7b:4k`, tres candidatos por método y hasta tres reparaciones. El runner informó 1/12 pases directos y 3/12 con reparación, tras 30 reparaciones. La auditoría manual cambia la lectura:

| Lenguaje | Casos | Pases directos del runner | Pases con reparación del runner | Éxitos sustantivos directos | Éxitos sustantivos con reparación | Reparaciones |
|---|---:|---:|---:|---:|---:|---:|
| Python | 6 | 0/6 | 0/6 | 0/6 | 0/6 | 18 |
| TypeScript/Node | 6 | 1/6 | 3/6 | 1/6 | 1/6 | 12 |
| **Total** | **12** | **1/12** | **3/12** | **1/12** | **1/12** | **30** |

Dos de los tres pases de reparación en Node son falsos positivos: los tests generados para `nodeDir` implementan `suite`/`test` propios, capturan las excepciones de las aserciones y solo las imprimen. El proceso termina con código cero aunque haya fallos. El único artefacto aceptado por la auditoría usa `node:test` para `bestByRound`; el mismo test pasó en directo y reparación sin cambios (SHA-256 `48604710808BBC2BC68EEBF3237C18481E896BD619503FEACE29CAAEA01D4566`). Tras auditar, hay un único par que pasa en ambas ramas y ninguna mejora exclusiva de reparación.

En Python no hubo pases. Los tests generados mezclaron errores de expectativas y casos mal especificados; por ejemplo, uno esperaba que `to_wsl_path("C:\\Users\\user\\Documents\\..\\file.txt")` lanzara `ValueError`, aunque la implementación solo valida el formato de ruta absoluta con unidad y conserva los segmentos `..`. La suite expuso un test incorrecto, no un fallo de ejecución del runner.

Este hallazgo endurece el protocolo: además de comprobar ejecución, aserciones y llamada al método focal, la auditoría debe verificar que el runner registra realmente los tests y que las excepciones de aserción llegan al proceso. Es la misma preocupación por falsos éxitos que motiva la auditoría descrita en la tesis de referencia; aquí apareció en un harness Node generado por el propio modelo.

## Artefactos

- Los registros, resúmenes y auditorías de las corridas piloto del 21 de noviembre de 2026 (`records.jsonl`, `summary.json`, `audit.jsonl`) se conservan únicamente en local y no se publican en este repositorio; el [registro de corridas](../results/README.md) deja constancia de cada una.
- Métodos reales: el [manifiesto de fuentes](../benchmarks/vera01/real/manifest.json) permanece versionado.
- Los tests generados y la salida cruda de cada runner están en los subdirectorios del [registro de corridas](../results/README.md).


## Bloque determinista de Java (VERA-01, réplica)

Ejecutado el 22 de noviembre de 2026 con `python -m vera run --block determinista --language java`: dos modelos (`llama3.1:8b`, `qwen2.5-coder:7b`), diez métodos de `StringUtils` de Apache Commons Lang (commit `89bb30909bf873d75f5e06d144f9b2e72d74c076`), dos condiciones (`MAX_REPAIRS` 0 y 3) y dos repeticiones, con semilla 42 y temperatura 0: 80 ejecuciones, todas válidas, ninguna con fallo de infraestructura, ninguna interrumpida ni reanudada, sin ficheros `.tmp`. El conjunto completo tardó unos 20 minutos de cómputo de modelo y Maven (6,5 s por validación). El informe completo figura en [informe.md](../results/runs/determinista/java/informe.md) y el manifiesto en [manifest.json](../results/runs/determinista/java/manifest.json); los registros crudos no se versionan.

| Modelo | Baseline (REAL) | Reparación (REAL) | Diferencia (IC 95 % de Newcombe) |
|---|---:|---:|---|
| `llama3.1:8b` | 6/20 (30 %) | 17/20 (85 %) | +0,55 [+0,25; +0,73] |
| `qwen2.5-coder:7b` | 8/20 (40 %) | 17/20 (85 %) | +0,45 [+0,15; +0,66] |

**Auditoría.** De las 80 ejecuciones, 48 fueron aceptadas por el validador y las 48 se clasificaron `REAL`; no apareció ningún `EMPTY`, `TEST_FREE`, `ASSERTION_FREE` ni `NO_FOCAL`, de modo que la tasa del runner coincide con la tasa sustantiva. Una comprobación adicional sobre los 48 tests aceptados (todos contienen `@Test`, al menos una aserción por prueba, ninguna aserción trivial y al menos una llamada al método focal) no halló sospechosos. No hubo, por tanto, ningún falso éxito que inspeccionar; las 32 ejecuciones restantes agotaron el presupuesto (26 en baseline, 6 en reparación). Todas las salidas se parsearon, ninguna se truncó.

**Estabilidad.** Las dos repeticiones coinciden en el veredicto en 36 de 40 pares (90 %). Los cuatro pares discordantes son `llama3.1:8b` en `equalsIgnoreCase` y `isNotEmpty` (baseline), `llama3.1:8b` en `isBlank` (reparación: 3 intentos frente a 4 sin éxito) y `qwen2.5-coder:7b` en `trimToNull` (reparación, mismo patrón). La discordancia con temperatura 0 y semilla fija indica que el motor no es bit a bit determinista (probable no determinismo numérico de la GPU); no se ha investigado la causa.

**Fallos tras reparación (6 ejecuciones).** `llama3.1:8b` en `length` (2 de 2): insiste en un `assertThrows(NullPointerException)` que `StringUtils.length(null)` no lanza (devuelve 0) y no corrige tras tres reparaciones; `llama3.1:8b` en `isBlank` (1): expectativa de aserción errónea; `qwen2.5-coder:7b` en `trimToEmpty` (2 de 2) y `trimToNull` (1): error de compilación persistente tras tres reparaciones.

**Comparación con la orientación de la tesis** (sin exigir coincidencia): la tesis apunta a 4/10 → 6/10 en `qwen2.5-coder:7b` y a 1/10 → 3/10 en `llama3.1:8b`. Aquí, por repetición, `qwen2.5-coder:7b` pasa de 4/10 (ambas repeticiones dan 8/20, es decir, 4/10 de media) a 8,5/10 y `llama3.1:8b` de 3/10 a 8,5/10. El baseline de qwen coincide con la orientación; el de llama es más alto (3/10 frente a 1/10) y la mejora con reparación es sensiblemente mayor en ambos. Desviaciones posibles, sin contrastar: modelo y cuantización servidos por Ollama, prompt versionado `vera01-p1`, auditoría y proyecto distintos de los de la tesis.

**Cautelas.** Son 80 ejecuciones de un bloque de planificación y estabilidad, no de significación: los 10 métodos son los mismos en cada celda y las dos repeticiones no son independientes (el 90 % de estabilidad lo confirma), de modo que los 20 casos por celda son en realidad unos 10 y el intervalo de Newcombe del informe, que los trata como independientes, es optimista. Lo único que cabe afirmar es que la reparación ayudó de forma consistente en estos métodos; la magnitud definitiva corresponde al bloque estadístico. No se detectó ningún defecto del arnés (parser, auditoría, adaptador) en el bloque.


## Réplica VERA-01 (informe consolidado)

**Estado a 22 de noviembre de 2026:** solo hay un bloque completo y válido, el determinista de Java (80 ejecuciones, descrito arriba). El bloque estadístico de Java (2.400 ejecuciones planificadas) estaba en curso y los de Python y Node no se han ejecutado; sus tasas se incorporarán aquí únicamente cuando cada bloque esté completo. Cabe señalar que `python -m vera report --block <bloque> --language <lenguaje>` se niega a presentar tasas de un bloque con menos ejecuciones que las planificadas (con `--partial` las marca como PARCIAL y no una métrica), y que el piloto del 21 de noviembre, las corridas parciales y las interrumpidas no entran en ninguna cifra de la réplica.

### Entorno

Versiones, rutas y orden de preparación en [entorno-vera01.md](entorno-vera01.md); medición de motores y puerta de calidad con `num_ctx` 8192 en [medicion-8192.md](medicion-8192.md). Motor: Ollama 0.40.13 (puertos 11434 y 11435; 11431 para la ampliación y para p2, pues el 11435 quedó reservado por Windows); versión del prompt: `vera01-p1` (`PROMPT_VERSION`).

### Desviaciones respecto de la tesis

| Aspecto | Tesis | Réplica | Efecto probable |
|---|---|---|---|
| Prompts | Texto no publicado | Reconstruidos (`vera01-p1`) | Las tasas absolutas no son comparables en rigor |
| Orquestación | LangChain y LangGraph 1.1.4, grafo de tres nodos | Flujo propio de tres nodos (`src/vera/workflow.py`), sin LangGraph | Mismo ciclo; posibles diferencias de formato y reintentos |
| Contexto | `OLLAMA_NUM_CTX=8192` | `num_ctx` 8192, `num_predict` 2048 (tope no publicado en la tesis) | Lo truncado cuenta como fallo y consume una reparación |
| Hardware | RTX 4060 Laptop, driver 576.02 | RTX 3060 Ti, driver 610.88 | Afecta al tiempo; el efecto en las tasas no se ha medido |
| Métodos del bloque estadístico | 20 métodos; los diez adicionales no se publican | Diez adicionales elegidos por la réplica | La dificultad del conjunto difiere |
| Veredicto | Validación con Maven en el árbol del proyecto | Maven en modo desconectado, limitado al test generado; sin suite completa | Un test que rompa otros módulos no se detecta |
| Javadoc | No consta que se omita | El `focal_source` se entrega sin Javadoc | Menos pistas sobre el oráculo que en un uso real |
| Python y Node | No existen en la tesis | Proyectos propios ([proyectos-python-node.md](proyectos-python-node.md)) | Sin cifra de la tesis con la que comparar |
| Importación de la clase bajo prueba | No consta | El prompt da el nombre de la clase sin su paquete (véase más abajo) | Los fallos de compilación por importación dominan el primer intento |

### Limitación del prompt: el paquete de la clase bajo prueba

Cabe señalar que el prompt `vera01-p1` exige `package org.generated;` e indica la clase bajo prueba únicamente por su nombre (por ejemplo `BooleanUtils`), sin su paquete `org.apache.commons.lang3`. El modelo ha de deducirlo por sí mismo, de suerte que la tasa mide, en parte, si conoce Commons Lang y no solo su destreza para escribir tests. Se detectó al examinar el 0 % de baseline de `qwen3:8b`.

Primer intento de la condición baseline, 300 ejecuciones por modelo (bloque estadístico):

| Modelo | No compilan | Detalle |
|---|---:|---|
| `qwen3:8b` | 299 | 298 importan `org.generated.X`, clase inexistente |
| `llama3.1:8b` | 259 | 50 importan `org.generated.X`; 43 inventan un paquete |
| `qwen2.5-coder:7b` | 192 | 11 importan `org.generated.X` |
| `gemma4:e4b` | 279 | 242 con `cannot find symbol`; ninguna con importación explícita de la clase |

Decisión: los resultados de `vera01-p1` se conservan sin alteración y se informan con esta salvedad; no se corrigen ni se repiten. Una versión que indicase el paquete sería un prompt distinto (`vera01-p2`) y exigiría un bloque nuevo con todos los modelos, nunca solo con uno, pues el informe rechaza mezclar versiones. Las diferencias absolutas con la tesis, y en particular el hundimiento de `qwen3:8b` en baseline, deben leerse con esta limitación presente.

### Ampliación con Ornith 1.5 9B

Con el mismo prompt, parámetros y tareas se añade el bloque `ampliacion` (600 ejecuciones): Ornith 1.5 9B, conversión GGUF Q4_K_M de bartowski, servida en el puerto 11431 desde `E:\ollama-vera\models` (Windows reservó el rango 11435-11534 tras el reinicio del 23 de noviembre de 2026). Superó la puerta de velocidad (29,5 tok/s; mínimo 20), aunque un 14 % del modelo reside en CPU. `qwen3-coder:30b` (18,7 tok/s) y `qwen3:30b-a3b` (19,6 tok/s) no la superaron y quedaron fuera por lo acordado. El informe mezcla ambos bloques con `python -m vera report --block estadistico --with ampliacion --language java`, lo cual es lícito porque comparten prompt, parámetros y tareas.

### Resultados por lenguaje y modelo

**Java, bloque determinista** (completo; `results/runs/determinista/java/informe.md`): véase la sección anterior. Tasas REAL, baseline frente a reparación, de 20 ejecuciones por celda: `llama3.1:8b` 6/20 frente a 17/20 y `qwen2.5-coder:7b` 8/20 frente a 17/20.

| Modelo | Tesis publicada (Tabla 4.3, métodos de 10) | Réplica (REAL, por 10 métodos) |
|---|---|---|
| `qwen2.5-coder:7b` | 4/10 → 6/10 | 40 % → 85 % |
| `llama3.1:8b` | 1/10 → 3/10 | 30 % → 85 % |

**Java, bloque estadístico:** completo, véase la sección siguiente. **Python y Node:** completos, véase «Resultados del bloque estadístico de Python y Node». Cifras de la tesis para el bloque estadístico, verificadas en el PDF (porcentajes de 300 ejecuciones por celda; ingenua = compila y pasa, sustantiva = auditada): Llama 3.1 17,7 → 54,7 (sustantiva 17,7 → 22,3); Qwen 2.5-Coder 25,7 → 46,3 (25,0 → 45,0); Qwen3 42,7 → 52,3 (42,7 → 52,0); Gemma 4 31,3 → 66,7 (31,3 → 65,3); odds ratio agregado 3,74 con el criterio ingenuo, que la propia tesis rebaja a 2,60 al retirar la contribución inflada de Llama 3.1 (verificado en el PDF); 10,7 % de éxitos vacíos sobre 1.012 aceptados; el múltiplo de tokens publicado es de aproximadamente 3 a 6. Python y Node no tienen cifra de la tesis y no se inventa ninguna.

### Resultados del bloque estadístico ampliado (Java)

Cabe señalar que el informe completo, con cinco modelos y 3.000 ejecuciones válidas (las 2.400 del bloque estadístico más las 600 de la ampliación con Ornith), figura en [results/runs/estadistico/java/informe.md](../results/runs/estadistico/java/informe.md). Tasas REAL de 300 ejecuciones por celda, con la mejora de reparación sobre baseline en puntos porcentuales y su intervalo de confianza del 95 % (Newcombe):

| Modelo | Baseline | Repair | Mejora (IC 95 %) | Vacíos | Múltiplo de tokens |
|---|---:|---:|---|---:|---:|
| `qwen3:8b` | 0,0 % | 74,7 % | +75 [+69, +79] | 0 % | 4,48 |
| `ornith-1.5:9b` | 25,0 % | 64,0 % | +39 [+31, +46] | 4 % | 4,38 |
| `qwen2.5-coder:7b` | 32,3 % | 58,7 % | +26 [+18, +34] | 0 % | 4,19 |
| `llama3.1:8b` | 8,3 % | 53,3 % | +45 [+38, +51] | 0 % | 5,49 |
| `gemma4:e4b` | 6,0 % | 18,3 % | +12 [+7, +18] | 1 % | 6,99 |

Lectura, sin afirmar coincidencia con la tesis:

- La reparación mejora a los cinco modelos y el intervalo no contiene el cero en ninguno. Los intervalos son optimistas por la falta de independencia indicada en los límites.
- El tamaño de la mejora y el orden de los modelos difieren de los de la tesis. Con reparación, la tesis sitúa a `gemma4:e4b` en cabeza (65,3 %) y a `llama3.1:8b` en último lugar (22,3 %); la réplica los invierte (18,3 % y 53,3 %). La mejora sustantiva de la tesis frente a la de la réplica es de +34,0 frente a +12,3 puntos en `gemma4:e4b`, +4,6 frente a +45,0 en `llama3.1:8b`, +20,0 frente a +26,4 en `qwen2.5-coder:7b` y +9,3 frente a +74,7 en `qwen3:8b`.
- `ornith-1.5:9b` no figura en la tesis y su cifra se marca "no verificable". Su baseline (25,0 %) es la más alta tras la de `qwen2.5-coder:7b`; no se ha analizado a qué se debe.
- La tesis sitúa el problema de los éxitos vacíos en `llama3.1:8b`; en la réplica es del 0 %. El único modelo con una proporción apreciable es `ornith-1.5:9b` (4 %).
- El múltiplo de tokens de la reparación va de 4,19 a 6,99, algo por encima del intervalo de unos 3 a 6 que publica la tesis.
- Todo ello debe leerse con la limitación del prompt descrita más arriba, que penaliza sobre todo a `qwen3:8b` en baseline.

Nota de procedimiento: una ejecución de la ampliación (`java-StringUtils-length`, baseline, repetición 12) quedó inicialmente inválida por un `UnicodeEncodeError` (un carácter suelto en la respuesta del modelo), fallo de infraestructura y no resultado. Conforme al diseño del ejecutor, que reintenta las ejecuciones con fallo de infraestructura, se repitió una sola vez y salió válida; el informe no contiene ninguna ejecución inválida.

### Cuánto de la mejora procede de corregir la importación

Cabe señalar que, entre las ejecuciones de la condición *repair* rescatadas por la reparación (aceptadas tras al menos una reparación), se clasificó el primer fallo según su diagnóstico. Primer fallo de resolución de símbolos (`cannot find symbol`, `does not exist` y similares):

| Modelo | Rescatadas | Primer fallo de resolución de símbolos |
|---|---:|---:|
| `qwen3:8b` | 223 | 97 % |
| `llama3.1:8b` | 138 | 84 % |
| `gemma4:e4b` | 45 | 71 % |
| `qwen2.5-coder:7b` | 89 | 64 % |
| `ornith-1.5:9b` | 127 | 36 % |

Es un tope y no una medida exacta de lo atribuible a la importación: `cannot find symbol` también aparece por un método o una variable inexistentes. Aun así, indica que en cuatro de los cinco modelos la mayor parte de la ganancia atribuida al bucle consiste en corregir símbolos que el prompt p1 no permitía resolver. `ornith-1.5:9b`, el menos afectado, mejora +39 puntos [+31, +46] con solo un 36 % de rescates de ese tipo, y es el caso que mejor sugiere un efecto genuino del bucle.

Formulación prudente para citar estos resultados: *en esta réplica, el bucle validar-reparar mejora la tasa de tests con aserciones reales en los cinco modelos, si bien buena parte de la mejora procede de corregir errores de resolución de símbolos derivados de un prompt incompleto; su efecto sobre la calidad de los tests, aislado de ese factor, se mide en el bloque con el prompt `vera01-p2`, cuyo protocolo se fijó de antemano en [prerregistro-vera01-p2.md](prerregistro-vera01-p2.md).*

### Resultado del bloque con el prompt p2 (import dado)

Cabe señalar que el bloque `estadistico-p2` (3.000 ejecuciones, ninguna inválida) se lanzó con el protocolo fijado de antemano en [prerregistro-vera01-p2.md](prerregistro-vera01-p2.md); la comparación completa, con intervalos, figura en [comparativa-p1-p2.md](comparativa-p1-p2.md) y el informe en `results/runs/estadistico-p2/java/informe.md`.

- Al dar el import, el baseline REAL sube en los cinco modelos (de +18 a +51 puntos) y los rescates cuyo primer fallo fue de símbolos caen del 36-97 % al 3-15 %.
- La mejora del bucle (repair menos baseline) baja en cuatro modelos: llama3.1:8b de +45 a +12, qwen3:8b de +75 a +8, qwen2.5-coder:7b de +26 a +15 y ornith-1.5:9b de +39 a +35; sube en gemma4:e4b, de +12 a +21. Excluye el cero en cuatro de los cinco modelos (todos salvo qwen3:8b), de modo que se cumple el criterio prerregistrado (al menos tres).
- qwen3:8b merece mención aparte: su tasa del runner (53 % → 69 %) y su tasa REAL (34 % → 42 %) divergen porque el 38 % de sus ejecuciones son vacías.
- Formulación prudente: *con el paquete de la clase indicado, el bucle validar-reparar conserva un efecto positivo de entre +8 y +35 puntos en cuatro de cinco modelos; el efecto de p1 estaba muy inflado por la importación.*

### Resultados del bloque estadístico de Python y Node

Cabe señalar que ambos bloques (2.400 ejecuciones cada uno, prompt `vera01-p1`, mismos cuatro modelos y parámetros que en Java) se completaron el 25 de noviembre de 2026; los informes figuran en [results/runs/estadistico/python/informe.md](../results/runs/estadistico/python/informe.md) y [results/runs/estadistico/node/informe.md](../results/runs/estadistico/node/informe.md). La tesis no publica cifras para estos lenguajes, de modo que no hay comparación posible. Tasas REAL de 300 ejecuciones por celda, con la mejora de reparación sobre baseline y su intervalo del 95 % (Newcombe):

| Lenguaje | Modelo | Baseline | Repair | Mejora (IC 95 %) | Vacíos | Múltiplo de tokens |
|---|---|---:|---:|---|---:|---:|
| Python | `gemma4:e4b` | 28 % | 53 % | +25 [+17, +32] | 0 % | 5,20 |
| Python | `llama3.1:8b` | 32 % | 53 % | +21 [+13, +29] | 0 % | 4,75 |
| Python | `qwen2.5-coder:7b` | 55 % | 68 % | +13 [+6, +21] | 2 % | 3,41 |
| Python | `qwen3:8b` | 50 % | 57 % | +7 [−1, +15] | 0 % | 3,64 |
| Node | `gemma4:e4b` | 30 % | 58 % | +28 [+20, +35] | 10 % | 4,61 |
| Node | `llama3.1:8b` | 35 % | 47 % | +12 [+4, +20] | 0 % | 4,89 |
| Node | `qwen2.5-coder:7b` | 18 % | 29 % | +11 [+5, +18] | 3 % | 5,87 |
| Node | `qwen3:8b` | 50 % | 65 % | +15 [+7, +23] | 0 % | 3,61 |

- La reparación mejora en siete de las ocho celdas con un intervalo que excluye el cero; la excepción es `qwen3:8b` en Python, cuyo intervalo contiene el cero. Los intervalos son optimistas por la falta de independencia indicada en los límites.
- Las mejoras (de +7 a +28 puntos) quedan muy por debajo de las de Java con p1 y en el orden de las de Java con p2, lo cual es coherente con que en Python y Node el prompt no adolece del problema de importación que inflaba el efecto en Java.
- `gemma4:e4b` en Node presenta un 10 % de éxitos vacíos, la proporción más alta de toda la réplica; su tasa del runner con reparación (65 %) supera en siete puntos a la REAL (58 %).

Desviación de procedimiento (26 de noviembre de 2026). El bloque de Node terminó con 44 ejecuciones inválidas, de las que 36 se debían a un defecto del arnés y no del modelo: cuando el modelo escribía en su JSON un escape de cadena de JavaScript sin duplicar la barra, `json.loads` producía un sustituto UTF-16 suelto que no podía escribirse en UTF-8, y la ejecución se contaba como fallo de infraestructura, con pérdida de sus intentos. La exclusión no era aleatoria: 35 de las 36 correspondían a la tarea `node-isSurrogatePair` (31 de ellas de `gemma4:e4b`), de modo que sesgaba las tasas de esa tarea y de ese modelo. Se corrigió el analizador (commit `ccd41b3`), que ahora devuelve cada sustituto suelto a su escape textual, lo que el modelo quiso escribir; se guardó copia de los registros inválidos en `records/_sustituidas/` (fuera de git) y se repitieron únicamente las ejecuciones inválidas, conforme al diseño del ejecutor, sin tocar las 2.356 válidas. De las 44, 40 salieron válidas; quedan inválidas 4 en Node y 1 en Python, todas por `HTTP 500` del servidor de Ollama que se reproduce al repetir con la misma semilla. Tras la corrección cambian sobre todo las celdas de `gemma4:e4b` en Node (baseline REAL de 83/284 a 89/300 y repair de 162/284 a 173/300), sin alterar ninguna conclusión. El incidente análogo de la ampliación de Java (`java-StringUtils-length`) tuvo, con toda probabilidad, la misma causa.

Segunda desviación de procedimiento (26 de noviembre de 2026). Ciertamente, las cinco inválidas restantes tampoco eran fallos de infraestructura. Reproducida a mano la primera llamada de cada una, el cuerpo del `HTTP 500`, que el motor descartaba, resultó ser `prediction aborted, token repeat limit reached`: Ollama interrumpe la generación cuando el modelo entra en bucle repitiendo tokens. Dícese, pues, de una salida degenerada del propio modelo, equiparable a la que agota `num_predict`, y excluirla sesgaba las tasas a favor del éxito. El aborto tampoco es determinista: en la reproducción manual, dos de las cinco llamadas terminaron con normalidad. Se modificó el motor (`src/vera/engines/ollama.py`) para que ese aborto concreto cuente como salida truncada y vacía, de modo que en baseline la ejecución fracasa y en reparación el modelo recibe el diagnóstico de formato, como con cualquier truncamiento; cualquier otro `HTTP 500` sigue siendo fallo de infraestructura y ahora conserva en el mensaje el cuerpo del error. Se guardó copia de las cinco en `records/_sustituidas-500/` (fuera de git) y se repitieron solo esas, sin tocar las 4.795 válidas. Las cinco salieron válidas, de modo que ambos bloques quedan completos con 2.400 de 2.400. Tres fueron aceptadas como REAL en el primer intento, sin bucle. En las otras dos el aborto volvió a producirse en la primera llamada: `node-isBoolean` en baseline (agota el presupuesto) y `python-strings-ends_with` en reparación (tres reparaciones válidas que no pasan la validación). Las cifras apenas se mueven (Node: `llama3.1:8b` baseline 105/300 y repair 141/300; `qwen2.5-coder:7b` baseline 53/300; Python: `qwen2.5-coder:7b` repair 204/300) y ninguna conclusión cambia. Una salvedad: las ejecuciones abortadas no registran los tokens que llegaron a generarse, de modo que el múltiplo de tokens de esas dos queda ligeramente subestimado.

### Criterios de éxito (sección 11 de la especificación)

- Mejora por reparación en al menos tres de los cuatro modelos de Java (criterio: diferencia positiva con intervalo de confianza del 95 % que excluye el cero): **cumplido**, y en los cinco modelos (los cuatro del bloque original y Ornith); los intervalos son optimistas por la falta de independencia indicada en los límites.
- Porcentaje de éxitos vacíos por modelo: 0 % en `llama3.1:8b`, `qwen2.5-coder:7b` y `qwen3:8b`, 1 % en `gemma4:e4b` y 4 % en `ornith-1.5:9b`; en el determinista fue 0 % (48 aceptados, 48 REAL). La tesis sitúa el problema en Llama 3.1, que en la réplica no lo presenta.
- Múltiplo de tokens de la reparación: de 4,19 (`qwen2.5-coder:7b`) a 6,99 (`gemma4:e4b`), según el informe del bloque estadístico ampliado.

### Límites

Una sola máquina y un solo contexto (8192); prompts reconstruidos, no idénticos a los de la tesis; sin mutation score ni medida del poder de detección de las aserciones; la tasa REAL descansa en una auditoría estática cuyos límites para Python y Node están en [entorno-vera01.md](entorno-vera01.md), de modo que puede contener falsos REAL no cuantificados; los intervalos de Newcombe suponen independencia que no existe (mismos métodos en todas las celdas), por lo que son optimistas. No se afirma coincidencia con la tesis: solo se informa la dirección y la magnitud observadas.

