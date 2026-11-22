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
4. Con red, una sola vez más (calentamiento de Surefire, Tarea 7): `go-offline` y `test-compile` no descargan el proveedor de JUnit 5 de Surefire, de modo que toda ejecución offline de tests fallaba con `Cannot access central ... in offline mode and the artifact org.apache.maven.surefire:surefire-junit-platform:jar:3.5.4 has not been downloaded from it before`. Se ejecutó, con un test trivial en `src/test/java/org/generated/ProbeOkTest.java` (retirado después), el comando del adaptador sin `-o`:
   `mvn -B -q -Dmaven.repo.local=E:/vera-data/m2 -Drat.skip=true -Dtest=ProbeOkTest -Dsurefire.failIfNoSpecifiedTests=false test`
   Añadió al repositorio local (unos 0,7 MiB): `org.apache.maven.surefire:surefire-junit-platform:3.5.4`, `org.apache.maven.surefire:common-java5:3.5.4`, `org.apache.maven.surefire:surefire-providers:3.5.4` (pom) y `org.junit.platform:junit-platform-{commons,engine,launcher}:1.12.1`. Tamaño resultante de `E:\vera-data\m2`: 354 MiB (358.771.073 bytes).
5. Verificar: `.venv/Scripts/python scripts/env/check_env.py` (código 0 si el commit es el fijado, ambos servidores contestan, están los 4 modelos y una validación offline real con Surefire ejecuta exactamente un test JUnit 5 trivial en `src/test/java/org/generated/`, con el comando exacto del adaptador, `-Drat.skip=true` incluido; el fichero se retira siempre. Si falta un artefacto en `E:\vera-data\m2`, el fallo lo nombra).

Comando de validación del adaptador (`src/vera/adapters/java_maven.py`, Tarea 7c), desde `E:\vera-data\commons-lang`:
`mvn -o -B -q -Dmaven.repo.local=E:/vera-data/m2 -Drat.skip=true -Denforcer.skip=true -Dmaven.antrun.skip=true -Dremoteresources.skip=true -Dmaven.buildNumber.skip=true -Dbundle.skip=true -Dmaven.compiler.useIncrementalCompilation=false -Dtest=<test_name> -Dsurefire.failIfNoSpecifiedTests=false test`.
Con `useIncrementalCompilation=false` javac compila solo las fuentes obsoletas (el test generado), contra las clases de `target/test-classes`; el adaptador suprime después las clases nacidas del test generado. Requiere que `target/` esté construido (paso 3); si se vacía, la primera validación recompila el módulo de test entero, pues todas sus fuentes quedan obsoletas (comportamiento deducido, no medido).

No se toca el `PATH` global ni `%USERPROFILE%\.m2`. La lógica vive en `src/vera/envinfo.py`; `scripts/env/check_env.py` es un envoltorio fino.

## Tareas de Java fijadas

Las veinte firmas del plan existen y son inequívocas en el commit fijado; no se sustituyó ninguna. Cabe señalar que `StringUtils.equals` y `StringUtils.equalsIgnoreCase` figuran como `@Deprecated` en dicho commit; se conservan, y la anotación permanece en el `focal_source` (sin Javadoc). `scripts/build_java_tasks.py` (envoltorio de `src/vera/javasrc.py`) escribe `benchmarks/vera01/replica/java/tasks.json`.

## Limpieza final

Previa confirmación expresa: detener el servidor 11435 y borrar `E:\ollama-vera` y `E:\vera-data`. Inventario completo en `docs/ollama-vera-models.md`.


### Known limits of the static Node audit

