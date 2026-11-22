"""Tasas, intervalos y medidas descriptivas de las ejecuciones (solo librería estándar)."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from statistics import mean

from vera.types import AuditOutcome, Condition, RunRecord

REPLICA_BLOCKS = ("determinista", "estadistico")


@dataclass
class Rate:
    k: int
    n: int
    rate: float


def replica_records(records) -> list[RunRecord]:
    """Solo los registros de la réplica; la extensión se informa aparte."""
    return [r for r in records if r.config.block in REPLICA_BLOCKS]


def _success(record: RunRecord, audited: bool) -> bool:
    if audited:
        return record.accepted and record.audit is AuditOutcome.REAL
    return record.accepted


def rates(records, *, audited: bool) -> dict[tuple[str, str], Rate]:
    """Tasa de éxito por (modelo, condición); las ejecuciones inválidas nunca cuentan."""
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in records:
        if not r.valid:
            continue
        cell = counts[(r.config.model.name, r.config.condition.value)]
        cell[0] += _success(r, audited)
        cell[1] += 1
    return {key: Rate(k, n, k / n) for key, (k, n) in counts.items()}


def _wilson(k: int, n: int, z: float) -> tuple[float, float]:
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int,
                     z: float = 1.96) -> tuple[float, float, float]:
    """Diferencia p2 - p1 con el intervalo híbrido de Newcombe (método 10),
    construido con las cotas de Wilson de cada proporción."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = _wilson(k1, n1, z)
    l2, u2 = _wilson(k2, n2, z)
    diff = p2 - p1
    lo = diff - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = diff + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return diff, lo, hi


def improves(base: Rate, repair: Rate) -> bool:
    """Mejora: diferencia positiva con el límite inferior del IC del 95 % por encima de cero."""
    if base.n == 0 or repair.n == 0:
        return False
    diff, lo, _ = newcombe_diff_ci(base.k, base.n, repair.k, repair.n)
    return diff > 0 and lo > 0


def vacuous_share(records) -> dict[str, float]:
    """Por modelo, fracción de las ejecuciones válidas aceptadas que la auditoría no da por REAL."""
    accepted: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        if r.valid and r.accepted:
            accepted[r.config.model.name].append(r.audit is not AuditOutcome.REAL)
    return {model: sum(flags) / len(flags) for model, flags in accepted.items()}


def token_multiple(records) -> dict[str, float]:
    """Por modelo, tokens medios (entrada y salida) de REPAIR entre los de BASELINE."""
    tokens: dict[tuple[str, Condition], list[int]] = defaultdict(list)
    for r in records:
        if r.valid:
            tokens[(r.config.model.name, r.config.condition)].append(
                r.total_prompt_tokens + r.total_completion_tokens)
    out = {}
    for model in {m for m, _ in tokens}:
        base, repair = tokens.get((model, Condition.BASELINE)), tokens.get((model, Condition.REPAIR))
        if base and repair and mean(base) > 0:
            out[model] = mean(repair) / mean(base)
    return out


def stability(records) -> float:
    """Fracción de pares de repeticiones del bloque determinista con el mismo resultado del
    runner; NaN si no hay pares."""
    groups: dict[tuple[str, str, Condition], list[bool]] = defaultdict(list)
    for r in records:
        if r.valid and r.config.block == "determinista":
            groups[(r.config.model.name, r.config.task.id, r.config.condition)].append(r.accepted)
    pairs = [a == b for outcomes in groups.values() for a, b in combinations(outcomes, 2)]
    return sum(pairs) / len(pairs) if pairs else math.nan
