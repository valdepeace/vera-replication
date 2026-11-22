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
