# Prerregistro del bloque estadístico con el prompt vera01-p2

**Fecha de redacción:** 23 de noviembre de 2026, antes de lanzar la primera ejecución del bloque. El *commit* que incorpora este documento precede al de cualquier registro del bloque.

## Motivo

Cabe señalar que el prompt `vera01-p1` indica la clase bajo prueba solo por su nombre, sin su paquete (véase la sección *Limitación del prompt* de [findings.md](findings.md)). En el bloque estadístico ampliado, la proporción de ejecuciones rescatadas por la reparación cuyo primer fallo fue de resolución de símbolos va del 36 % (`ornith-1.5:9b`) al 97 % (`qwen3:8b`). Se desconoce, pues, cuánto de la mejora atribuida al bucle de reparación se debe a corregir esa importación y cuánto a reparar tests mal escritos.

## Qué cambia

Una sola línea del prompt de Java. Queda la regla de importación así:

| Versión | Línea |
|---|---|
| `vera01-p1` | `Import the class under test as StringUtils.` |
| `vera01-p2` | `Import the class under test with: import org.apache.commons.lang3.StringUtils;` |

Todo lo demás es idéntico a p1: prompt del sistema, esquema de salida, instrucciones de reparación, tareas (20 métodos), temperatura 0,7, `num_ctx` 8192, `num_predict` 2048, `keep_alive` 30 m, 15 repeticiones por método y condición, presupuesto de 3 reparaciones, validador y auditoría. Una prueba automática verifica que el prompt de p2 difiere del de p1 en esa única línea.

## Qué se ejecuta

- Bloque `estadistico-p2`, Java: 5 modelos × 20 métodos × 2 condiciones × 15 repeticiones = **3.000 ejecuciones**.
- Modelos: `llama3.1:8b`, `qwen2.5-coder:7b`, `qwen3:8b`, `gemma4:e4b` y `ornith-1.5:9b`, con las mismas pesas que en p1 (los resúmenes criptográficos de llama y gemma coinciden con los del manifiesto de p1).
- Cambio de infraestructura: el servidor de `E:\ollama-vera\models` escucha en el puerto 11431, pues Windows reservó el rango 11435-11534. Semillas: la semilla deriva del identificador de la ejecución, que incluye el nombre del bloque, de modo que **las semillas de p2 difieren de las de p1** y la comparación entre ambas incluye ruido de muestreo.

## Hipótesis, formuladas antes de ver resultados

- **H1.** Con p2 sube la tasa REAL de baseline de los modelos cuyo primer fallo era de resolución de símbolos (`qwen3:8b`, `llama3.1:8b`, `gemma4:e4b`).
- **H2.** La mejora de reparación (repair menos baseline) en p2 es menor o igual que en p1 en esos mismos modelos; si el bucle aportase algo más que corregir la importación, seguirá siendo positiva.
- **H3.** `ornith-1.5:9b`, el menos afectado, cambia poco entre p1 y p2.

Ninguna hipótesis se da por confirmada ni se descarta por una sola cifra: se informa la magnitud con su intervalo.

## Resultados que se informarán

1. Tasa REAL por modelo y condición, con la mejora y su intervalo de Newcombe del 95 %, como en el informe de p1.
2. Diferencia entre p1 y p2 por modelo, en baseline, en repair y en la mejora. Los intervalos tratan las ejecuciones como independientes y son optimistas; no se emplean contrastes de significación.
3. Proporción de rescates cuyo primer fallo fue de resolución de símbolos, con el mismo criterio heurístico que en p1.
4. **Criterio de que el bucle conserva efecto con p2:** mejora positiva con intervalo del 95 % que excluya el cero en al menos tres de los cinco modelos.

## Reglas

- No se modifican el prompt, el código ni los parámetros una vez lanzado el bloque. Si aparece otro defecto, se documenta y, de corregirse, será una versión nueva (`vera01-p3`) y otro bloque.
- Un fallo de infraestructura se reintenta una sola vez, como establece el ejecutor.
- Se publican todos los resultados, cualquiera que sea su sentido, junto a los de p1, que permanecen inalterados.
- No se afirma que p2 sea el prompt de la tesis, cuyo texto no es público; solo que da el paquete de la clase.
