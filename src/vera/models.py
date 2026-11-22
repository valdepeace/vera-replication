"""Registro de los modelos de VERA-01 y del servidor de Ollama que sirve a cada uno."""
from __future__ import annotations

from vera.types import ModelSpec

_PORT_E = "http://127.0.0.1:11435"  # modelos en E:\ollama-vera\models
_PORT_G = "http://127.0.0.1:11434"  # modelos en G:

MODELS: dict[str, ModelSpec] = {
    spec.name: spec
    for spec in (
        ModelSpec(name="llama3.1:8b", engine="ollama", base_url=_PORT_E),
        ModelSpec(name="gemma4:e4b", engine="ollama", base_url=_PORT_E),
        ModelSpec(name="qwen2.5-coder:7b", engine="ollama", base_url=_PORT_G),
        ModelSpec(name="qwen3:8b", engine="ollama", base_url=_PORT_G),
    )
}
