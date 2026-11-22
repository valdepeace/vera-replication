import re

from vera.__main__ import main
from vera.analysis.report import render_markdown
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
    assert main(["report", "--block", "determinista", "--language", "java"]) == 0
    out = capsys.readouterr().out
    assert "ejecuciones=18 invalidas=2 tmp_sin_cerrar=2" in out
    assert "| llama3.1:8b | baseline |" in out
