import re

from vera.__main__ import main
import pytest

from vera.analysis.report import IncompleteBlockError, render_markdown
from vera.store import RunStore
from vera.types import AuditOutcome, Condition

B, RP = Condition.BASELINE, Condition.REPAIR


def sample(make_record, block="estadistico"):
    records = []
    for model in ("llama3.1:8b", "qwen2.5-coder:7b"):
        for t in range(4):
            records.append(make_record(model=model, condition=B, block=block, task_id=f"t{t}",
                                       accepted=t == 0))
            records.append(make_record(model=model, condition=RP, block=block, task_id=f"t{t}",
                                       audit=AuditOutcome.REAL if t % 2 else AuditOutcome.TEST_FREE))
    records.append(make_record(model="llama3.1:8b", condition=RP, block=block, task_id="t9",
                               valid=False))
    records.append(make_record(model="llama3.1:8b", condition=B, block=block, task_id="t9",
                               valid=False))
    return records


def rows(md, first_cell):
    return [line for line in md.splitlines() if line.startswith(f"| {first_cell} |")]


def test_report_contains_one_row_per_model_and_condition(make_record):
    md = render_markdown(sample(make_record), block="estadistico")
    assert "java" in md
    for model in ("llama3.1:8b", "qwen2.5-coder:7b"):
        cond_rows = [r for r in rows(md, model) if "| baseline |" in r or "| repair |" in r]
        assert len(cond_rows) == 2
    assert "Mejora" in md and "Vacíos" in md and "Múltiplo de tokens" in md


def test_report_flags_invalid_runs_count(make_record):
    md = render_markdown(sample(make_record), block="estadistico")
    assert re.search(r"Inválidas", md)
    llama = [r for r in rows(md, "llama3.1:8b") if "baseline" not in r and "repair" not in r]
    qwen = [r for r in rows(md, "qwen2.5-coder:7b") if "baseline" not in r and "repair" not in r]
    assert llama and llama[0].rstrip().endswith("| 2 |")
    assert qwen and qwen[0].rstrip().endswith("| 0 |")
    assert "Ejecuciones inválidas (excluidas de toda tasa): 2" in md


def test_report_ignores_other_blocks(make_record):
    records = sample(make_record) + [make_record(model="intruso", block="extension")]
    md = render_markdown(records, block="estadistico")
    assert "intruso" not in md


def test_cli_report_counts_runs_invalid_and_tmp_files(make_record, tmp_path, monkeypatch, capsys):
    import vera.__main__ as cli

    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    records_dir = tmp_path / "results" / "runs" / "determinista" / "java" / "records"
    store = RunStore(records_dir)
    for record in sample(make_record, block="determinista"):
        store.save(record)
    (records_dir / "a-run.json.tmp").write_text("{", encoding="utf-8")
    (records_dir / "b-run.json.tmp").write_text("", encoding="utf-8")
    assert main(["report", "--block", "determinista", "--language", "java", "--partial"]) == 0
    out = capsys.readouterr().out
    assert "ejecuciones=18 invalidas=2 tmp_sin_cerrar=2" in out
    assert "| llama3.1:8b | baseline |" in out


def ids(records):
    return {r.config.run_id for r in records}


def test_partial_block_is_refused(make_record):
    records = sample(make_record)
    planned = ids(records) | {"estadistico/m/t99/baseline/r1"}
    with pytest.raises(IncompleteBlockError, match="parcial"):
        render_markdown(records, block="estadistico", planned_ids=planned)


def test_partial_block_with_flag_is_marked_and_skips_thesis(make_record):
    records = sample(make_record)
    planned = ids(records) | {"estadistico/m/t99/baseline/r1"}
    md = render_markdown(records, block="estadistico", planned_ids=planned, partial_ok=True)
    assert "(PARCIAL)" in md and "NO son una métrica" in md
    assert "Omitida" in md and "no verificable" not in md


def test_complete_block_declares_engine_prompt_limits_and_thesis(make_record):
    records = sample(make_record, block="determinista")
    md = render_markdown(records, block="determinista", planned_ids=ids(records))
    assert "PARCIAL" not in md
    assert "Motor de `llama3.1:8b`: ollama" in md
    assert "vera01-p1" in md and "AVISO: la versión" in md  # los sintéticos llevan "v"
    assert "Cota de falsos REAL" in md and "No independencia" in md
    assert "docs/entorno-vera01.md" in md and "Known limits of the static" not in md  # solo java
    assert "4/10 → 6/10" in md and "1/10 → 3/10" in md


def test_limits_cite_static_audit_docs_for_python_and_node(make_record):
    records = [make_record(language=lang) for lang in ("python", "node")]
    md = render_markdown(records, block="estadistico", planned_ids=ids(records))
    assert "Known limits of the static Python audit" in md
    assert "Known limits of the static Node audit" in md
    assert "no se comparan otros lenguajes" in md or "no hay cifra comparable" in md


def test_statistical_thesis_figures_and_unverifiable_model(make_record):
    records = sample(make_record) + [make_record(model="otro:1b")]
    md = render_markdown(records, block="estadistico", planned_ids=ids(records))
    assert "17.7 % → 54.7 %" in md and "17.7 % → 22.3 %" in md
    assert [r for r in rows(md, "otro:1b") if "no verificable" in r]


def test_invalid_runs_never_enter_rates_of_complete_block(make_record):
    records = [make_record(condition=B, accepted=False), make_record(condition=RP, valid=False)]
    md = render_markdown(records, block="estadistico", planned_ids=ids(records))
    assert "| m1 | repair | — |" in md
    assert "Ejecuciones inválidas (excluidas de toda tasa): 1" in md


def test_mixed_prompt_versions_are_refused(make_record):
    a = make_record(task_id="a")
    b = make_record(task_id="b")
    object.__setattr__(b.config, "prompt_version", "otra")
    with pytest.raises(IncompleteBlockError, match="versiones del prompt"):
        render_markdown([a, b], block="estadistico", planned_ids=ids([a, b]))


def test_cli_refuses_partial_block_without_flag(make_record, tmp_path, monkeypatch, capsys):
    import vera.__main__ as cli

    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    store = RunStore(tmp_path / "results" / "runs" / "determinista" / "java" / "records")
    for record in sample(make_record, block="determinista"):
        store.save(record)
    assert main(["report", "--block", "determinista", "--language", "java"]) == 1
    captured = capsys.readouterr()
    assert "parcial" in captured.err and "| baseline |" not in captured.out