Cabe señalar que `audit_node` es un análisis textual, no una ejecución: ante la duda resuelve hacia TEST_FREE o ASSERTION_FREE (se prefiere infravalorar REAL). Cierra, entre otros, estos patrones: `.catch(...)` sin relanzar, `return`/`throw`/`process.exit` incondicional previo, `if (false|0|null)`, `while (false)`, funciones locales nunca invocadas, helpers locales que envuelven la llamada en try/catch sin relanzar, `skip`/`todo` (opciones, `t.skip()`, `t.todo()`, `describe.skip`), catch que no relanza, `finally { return; }`, `.unref()`/`clearTimeout` del temporizador, `process.exit`/`process.on('exit'|'uncaughtException'|'unhandledRejection')` en cualquier parte del fichero, `assert` local falso y `assert.x = ...`.

Lo que no puede cerrarse estáticamente (y por tanto puede contarse como REAL aun sin propagar el fallo):

- Condiciones en tiempo de ejecución que resultan falsas: `if (process.env.X) { assert... }`, `if (flag)` con `flag` falso, `if (1 > 2)`, `if (!!0)`.
- `.then(onOk, onErr)` con segundo argumento que traga, y `.catch` cuyo callback es un identificador que no relanza (se tratan como tragado salvo `fail`/`reject`; el resto de formas indirectas no).
- Funciones de usuario que reciben el callback con la aserción y nunca lo invocan, salvo que sean helpers con try/catch sin relanzar del mismo fichero; helpers importados de otros módulos.
- `return`/`throw` condicionales cuya condición es siempre cierta (`if (true) return;` se trata como condicional).
- Funciones referenciadas solo como valor (`const f = () => ...; list.push(f)`) se dan por no invocadas; pasadas a invocadores no listados (más allá de then, setTimeout, forEach, map, test, it...) también.
- Aserciones en callbacks de eventos (`emitter.on(...)`) que nadie emite; promesas que no se resuelven nunca; `await` de una promesa que el propio test cancela.
- Tests pasados por referencia a una función importada de otro módulo, o resueltos mediante alias dinámicos (`const t = cond ? test : () => {}`).
- Sombreado de `assert` mediante parámetros o ámbitos interiores, o mutación indirecta (`Object.assign(assert, ...)`).
- Mutación dinámica del código: queda fuera de alcance (no hay auditoría dinámica).

### Known limits of the static Python audit

`audit_python` decides by static analysis (`ast`) and follows one rule: every doubt is resolved toward `TEST_FREE` or `ASSERTION_FREE`, so `REAL` is under-counted and never inflated. It discards: tests disabled by `skip`, `skipif` (literal-true or undecidable condition), `skipUnless`, `xfail` and `expectedFailure` decorators (also on the class or via module-level `pytestmark`); async tests; assertions after `return`, `raise`, `pytest.skip`, `self.skipTest`, `sys.exit` and similar, including when only one branch of an `if` does so; `if False/0/None` blocks; `try` bodies whose handler swallows `AssertionError` (bare `except`, `Exception`, `BaseException`, `AssertionError`) without a top-level `raise`; `contextlib.suppress`; nested functions never called by name in the test; lambdas; `for` over a literal empty collection; and module-level exit, raise or `pytestmark` skip.

What cannot be closed statically (these can still yield `REAL` without enforcing anything, or the opposite):

- Conditions decided at run time (`if flag:` where `flag` is false at run time, `while` with a non-literal condition, loops over an iterable that happens to be empty such as `for x in cases:` with `cases = []`).
- Aliased or indirect calls: a skip, exit or swallowing wrapper defined by the test itself, `getattr`, a helper that catches `AssertionError`, a nested function reached through an alias, a method called as `self.helper()`, or a lambda stored and called later (treated as never run, which under-counts).
- Assertions that are vacuous but syntactically alive (`assert slugify(x) or True`, `assert slugify(x) is not None`, a comparison of the result with itself). The audit checks that the focal call takes part in an assertion, not that the assertion can fail.
- Branches in `match` statements and in `except` handlers are ignored (under-count), and the data-flow hop follows a single assignment of a plain local name.
- The harness treats pytest exit code 5 as a runner pass; dynamic effects such as fixtures that skip (`pytest.skip` inside a fixture) or `conftest.py` hooks are not modelled.
