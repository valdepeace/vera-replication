from vera.types import Condition, ModelSpec, RunConfig, Task


def make_config(condition=Condition.BASELINE, repetition=0):
    task = Task(
        id="java-StringUtils-isEmpty",
        language="java",
        project="commons-lang",
        focal_name="isEmpty",
        focal_source="public static boolean isEmpty(CharSequence cs) { return cs == null || cs.length() == 0; }",
        container="org.apache.commons.lang3.StringUtils",
        test_name="StringUtilsIsEmptyTest",
        import_hint="import org.apache.commons.lang3.StringUtils;",
    )
    model = ModelSpec(name="llama3.1:8b", engine="ollama", base_url="http://localhost:11434")
    return RunConfig(
        block="determinista",
        model=model,
        task=task,
        condition=condition,
        repetition=repetition,
        seed=42,
        temperature=0.0,
        prompt_version="v1",
    )


def test_condition_max_repairs():
    assert Condition.BASELINE.max_repairs == 0
    assert Condition.REPAIR.max_repairs == 3


def test_run_id_differs_per_condition_and_repetition():
    ids = {
        make_config(Condition.BASELINE, 0).run_id,
        make_config(Condition.REPAIR, 0).run_id,
        make_config(Condition.BASELINE, 1).run_id,
        make_config(Condition.REPAIR, 1).run_id,
    }
    assert len(ids) == 4


def test_run_id_format():
    assert (
        make_config().run_id
        == "determinista/llama3.1:8b/java-StringUtils-isEmpty/baseline/r0"
    )
