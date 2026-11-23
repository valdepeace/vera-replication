"""Pruebas de la extraccion de metodos Java."""
import json

import pytest

from vera.javasrc import build_tasks, extract_method

OVERLOADS = '''
public class A {
    /**
     * Javadoc de la primera.
     */
    public static boolean isEmpty(final CharSequence cs) {
        return cs == null || cs.length() == 0;
    }

    /** Otra sobrecarga. */
    public static boolean isEmpty(final Object[] array) {
        return array == null || array.length == 0;
    }
}
'''


def test_extract_method_selects_exact_overload():
    got = extract_method(OVERLOADS, "isEmpty(Object[])")
    assert "array.length == 0" in got
    assert "CharSequence" not in got
    got = extract_method(OVERLOADS, "isEmpty(CharSequence)")
    assert "cs.length() == 0" in got
    assert "Object[]" not in got


def test_extract_method_excludes_javadoc():
    got = extract_method(OVERLOADS, "isEmpty(CharSequence)")
    assert "/**" not in got and "Javadoc" not in got
    assert got.startswith("public static boolean isEmpty(")
    assert got.endswith("}")


def test_extract_method_handles_nested_braces_and_strings_with_braces():
    src = '''
class B {
    // comentario con { llave
    @Deprecated
    static String f(final String s, final char... cs) throws Exception {
        if (s == null) {
            return "}{";
        }
        char c = '}';
        /* } */
        for (int i = 0; i < 2; i++) { s += "\\"}"; }
        return s;
    }

    static String g() { return "otro"; }
}
'''
    got = extract_method(src, "f(String, char...)")
    assert got.startswith("@Deprecated")
    assert got.endswith("return s;\n    }")
    assert "otro" not in got and "comentario" not in got


def test_extract_method_raises_when_signature_missing():
    with pytest.raises(ValueError):
        extract_method(OVERLOADS, "isEmpty(int)")
    with pytest.raises(ValueError):
        extract_method(OVERLOADS, "noExiste(CharSequence)")


def test_build_tasks_builds_fixed_task_fields(tmp_path):
    pkg = tmp_path / "src/main/java/org/apache/commons/lang3"
    pkg.mkdir(parents=True)
    (pkg / "X.java").write_text(OVERLOADS.replace("class A", "class X"), encoding="utf-8")
    tasks = build_tasks(tmp_path, [("X", "isEmpty(CharSequence)")])
    assert len(tasks) == 1
    t = tasks[0]
    assert t.id == "java-X-isEmpty"
    assert t.test_name == "Generated_X_isEmpty_Test"
    assert (t.language, t.project, t.container, t.import_hint) == (
        "java", "commons-lang", "X", "import org.apache.commons.lang3.X;")
    assert t.focal_name == "isEmpty"
    json.dumps(t.__dict__)
