# Base de investigación: adaptación del flujo validate–repair

## Objetivo de Loom VERA

El prompt de [prompts.md](prompts.md) define VERA como un POC para validar, ejecutar, reparar y auditar código generado por modelos locales. VERA-01 adapta a Python y JavaScript/Node la comparación entre generación directa y reparación iterativa de tests unitarios. VERA-02 lleva después el flujo a una selección fija de tareas de DeepSWE. ODD + Gauntlet se estudiarán como comparación posterior.

La pregunta que orienta VERA es: **¿cuánto mejora un ciclo de generación, validación y reparación la proporción de artefactos realmente válidos, y cuándo el validador puede dar una impresión engañosa de éxito?**

## Plan acordado

La metodología de la tesis se adapta a **Python y JavaScript con Node.js**. No intentaremos reproducir literalmente su experimento Java; conservaremos la comparación de generación directa frente a reparación iterativa y la auditoría de los éxitos.

### VERA-01: comparación controlada

- Tarea: generar tests unitarios para una colección fija de métodos en proyectos Python y JavaScript/Node.
- Validación: ejecutar la suite del proyecto con su runner habitual (por ejemplo, `pytest` y `node --test`).
- Condiciones: un harness común por lenguaje, con el mismo modelo, prompt, parámetros, tareas, tests y límites; la única variable será el presupuesto de reparación: `0` frente a un máximo de `3` reparaciones.
- Auditoría: cada resultado aceptado debe contener un test ejecutable, una aserción y una llamada al método focal. Además, comprobar que el runner registra el test y que los fallos de aserción llegan al proceso; informar por separado el éxito del runner y el éxito sustantivo.
- Registro: conservar tarea, versión del modelo, prompt, cada salida y traza, resultado, reparaciones, tokens/tiempo y causa de parada.

Los resultados se analizarán por lenguaje además del agregado: así no confundimos las diferencias de ecosistema o dificultad con el efecto de reparar.

### VERA-02: validación externa con DeepSWE

