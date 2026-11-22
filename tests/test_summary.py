import pytest

from vera.analysis.summary import (
    Rate,
    improves,
    newcombe_diff_ci,
    rates,
    replica_records,
    stability,
    token_multiple,
    vacuous_share,
)
from vera.types import AuditOutcome, Condition

B, RP = Condition.BASELINE, Condition.REPAIR


def test_rates_exclude_invalid_runs(make_record):
    records = [make_record(accepted=True), make_record(accepted=False),
               make_record(accepted=False, valid=False), make_record(accepted=True, valid=False)]
    r = rates(records, audited=False)[("m1", "baseline")]
    assert (r.k, r.n, r.rate) == (1, 2, 0.5)


def test_audited_rates_count_only_real(make_record):
    records = [make_record(audit=AuditOutcome.REAL), make_record(audit=AuditOutcome.TEST_FREE),
               make_record(audit=AuditOutcome.EMPTY), make_record(accepted=False)]
    assert rates(records, audited=True)[("m1", "baseline")] == Rate(k=1, n=4, rate=0.25)
    assert rates(records, audited=False)[("m1", "baseline")] == Rate(k=3, n=4, rate=0.75)


def test_rates_are_keyed_by_model_and_condition(make_record):
    records = [make_record(model="a", condition=B), make_record(model="a", condition=RP),
               make_record(model="b", condition=RP, accepted=False)]
    got = rates(records, audited=False)
    assert set(got) == {("a", "baseline"), ("a", "repair"), ("b", "repair")}
    assert got[("b", "repair")].k == 0


def test_newcombe_contains_diff_and_is_ordered():
    for k1, n1, k2, n2 in [(5, 20, 12, 20), (0, 20, 0, 20), (20, 20, 3, 20), (1, 7, 9, 13)]:
        diff, lo, hi = newcombe_diff_ci(k1, n1, k2, n2)
        assert diff == pytest.approx(k2 / n2 - k1 / n1)
        assert -1.0 <= lo < diff < hi <= 1.0


def test_newcombe_symmetry():
    diff, lo, hi = newcombe_diff_ci(5, 20, 12, 20)
    rdiff, rlo, rhi = newcombe_diff_ci(12, 20, 5, 20)
    assert rdiff == pytest.approx(-diff)
    assert rlo == pytest.approx(-hi)
    assert rhi == pytest.approx(-lo)


def test_newcombe_reference_value():
    # Calculado a mano en el informe de la tarea 10 (Newcombe, método 10).
    diff, lo, hi = newcombe_diff_ci(5, 20, 12, 20)
    assert diff == pytest.approx(0.35)
    assert lo == pytest.approx(0.0444, abs=1e-4)
    assert hi == pytest.approx(0.5778, abs=1e-4)


def test_improves_true_for_0_of_20_vs_18_of_20():
    assert improves(Rate(0, 20, 0.0), Rate(18, 20, 0.9))
    assert newcombe_diff_ci(0, 20, 18, 20)[1] > 0


def test_improves_false_for_5_of_20_vs_6_of_20():
    assert not improves(Rate(5, 20, 0.25), Rate(6, 20, 0.3))
    _, lo, hi = newcombe_diff_ci(5, 20, 6, 20)
    assert lo < 0 < hi


def test_improves_false_when_a_group_is_empty():
    assert not improves(Rate(0, 0, float("nan")), Rate(18, 20, 0.9))


def test_vacuous_share_is_per_model(make_record):
    records = [make_record(model="a", audit=AuditOutcome.REAL),
               make_record(model="a", audit=AuditOutcome.TEST_FREE),
               make_record(model="a", accepted=False),
               make_record(model="a", audit=AuditOutcome.NO_FOCAL, valid=False),
               make_record(model="b", audit=AuditOutcome.REAL)]
    assert vacuous_share(records) == {"a": 0.5, "b": 0.0}


def test_token_multiple_is_ratio_of_means(make_record):
    records = [make_record(condition=B, prompt_tokens=10, completion_tokens=0),
               make_record(condition=B, prompt_tokens=30, completion_tokens=0),
               make_record(condition=RP, prompt_tokens=50, completion_tokens=10),
               make_record(condition=RP, prompt_tokens=1000, completion_tokens=0, valid=False)]
    assert token_multiple(records) == {"m1": pytest.approx(3.0)}


def test_stability_all_equal_is_one(make_record):
    records = [make_record(block="determinista", task_id=t, repetition=r, condition=c,
                           accepted=(t == "t1"))
               for t in ("t1", "t2") for c in (B, RP) for r in (1, 2)]
    assert stability(records) == 1.0


def test_stability_counts_disagreeing_pairs(make_record):
    records = [make_record(block="determinista", repetition=1, accepted=True),
               make_record(block="determinista", repetition=2, accepted=False),
               make_record(block="determinista", task_id="t2", repetition=1),
               make_record(block="determinista", task_id="t2", repetition=2),
               make_record(block="estadistico", task_id="t3", repetition=1, accepted=False),
               make_record(block="estadistico", task_id="t3", repetition=2)]
    assert stability(records) == 0.5


def test_replica_records_excludes_extension_blocks(make_record):
    records = [make_record(block="determinista"), make_record(block="estadistico"),
               make_record(block="extension"), make_record(block="vera01b-llama-server")]
    assert [r.config.block for r in replica_records(records)] == ["determinista", "estadistico"]
