"""Informe en Markdown de un bloque: tablas por lenguaje y modelo."""
from __future__ import annotations

import math
from collections import Counter

from vera.prompts import PROMPT_VERSION
from vera.analysis.summary import (
    REPLICA_BLOCKS,
    Rate,
    improves,
    newcombe_diff_ci,
    rates,
    replica_records,
    stability,
    token_multiple,
    vacuous_share,
)
from vera.types import Condition

ENTORNO_DOC = "docs/entorno-vera01.md"


class IncompleteBlockError(RuntimeError):
    """El bloque tiene menos ejecuciones que las planificadas, o mezcla versiones del prompt."""


def planned_run_ids(block_name: str, language: str) -> set[str]:
    """Identificadores de las ejecuciones que planifica el bloque para un lenguaje."""
    from vera.blocks import BLOCKS, expand_block, load_tasks

    return {c.run_id for c in expand_block(BLOCKS[block_name], load_tasks(language))}


# Cifras publicadas de la tesis (docs/paper/1791733959420.pdf; resumen en docs/research.md).
# Bloque determinista (Tabla 4.3): métodos que pasan de 10, (baseline, reparación).
THESIS_DETERMINISTIC = {"qwen2.5-coder:7b": (4, 6), "llama3.1:8b": (1, 3)}
# Bloque estadístico, 300 ejecuciones por celda: porcentajes (ingenua base, ingenua rep.,
# sustantiva base, sustantiva rep.).
THESIS_STATISTICAL = {
    "llama3.1:8b": (17.7, 54.7, 17.7, 22.3),
    "qwen2.5-coder:7b": (25.7, 46.3, 25.0, 45.0),
    "qwen3:8b": (42.7, 52.3, 42.7, 52.0),
    "gemma4:e4b": (31.3, 66.7, 31.3, 65.3),
}


def _rate(rate: Rate | None) -> str:
    return "—" if rate is None else f"{rate.k}/{rate.n} ({rate.rate:.0%})"


def _num(value: float | None, fmt: str) -> str:
    return "—" if value is None or math.isnan(value) else format(value, fmt)


def _improvement(base: Rate | None, repair: Rate | None) -> str:
    if base is None or repair is None:
        return "—"
    diff, lo, hi = newcombe_diff_ci(base.k, base.n, repair.k, repair.n)
    verdict = "sí" if improves(base, repair) else "no"
    return f"{verdict} ({diff:+.2f} [{lo:+.2f}, {hi:+.2f}])"


def _language_section(language: str, records) -> list[str]:
    runner = rates(records, audited=False)
    real = rates(records, audited=True)
    vacuous = vacuous_share(records)
    multiple = token_multiple(records)
    invalid = Counter(r.config.model.name for r in records if not r.valid)
    models = sorted({r.config.model.name for r in records})
    lines = [f"## {language}", "",
             "| Modelo | Condición | Tasa del runner | Tasa sustantiva (REAL) |",
             "|---|---|---|---|"]
    for model in models:
        for condition in Condition:
            key = (model, condition.value)
            lines.append(f"| {model} | {condition.value} | {_rate(runner.get(key))} "
                         f"| {_rate(real.get(key))} |")
    lines += ["", "| Modelo | Mejora (REAL, IC 95 % Newcombe) | Vacíos | Múltiplo de tokens "
              "| Inválidas |", "|---|---|---|---|---|"]
    for model in models:
        base, repair = (real.get((model, c.value)) for c in Condition)
        lines.append(f"| {model} | {_improvement(base, repair)} "
                     f"| {_num(vacuous.get(model), '.0%')} | {_num(multiple.get(model), '.2f')} "
                     f"| {invalid[model]} |")
    lines += ["", f"Ejecuciones inválidas (excluidas de toda tasa): {sum(invalid.values())}", ""]
    return lines


