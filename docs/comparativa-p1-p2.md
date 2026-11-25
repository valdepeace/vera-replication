# Comparación de p1 y p2 (bloque estadístico, Java)

**Fecha:** 25 de noviembre de 2026. Ejecutado conforme a [prerregistro-vera01-p2.md](prerregistro-vera01-p2.md), sin modificar prompt, código ni parámetros tras el lanzamiento. Informe completo de p2 en `results/runs/estadistico-p2/java/informe.md` (3.000 ejecuciones, 0 inválidas). p1 reúne el bloque `estadistico` y la ampliación Ornith (3.000 ejecuciones).

Cabe señalar que las semillas de p2 difieren de las de p1 y que los intervalos de Newcombe tratan las ejecuciones como independientes: son optimistas y no constituyen contraste de significación.

## Tasa REAL y mejora por modelo (puntos porcentuales, IC 95 % de Newcombe)

| Modelo | Baseline p1 → p2 (Δ) | Repair p1 → p2 (Δ) | Mejora p1 | Mejora p2 |
|---|---|---|---|---|
| gemma4:e4b | 6 % → 57 % (+51,3 [+44,8, +57,2]) | 18 % → 79 % (+60,3 [+53,4, +66,2]) | +12,3 [+7,2, +17,6] | +21,3 [+13,9, +28,4] |
| llama3.1:8b | 8 % → 51 % (+42,7 [+35,9, +48,9]) | 53 % → 63 % (+9,3 [+1,4, +17,1]) | +45,0 [+38,3, +51,2] | +11,7 [+3,7, +19,4] |
| ornith-1.5:9b | 25 % → 43 % (+18,0 [+10,4, +25,3]) | 64 % → 78 % (+13,7 [+6,4, +20,7]) | +39,0 [+31,4, +45,9] | +34,7 [+27,1, +41,7] |
| qwen2.5-coder:7b | 32 % → 55 % (+23,0 [+15,1, +30,5]) | 59 % → 70 % (+11,7 [+4,0, +19,1]) | +26,3 [+18,5, +33,7] | +15,0 [+7,3, +22,5] |
| qwen3:8b | 0 % → 34 % (+34,0 [+28,7, +39,5]) | 75 % → 42 % (−33,0 [−40,1, −25,3]) | +74,7 [+69,3, +79,3] | +7,7 [−0,1, +15,3] |

## Primer fallo de resolución de símbolos en las rescatadas por la reparación

| Modelo | Rescatadas p1 | Símbolos p1 | Rescatadas p2 | Símbolos p2 |
|---|---:|---:|---:|---:|
| gemma4:e4b | 45 | 71 % | 60 | 15 % |
| llama3.1:8b | 138 | 84 % | 45 | 7 % |
| ornith-1.5:9b | 127 | 36 % | 105 | 13 % |
| qwen2.5-coder:7b | 89 | 64 % | 61 | 3 % |
| qwen3:8b | 223 | 97 % | 46 | 9 % |

Mismo criterio heurístico que en p1 (la cifra de p1 se reproduce exactamente).

## Hipótesis prerregistradas

- **H1 (sube el baseline REAL en qwen3, llama y gemma): se cumple.** +34, +43 y +51 puntos, con intervalos muy alejados del cero.
- **H2 (la mejora no es mayor en p2 que en p1): se cumple en llama (−33 puntos) y qwen3 (−67), pero no en gemma**, cuya mejora sube de +12 a +21. Respecto de «sigue siendo positiva», lo es en llama y gemma; en qwen3 el intervalo roza el cero [−0,1, +15,3].
- **H3 (ornith cambia poco): resultado mixto.** El baseline sube 18 puntos y el repair 14, de modo que no cambia poco; la mejora, en cambio, apenas se mueve (−4 puntos).
- **Criterio de que el bucle conserva efecto con p2: se cumple.** La mejora es positiva con intervalo que excluye el cero en 4 de los 5 modelos (todos salvo qwen3:8b); el umbral era 3.

## Lectura

1. La mayor parte de la mejora atribuida al bucle en p1 era corrección de la importación: en llama baja de +45 a +12 y en qwen3 de +75 a +8. Los rescates por símbolos caen del 36-97 % al 3-15 %.
2. Con el import dado, el bucle sigue aportando entre +8 y +35 puntos, y más en gemma y ornith. Es el efecto que cabe atribuirle una vez retirado el defecto del prompt.
3. **qwen3:8b es un caso aparte.** Su tasa del runner es del 53 % → 69 %, pero su tasa REAL es del 34 % → 42 %, porque el 38 % de sus ejecuciones son vacías. Con p2 pasa de no compilar a compilar sin probar nada, y por eso su repair REAL cae respecto de p1 (75 % → 42 %).
4. Salvedades vigentes: una sola máquina, `num_ctx` 8192, prompt reconstruido y auditoría estática, sin mutation score.
