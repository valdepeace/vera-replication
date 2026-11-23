"""Registro de los modelos de VERA-01 y del servidor de Ollama que sirve a cada uno."""
from __future__ import annotations

from vera.types import ModelSpec

# Windows reservó el rango 11435-11534 tras el reinicio del 23 de noviembre de 2026: el servidor de
# E:\ollama-vera\models, que escuchaba en 11435 (bloques vera01-p1), escucha desde entonces en 11431.
_PORT_E = "http://127.0.0.1:11431"  # modelos en E:\ollama-vera\models
_PORT_G = "http://127.0.0.1:11434"  # modelos en G:

MODELS: dict[str, ModelSpec] = {
    spec.name: spec
    for spec in (
        ModelSpec(name="llama3.1:8b", engine="ollama", base_url=_PORT_E),
        ModelSpec(name="gemma4:e4b", engine="ollama", base_url=_PORT_E),
        ModelSpec(name="qwen2.5-coder:7b", engine="ollama", base_url=_PORT_G),
        ModelSpec(name="qwen3:8b", engine="ollama", base_url=_PORT_G),
        # Ampliación: Ornith 1.5 9B (alias local de la conversión GGUF Q4_K_M de bartowski) y el par
        # qwen3-coder:30b / qwen3:30b-a3b, misma arquitectura MoE con y sin especialización en código.
        ModelSpec(name="ornith-1.5:9b", engine="ollama", base_url=_PORT_E),
        ModelSpec(name="qwen3-coder:30b", engine="ollama", base_url=_PORT_G),
        ModelSpec(name="qwen3:30b-a3b", engine="ollama", base_url=_PORT_G),
    )
}