def _conditions_section(records) -> list[str]:
    models = {}
    for r in records:
        models.setdefault(r.config.model.name, r.config.model)
    versions = sorted({r.config.prompt_version for r in records})
    lines = ["## Condiciones declaradas", "",
             f"- Versión del prompt en los registros: {', '.join(versions) or '—'} "
             f"(vigente en el código: `{PROMPT_VERSION}`)."]
    if versions != [PROMPT_VERSION]:
        lines.append(f"- AVISO: la versión de los registros no coincide con `{PROMPT_VERSION}`.")
    for name in sorted(models):
        lines.append(f"- Motor de `{name}`: {models[name].engine} en {models[name].base_url}.")
    for label, values in (
            ("Temperatura", sorted({r.config.temperature for r in records})),
            ("num_ctx", sorted({r.config.num_ctx for r in records})),
            ("num_predict", sorted({r.config.num_predict for r in records})),
            ("keep_alive", sorted({r.config.keep_alive for r in records}))):
        lines.append(f"- {label}: {', '.join(str(v) for v in values) or '—'}.")
    lines += [f"- La versión del servidor del motor no consta en los registros; la del entorno "
              f"se documenta en {ENTORNO_DOC}.", ""]
    return lines


def _limits_section(languages) -> list[str]:
    lines = ["## Límites de lectura", "",
             "- **Cota de falsos REAL.** `REAL` procede de una auditoría estática (el "
             "test contiene `@Test`/aserciones y llama al método focal), no de una "
             "ejecución ni de un mutation score. Las auditorías estáticas son "
             "conservadoras frente a REAL en los casos que cierran (ante la duda no lo conceden), "
             "pero los casos que documentan como abiertos aún pueden inflar REAL; ese posible "
             "exceso de falsos REAL no está cuantificado."]
    if "python" in languages:
        lines.append(f"  - Python: el análisis `ast` deja abiertos casos que pueden dar `REAL` "
                     f"sin que el fallo se propague (condiciones en tiempo de ejecución, "
                     f"aserciones vacuas pero vivas, indirecciones); véase la sección "
                     f"\"Known limits of the static Python audit\" de {ENTORNO_DOC}.")
    if "node" in languages:
        lines.append(f"  - Node: el análisis es textual; no cierra condiciones falsas en tiempo "
                     f"de ejecución, `.then(ok, err)` que traga, helpers importados ni alias "
                     f"dinámicos; véase \"Known limits of the static Node audit\" de {ENTORNO_DOC}.")
    if "java" in languages:
        lines.append("  - Java: la auditoría es estructural; una aserción puede ser vacua "
                     "(no mide el poder de detección).")
        lines.append("- **Prompt sin el paquete de la clase (Java).** El prompt reconstruido exige "
                     "`package org.generated;` e indica la clase bajo prueba solo por su nombre "
                     "(por ejemplo `BooleanUtils`), sin su paquete `org.apache.commons.lang3`. El "
                     "modelo debe deducirlo por sí mismo: buena parte de los fallos del primer "
                     "intento son errores de compilación por una importación equivocada y no de "
                     "calidad de los tests, de modo que la tasa mide también si el modelo conoce "
                     "Commons Lang. Afecta de forma muy desigual a los modelos (véase "
                     "docs/findings.md) y las tasas absolutas, en particular el 0 % de baseline de "
                     "qwen3:8b, deben leerse con esta salvedad.")
    lines += ["- **No independencia.** Los intervalos de Newcombe tratan las ejecuciones como "
              "independientes, pero comparten método focal (mismos métodos en cada celda y "
              "repeticiones del mismo método), modelo y comando de validación, y las "
              "condiciones se emparejan por método. Los intervalos son por ello optimistas "
              "(más estrechos de lo debido); en el bloque determinista las repeticiones, "
              "además, no son independientes.",
              "- Una sola máquina, un solo contexto (`num_ctx` 8192), prompts reconstruidos, sin "
              "mutation score. Las ejecuciones con `valid=False` quedan fuera de toda tasa.", ""]
    return lines


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} %"


