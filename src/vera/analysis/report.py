"""Informe en Markdown de un bloque: tablas por lenguaje y modelo."""
from __future__ import annotations

import math
from collections import Counter

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


def render_markdown(records, *, block: str) -> str:
    if block in REPLICA_BLOCKS:
        records = replica_records(records)
    records = [r for r in records if r.config.block == block]
    lines = [f"# Informe del bloque {block}", "",
             f"Ejecuciones: {len(records)} (válidas: {sum(r.valid for r in records)})", ""]
    if block == "determinista":
        lines += [f"Estabilidad entre repeticiones: {_num(stability(records), '.0%')}", ""]
    for language in sorted({r.config.task.language for r in records}):
        lines += _language_section(language, [r for r in records
                                              if r.config.task.language == language])
    return "\n".join(lines)