Después de validar el harness controlado, se probará una selección de tareas Python y JavaScript de DeepSWE para observar el comportamiento en cambios de repositorio más amplios. DeepSWE contiene 113 tareas originales en 91 repositorios y cinco lenguajes, entre ellos Python y JavaScript; usa verificadores funcionales escritos para comprobar el comportamiento solicitado. [Paper de DeepSWE](https://arxiv.org/abs/2607.07946)

Se fijarán tareas, verificador y harness para comparar condiciones. Si se modifica el harness oficial o se usa solo un subconjunto, el resultado se presentará como experimento VERA, no como puntuación oficial de DeepSWE. La comparación con ODD + Gauntlet queda para después de establecer estas dos líneas base.

Terminal-Bench no será el benchmark inicial: evalúa tareas terminales diversas, no solo ingeniería de software, y evoluciona por versiones; si se incorpora más adelante, habrá que fijar una release concreta. [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)

## Cómo ejecutar la réplica VERA-01

La réplica, no el piloto, es ahora el procedimiento vigente: se ejecuta con `python -m vera run --block <determinista|estadistico> --language <java|python|node>` (entorno en [entorno-vera01.md](entorno-vera01.md)), se resume con `python -m vera report --block ... --language ...` y se interpreta con el informe de [findings.md](findings.md#réplica-vera-01-informe-consolidado). Los bloques guardan una traza por ejecución en `results/runs/<bloque>/<lenguaje>/records/` y se reanudan tras una interrupción; el informe se niega a presentar tasas de un bloque con menos ejecuciones que las planificadas. Lo que sigue describe el piloto del 21 de noviembre, archivado y fuera de las métricas de la réplica.

## Cómo se ejecutó el piloto archivado

Empezamos por VERA-01 para comprobar que el ciclo y la auditoría funcionan en un entorno controlado. El primer piloto valida el procedimiento; por su tamaño no servirá para afirmar que la reparación mejora el rendimiento de forma general.

1. Para comprobar el mecanismo, usar los fixtures sintéticos de este repo: dos métodos por lenguaje y una suite base. Este piloto no representa repositorios reales. En una evaluación posterior se sustituirán por proyectos fijados a commits concretos.
2. Elegir un modelo local y fijar su versión, backend, cuantización y parámetros de generación. Mantenerlos iguales en Python y JavaScript/Node.
3. Generar tres candidatos iniciales por método: doce en total. Guardar prompt, salida, modelo, parámetros y traza.
4. Por cada candidato, crear dos copias limpias con el mismo código inicial. En la rama directa, ejecutar una vez `python -m pytest` o `node --test`, según el proyecto. En la rama de reparación, usar el mismo comando y permitir hasta tres reparaciones, pasando al modelo el diagnóstico de cada fallo.
5. Auditar cada resultado aceptado: el runner debe haber ejecutado el test nuevo, este debe contener una aserción y debe llamar al método focal. Contar como éxito sustantivo solo los resultados que pasan el runner y cumplen los tres criterios.
6. Comparar las dos ramas por candidato y por lenguaje. Registrar reparaciones, causa de parada, tokens y tiempo; conservar salidas y errores para poder repetir el análisis.

El ejecutor `scripts/run-pilot.mjs` coordina ambas ramas, lanza `pytest` o `node --test` y guarda prompts, candidatos, salidas y resultados en JSONL bajo `results/`. Cada rama trabaja en una copia limpia. El piloto se ejecutó con Ollama y `qwen3.5:4b` mediante `node scripts/run-pilot.mjs --model qwen3.5:4b`; usa tres generaciones por método, temperatura `0.7` y hasta tres reparaciones. Si valida la instrumentación, se amplía la suite antes de extraer conclusiones.

El informe de las corridas y sus límites está en [findings.md](findings.md). Las dos primeras usaron fixtures sintéticos. La tercera probó métodos copiados de `poc-ante` en el commit registrado en [manifest.json](../benchmarks/vera01/real/manifest.json), con tests base aislados; no ejecutó la suite completa del repositorio original. Detectó tests Node que ocultaban excepciones, por lo que la auditoría ahora exige verificar el registro del test y la propagación de fallos.

La corrida con esos métodos se reproduce con `node scripts/run-pilot.mjs --suite real --model local-coding-task-lab-qwen2.5-coder-7b:4k`. Las fuentes copiadas y sus hashes quedan en `benchmarks/vera01/real/`; el checkout `poc-ante` no se modifica.

### Extensión a DeepSWE

En VERA-02 se fijarán versión, commit, tareas y modelo. Para cada tarea se conserva el mismo parche inicial y se crean una rama directa y otra con hasta tres reparaciones. La reparación solo puede usar pruebas visibles del repositorio y pruebas generadas por VERA. El verificador oficial, que DeepSWE ejecuta en un entorno separado, se reserva para puntuar ambos parches al final; no se entrega su diagnóstico al agente. El repositorio oficial describe las tareas, sus entornos y el uso de Pier para ejecutarlas. [Repositorio y guía oficial de DeepSWE](https://github.com/datacurve-ai/deep-swe)

Usar un subconjunto filtrado por lenguaje o este ciclo de reparación modificado sirve para comparar las ramas de VERA, pero no produce una puntuación oficial de DeepSWE.

## Qué contiene el paper disponible

El archivo [1791733959420.pdf](paper/1791733959420.pdf) es la tesis de máster de **María Isabel González Sánchez** (UNED, septiembre de 2026), sobre generación automática de tests unitarios Java para Apache Commons Lang. Estudia modelos locales y un ciclo generate–validate–repair usando Maven y JUnit 5. Su contribución que más importa para VERA es auditar también los resultados aceptados: un test puede compilar y pasar porque no ejecuta ningún test o no contiene aserciones.

**Nombre del archivo:** el prompt espera `validate-repair-uned-2026.pdf`, mientras que en el checkout el PDF tiene el nombre `1791733959420.pdf`. El contenido corresponde a la tesis de UNED citada aquí.

## Método que se quiere reproducir

1. **Generar:** pedir al modelo un test JUnit 5 para un método focal, con el código del método como contexto.
2. **Validar:** escribir el test en el proyecto y ejecutar una compilación y prueba Maven. Un resultado limpio cuenta como éxito provisional.
3. **Reparar:** si falla, devolver al mismo modelo el artefacto anterior y el diagnóstico de compilación o ejecución; repetir hasta agotar el presupuesto.
4. **Auditar:** inspeccionar los artefactos aceptados y comprobar que declaran un test, contienen aserciones y que alguna aserción invoca el método focal. Separar estos éxitos sustantivos de los vacíos.

La comparación usa **un solo harness** y cambia solo el presupuesto `MAX_REPAIRS`: `0` para la línea base (generar y validar una vez) y `3` para la condición con reparación. Esto permite atribuir diferencias al ciclo, en vez de a prompts, parsing o herramientas distintas.

## Diseño experimental del PDF

| Bloque | Modelos y tareas | Ejecuciones | Propósito |
|---|---|---:|---|
| Piloto | Un modelo, `CharUtils.toChar` | Exploratorio | Identificar errores reales de formato, integración y semántica en generación directa. |
| Determinista | Llama 3.1 8B y Qwen 2.5-Coder 7B; 10 métodos de `StringUtils`; temperatura 0 | Una por método y condición | Examinar cada intento y caracterizar por qué converge o falla. |
| Estadístico | Llama 3.1 8B, Qwen 2.5-Coder 7B, Qwen3 8B y Gemma 4 E4B; 20 métodos de `StringUtils`, `CharUtils` y `BooleanUtils`; temperatura 0.7 | 15 repeticiones por método y condición; 2.400 en total | Estimar la magnitud y variabilidad del efecto, y medir coste en tokens. |

La tesis ejecuta los modelos en Ollama sobre Windows y valida en el checkout de Apache Commons Lang. En el bloque estadístico conserva la misma condición en ambas ramas y registra artefactos, respuestas, trazas de build, iteraciones y tokens para permitir análisis posterior sin volver a invocar los modelos.

## Resultados esenciales

- En el bloque determinista, Qwen pasa de **4/10 a 6/10** métodos y Llama de **1/10 a 3/10** con reparación. La mejora es de dos métodos para cada uno.
- En el bloque estadístico, la tasa provisional de compilación y paso aumenta para los cuatro modelos: Llama **17,7 % → 54,7 %**, Qwen 2.5-Coder **25,7 % → 46,3 %**, Qwen3 **42,7 % → 52,3 %** y Gemma 4 **31,3 % → 66,7 %**. La regresión de efectos mixtos estima un odds ratio de **3,74** para la condición con reparación, controlando modelo y dificultad del método.
- La auditoría de los **1.012 artefactos aceptados** encuentra un **10,7 % de éxitos vacíos** en conjunto. El problema se concentra en Llama 3.1: **97 de sus 164** artefactos aceptados con reparación no prueban nada. Al contar solo tests sustantivos, su tasa baja de **54,7 % a 22,3 %** y la ganancia frente a su línea base se reduce de **+37,0 a +4,7 puntos**, sin significación estadística. Las mejoras de los otros tres modelos se mantienen casi iguales tras la auditoría.
- La reparación también tiene coste: en el bloque estadístico consume aproximadamente **3–6 veces** los tokens de la línea base. Más iteraciones no garantizan mejoras proporcionales; la ganancia marginal cae.

## Qué significa «falso positivo» aquí

El riesgo central del PDF no es que Maven afirme incorrectamente que un test con aserciones falla o pasa. Es un **falso éxito del oráculo**: el build devuelve éxito aunque no se haya ejecutado ningún test útil. Por eso la reproducción debe informar al menos dos medidas:

- **Éxito del build:** compila y pasa según el comando de validación.
- **Éxito sustantivo:** además, el test contiene una aserción que ejercita el método focal.

La auditoría es necesaria, pero no demuestra que las aserciones tengan buen poder de detección. La tesis identifica como límite que no mide calidad de las aserciones ni mutation score.

## Alcance y límites de la evidencia

Los resultados que se resumen arriba corresponden al estudio original de tests Java en Apache Commons Lang; no son resultados de VERA. Python/Node y DeepSWE son adaptaciones con tareas, runners y harness distintos. La auditoría confirma que el test toca el método focal, pero no mide su poder para detectar defectos. La suite de VERA-01 deberá quedar fijada y versionada antes de comparar modelos.

## Referencia

González Sánchez, María Isabel. (2026, septiembre). *Agentic Validate–Repair Workflows for Local Large Language Models: A Controlled Empirical Evaluation on Automated Unit Test Generation* [Tesis de máster, MSc in Artificial Intelligence Research, UNED]. [PDF](paper/1791733959420.pdf).