def _thesis_section(block: str, records) -> list[str]:
    lines = ["## Comparación con la tesis", "",
             "Fuente: tesis de González Sánchez (UNED, 2026), docs/paper/1791733959420.pdf; "
             "resumen en docs/research.md. La tesis es de Java: no se comparan otros lenguajes. "
             "No se afirma coincidencia; una cifra que no consta publicada se marca "
             "\"no verificable\" y no se sustituye por ninguna estimación.", ""]
    java = [r for r in records if r.config.task.language == "java"]
    if not java:
        return lines + ["No hay ejecuciones de Java: no hay cifra comparable.", ""]
    runner = rates(java, audited=False)
    real = rates(java, audited=True)
    models = sorted({r.config.model.name for r in java})

    def pair(table, model):
        cells = [table.get((model, c.value)) for c in Condition]
        return " → ".join("—" if c is None else f"{c.rate:.1%}" for c in cells)

    if block == "determinista":
        lines += ["| Modelo | Tesis (n.º de métodos de 10, baseline → reparación) | Réplica, runner | "
                  "Réplica, REAL |", "|---|---|---|---|"]
        for model in models:
            ref = THESIS_DETERMINISTIC.get(model)
            thesis = f"{ref[0]}/10 → {ref[1]}/10" if ref else "no verificable"
            lines.append(f"| {model} | {thesis} | {pair(runner, model)} | {pair(real, model)} |")
    else:
        lines += ["| Modelo | Tesis ingenua (base → rep.) | Tesis sustantiva (base → rep.) | "
                  "Réplica, runner | Réplica, REAL |", "|---|---|---|---|---|"]
        for model in models:
            ref = THESIS_STATISTICAL.get(model)
            naive = f"{_pct(ref[0])} → {_pct(ref[1])}" if ref else "no verificable"
            subst = f"{_pct(ref[2])} → {_pct(ref[3])}" if ref else "no verificable"
            lines.append(f"| {model} | {naive} | {subst} | {pair(runner, model)} | "
                         f"{pair(real, model)} |")
    return lines + [""]


def render_markdown(records, *, block: str, planned_ids, partial_ok: bool = False,
                    include: tuple[str, ...] = ()) -> str:
    """Informe de un bloque. `planned_ids` (los run_id planificados) es obligatorio: sin plan no
    hay forma de saber si el bloque está completo. Se niega a presentar tasas de un bloque con
    menos ejecuciones que las planificadas, salvo `partial_ok`, que las marca con un aviso
    explícito de que no son una métrica. Las versiones del prompt mezcladas se rechazan siempre.
    `include` suma al informe, de forma explícita, los registros de otros bloques (la ampliación);
    la exigencia de un único prompt y de un plan completo se aplica a la unión."""
    if planned_ids is None:
        raise ValueError("planned_ids es obligatorio: sin plan no se puede comprobar la completitud")
    blocks = (block, *include)
    records = [r for r in records if r.config.block in blocks]
    versions = {r.config.prompt_version for r in records}
    if len(versions) > 1:
        raise IncompleteBlockError(
            f"el bloque {block} mezcla versiones del prompt ({', '.join(sorted(versions))})")
    present = {r.config.run_id for r in records}
    planned = set(planned_ids)
    missing = len(planned - present)
    if missing and not partial_ok:
        raise IncompleteBlockError(
            f"el bloque {block} tiene {len(planned & present)} de {len(planned)} ejecuciones "
            f"planificadas: corrida parcial o interrumpida; no se presentan tasas")
    title = f"# Informe del bloque {' + '.join(blocks)}"
    lines = [title + (" (PARCIAL)" if missing else ""), ""]
    if missing:
        lines += [f"> AVISO: corrida PARCIAL ({len(planned & present)} de {len(planned)} "
                  f"ejecuciones planificadas). Las tasas siguientes NO son una métrica y no "
                  f"deben citarse.", ""]
    lines += [f"Ejecuciones: {len(records)} (válidas: {sum(r.valid for r in records)}; "
              f"planificadas: {len(planned)})", ""]
    lines += _conditions_section(records)
    if block == "determinista":
        lines += [f"Estabilidad entre repeticiones: {_num(stability(records), '.0%')}", ""]
    languages = sorted({r.config.task.language for r in records})
    for language in languages:
        lines += _language_section(language, [r for r in records
                                              if r.config.task.language == language])
    if not missing:
        lines += _thesis_section(block, records)
    else:
        lines += ["## Comparación con la tesis", "",
                  "Omitida: una corrida parcial no se compara con la tesis.", ""]
    lines += _limits_section(languages)
    return "\n".join(lines)
