import random

import pytest

pytest.importorskip("statsmodels")

from vera.analysis.mixed import MixedResult, mixed_model  # noqa: E402
from vera.types import AuditOutcome, Condition  # noqa: E402

pytestmark = pytest.mark.analysis


def synthetic(make_record, p_base, p_repair, *, seed=20261122):
    rng = random.Random(seed)
    records = []
    for model in ("m1", "m2"):
        for method in range(10):
            shift = rng.uniform(-0.1, 0.1)  # dificultad propia del método
            for condition, p in ((Condition.BASELINE, p_base), (Condition.REPAIR, p_repair)):
                for rep in range(8):
                    ok = rng.random() < min(max(p + shift, 0.0), 1.0)
                    records.append(make_record(model=model, task_id=f"t{method}",
                                               condition=condition, repetition=rep,
                                               accepted=ok, audit=AuditOutcome.REAL))
    return records


def test_mixed_model_detects_strong_effect(make_record):
    result = mixed_model(synthetic(make_record, 0.2, 0.8))
    assert isinstance(result, MixedResult)
    assert result.method
    assert result.odds_ratio > 1
    assert result.log_odds > 0 and result.se > 0


def test_mixed_model_falls_back_to_gee(make_record, monkeypatch):
    import vera.analysis.mixed as mixed

    def no_convergence(df, formula):
        raise mixed.warnings.warn("no converge", RuntimeWarning)

    monkeypatch.setattr(mixed, "_bayes", no_convergence)
    result = mixed_model(synthetic(make_record, 0.2, 0.8))
    assert result.method.startswith("GEE")
    assert result.odds_ratio > 1


def test_mixed_model_without_effect_is_near_one(make_record):
    result = mixed_model(synthetic(make_record, 0.5, 0.5))
    assert result.method
    assert 0.5 < result.odds_ratio < 2
