# Resultados del piloto VERA-01

**Estado:** pilotos exploratorios ejecutados el 21 de noviembre de 2026. Incluyen fixtures sintéticos y métodos reales copiados a un harness aislado; no son una evaluación end-to-end de repositorios ni permiten concluir que reparar mejore el rendimiento en general.

## Diseño y entorno

- Cuatro funciones sintéticas: `normalize_whitespace` y `chunk_text` en Python; `normalizeWhitespace` y `chunkText` en JavaScript.
- Tres candidatos iniciales por función: 12 candidatos, cada uno bifurcado en una rama directa y otra con hasta tres reparaciones. Ambas ramas parten de la misma salida inicial.
- Una rama se cuenta como aprobada si pasa el test generado y la suite completa. Los tests aceptados se auditaron además para confirmar ejecución, aserciones y llamada a la función focal.
- Modelo: `qwen3.5:4b`, Q4_K_M, SHA-256 `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7572f6d2e92e38c04`.
- Ollama 0.40.13, API `/api/chat` con `think: false`, temperatura 0.7, contexto 4096 y máximo de 2048 tokens de salida. Se registran semillas por candidato.
- Python 3.12.10 con pytest 9.1.1; Node.js 24.8.0.

La tesis que inspira la comparación y la auditoría es la de **María Isabel González Sánchez** (UNED, 2026), sobre generación de tests Java. Este piloto conserva la comparación generate–validate–repair y la auditoría de falsos éxitos, pero usa fixtures sintéticos en Python y JavaScript; no reproduce el experimento de la tesis. Véase [research.md](research.md) y el [PDF de la tesis](../paper/1791733959420.pdf).

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

Este hallazgo endurece el protocolo: además de comprobar ejecución, aserciones y llamada al método focal, la auditoría debe verificar que el runner registra realmente los tests y que las excepciones de aserción llegan al proceso. Es la misma preocupación por falsos éxitos que motiva la auditoría descrita en la tesis de **María Isabel González Sánchez**; aquí apareció en un harness Node generado por el propio modelo.

## Artefactos

- [Registro por candidato](../results/vera01-2026-11-21T14-05-08.057Z-aBzg7a/records.jsonl): prompts, respuestas, comandos, resultados y trazas.
- [Resumen de ejecución](../results/vera01-2026-11-21T14-05-08.057Z-aBzg7a/summary.json).
- [Auditoría de los resultados aceptados](../results/vera01-2026-11-21T14-05-08.057Z-aBzg7a/audit.jsonl).
- Segunda corrida: [registro](../results/vera01-2026-11-21T16-15-12.346Z-BLv52y/records.jsonl), [resumen](../results/vera01-2026-11-21T16-15-12.346Z-BLv52y/summary.json) y [auditoría](../results/vera01-2026-11-21T16-15-12.346Z-BLv52y/audit.jsonl).
- Métodos reales: [registro](../results/vera01-real-2026-11-21T17-21-17.724Z-E9Hig2/records.jsonl), [resumen](../results/vera01-real-2026-11-21T17-21-17.724Z-E9Hig2/summary.json), [auditoría manual](../results/vera01-real-2026-11-21T17-21-17.724Z-E9Hig2/audit.jsonl) y [manifiesto de fuentes](../benchmarks/vera01/real/manifest.json).
- Los tests generados y la salida cruda de cada runner están en los subdirectorios del [registro de corridas](../results/README.md).
