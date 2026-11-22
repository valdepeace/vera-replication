# Proyectos de Python y Node fijados para la réplica

Cabe señalar que la elección sigue los criterios de la sección 9 de la especificación: proyecto de utilidades de código abierto, fijado a un commit, con suite propia que pasa y unos veinte métodos de oráculo comparable (cadenas, nulos y vacíos, booleanos, caracteres). Los candidatos del plan eran orientativos.

## Proyectos

| | Python | Node |
|---|---|---|
| Proyecto | pydash | validator.js |
| Repositorio | https://github.com/dgilland/pydash | https://github.com/validatorjs/validator.js |
| Commit fijado | `683471ca9c062bd5e1283fbd958928fc2dffe672` | `9ff342479591ca5a43cb30000195bcf55c1bbed9` |
| Licencia | MIT | MIT |
| Clon | `E:\vera-data\pydash` (6 MiB) | `E:\vera-data\validatorjs` (99 MiB con `node_modules` y la compilación) |
| Suite propia | `pytest tests/test_predicates.py tests/test_strings.py`, pasa | `mocha --require @babel/register --recursive`, 323 pruebas, pasa |
| Directorio de validación (adaptador) | `E:\vera-data\pydash\src` | `E:\vera-data\validatorjs\lib` |
| Importación en el test generado | `from pydash import <función>` | `import <función> from './<función>.js';` |

El adaptador copia entero el directorio del proyecto en cada validación; por ello se le entrega solo el código (sin `tests`, `docs` ni `node_modules`). En Node, `lib` es la compilación de Babel (`npm run build`) y su importación por defecto funciona desde un módulo ES.

Preparación de Node (con red, una sola vez): `npm install --no-package-lock` y `npm run build` en `E:\vera-data\validatorjs`. Ninguno de los dos clones se modifica tras la preparación; ni `node_modules` ni la compilación están bajo control de versiones.

Se descartaron de los veinte, por exportar además constantes con nombre y no resolverse la importación por defecto, `isFullWidth`, `isHalfWidth` y `isVariableWidth`; `isAlpha` e `isAlphanumeric` por la misma causa.

El texto fuente de cada tarea omite el docstring de Python (sus ejemplos desvelarían el oráculo) y las importaciones de Node, pero conserva las constantes del módulo.

## Veinte métodos de Python (pydash; los diez primeros, en orden, forman el bloque determinista)

| N.º | Firma |
|---|---|
| 1 | `def is_blank(text: t.Any) -> TypeGuard[str]` |
| 2 | `def is_boolean(value: t.Any) -> TypeGuard[bool]` |
| 3 | `def is_empty(value: t.Any) -> bool` |
| 4 | `def is_none(value: t.Any) -> TypeGuard[None]` |
| 5 | `def is_string(value: t.Any) -> TypeGuard[str]` |
| 6 | `def chars(text: t.Any) -> t.List[str]` |
| 7 | `def clean(text: t.Any) -> str` |
| 8 | `def count_substr(text: t.Any, subtext: t.Any) -> int` |
| 9 | `def decapitalize(text: t.Any) -> str` |
| 10 | `def ends_with(text: t.Any, target: t.Any, position: t.Union[int, None] = None) -> bool` |
| 11 | `def ensure_ends_with(text: t.Any, suffix: t.Any) -> str` |
| 12 | `def ensure_starts_with(text: t.Any, prefix: t.Any) -> str` |
| 13 | `def has_substr(text: t.Any, subtext: t.Any) -> bool` |
| 14 | `def lower_first(text: str) -> str` |
| 15 | `def upper_first(text: str) -> str` |
| 16 | `def capitalize(text: t.Any, strict: bool = True) -> str` |
| 17 | `def starts_with(text: t.Any, target: t.Any, position: int = 0) -> bool` |
| 18 | `def trim(text: t.Any, chars: t.Union[str, None] = None) -> str` |
| 19 | `def trim_start(text: t.Any, chars: t.Union[str, None] = None) -> str` |
| 20 | `def trim_end(text: t.Any, chars: t.Union[str, None] = None) -> str` |

## Veinte métodos de Node (validator.js; los diez primeros, en orden, forman el bloque determinista)

| N.º | Firma |
|---|---|
| 1 | `export default function isEmpty(str, options)` |
| 2 | `export default function isBoolean(str, options = defaultOptions)` |
| 3 | `export default function isAscii(str)` |
| 4 | `export default function isLowercase(str)` |
| 5 | `export default function isUppercase(str)` |
| 6 | `export default function isMultibyte(str)` |
| 7 | `export default function trim(str, chars)` |
| 8 | `export default function isWhitelisted(str, chars)` |
| 9 | `export default function isSurrogatePair(str)` |
| 10 | `export default function isHexadecimal(str)` |
| 11 | `export default function isOctal(str)` |
| 12 | `export default function isNumeric(str, options)` |
| 13 | `export default function isSlug(str)` |
| 14 | `export default function isMD5(str)` |
| 15 | `export default function isLength(str, options)` |
| 16 | `export default function equals(str, comparison)` |
| 17 | `export default function contains(str, elem, options)` |
| 18 | `export default function toBoolean(str, strict)` |
| 19 | `export default function ltrim(str, chars)` |
| 20 | `export default function rtrim(str, chars)` |

## Comprobación de sensibilidad

Orden: `.venv/Scripts/python scripts/check_project_sensitivity.py all`. Verifica que la suite base pasa y que cada mutación manual hace fallar la suite (`vera.sensitivity.mutation_detected`, que restaura siempre el fichero). Resultado del 22 de noviembre de 2026: **5 de 5 mutaciones detectadas en Python y 5 de 5 en Node** (criterio: al menos 3 de 3).

| Lenguaje | Fichero | Mutación |
|---|---|---|
| Python | `predicates.py` | `is_empty`: `or not value` pasa a `or value` |
| Python | `strings.py` | `ensure_ends_with`: condición negada |
| Python | `strings.py` | `count_substr`: `+ 1` |
| Python | `strings.py` | `trim_start`: `lstrip` pasa a `rstrip` |
| Python | `predicates.py` | `is_none`: `is` pasa a `is not` |
| Node | `src/lib/isEmpty.js` | `=== 0` pasa a `=== 1` |
| Node | `src/lib/equals.js` | `===` pasa a `!==` |
| Node | `src/lib/toBoolean.js` | última cláusula `!== ''` pasa a `=== ''` |
| Node | `src/lib/isLowercase.js` | `toLowerCase` pasa a `toUpperCase` |
| Node | `src/lib/isHexadecimal.js` | `+` pasa a `*` en la expresión regular |

Las pruebas de validator.js importan `../src/index`, de modo que las mutaciones de Node se aplican a `src/lib` y no a la compilación `lib`.

## Generación de tareas

`.venv/Scripts/python scripts/check_project_sensitivity.py --build` escribe `benchmarks/vera01/replica/{python,node}/tasks.json`. Las tareas se validaron con los adaptadores reales y un test mínimo sin modelo (20 de 20 en cada lenguaje).

## Pendiente

No se ha ejecutado ningún modelo: el bloque de Java ocupa la GPU y el controlador decide el momento. El punto de control con la persona responsable (paso 5) queda a cargo del controlador: estos proyectos y estos veinte métodos deben enseñársele antes de ejecutar nada.
