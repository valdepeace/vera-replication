"""Cliente de Ollama sobre urllib (solo biblioteca estándar)."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

from vera.engines.base import ChatOptions, ChatResult, EngineError

_NS = 1_000_000_000


class OllamaEngine:
    def __init__(self, base_url: str, timeout_s: float = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        options: ChatOptions,
        json_schema: dict | None,
    ) -> ChatResult:
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": options.keep_alive,
            "options": {
                "num_ctx": options.num_ctx,
                "num_predict": options.num_predict,
                "temperature": options.temperature,
                "seed": options.seed,
            },
        }
        if json_schema is not None:
            payload["format"] = json_schema
        body = self._post_chat(payload, model)
        return ChatResult(
            text=(body.get("message") or {}).get("content", ""),
            prompt_tokens=int(body.get("prompt_eval_count", 0)),
            completion_tokens=int(body.get("eval_count", 0)),
            load_seconds=body.get("load_duration", 0) / _NS,
            total_seconds=body.get("total_duration", 0) / _NS,
            truncated=body.get("done_reason") == "length",
        )

    def unload(self, model: str) -> None:
        """Descarga el modelo de la memoria del servidor (keep_alive 0) sin esperar a que caduque."""
        self._post_chat({"model": model, "messages": [], "keep_alive": 0}, model)

    def _post_chat(self, payload: dict, model: str) -> dict:
        req = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise EngineError("model_missing", f"modelo no disponible: {model}") from exc
            raise EngineError("server", f"HTTP {exc.code}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise EngineError("timeout", str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise EngineError("timeout", str(exc.reason)) from exc
            raise EngineError("connection", str(exc.reason)) from exc
        except (ConnectionError, OSError) as exc:
            raise EngineError("connection", str(exc)) from exc
        except ValueError as exc:
            raise EngineError("server", f"respuesta no válida: {exc}") from exc
        return body
