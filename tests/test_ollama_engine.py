import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from vera.engines.base import ChatOptions, EngineError
from vera.engines.ollama import OllamaEngine

OPTS = ChatOptions(num_ctx=8192, num_predict=2048, temperature=0.0, seed=7, keep_alive="30m")
SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}}}
MSGS = [{"role": "user", "content": "hola"}]


@pytest.fixture
def server():
    state = {"status": 200, "reply": {}, "received": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            state["received"] = (self.path, json.loads(self.rfile.read(n)))
            body = json.dumps(state["reply"]).encode()
            self.send_response(state["status"])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    yield state
    httpd.shutdown()
    httpd.server_close()


def test_payload_has_expected_fields(server):
    server["reply"] = {"message": {"content": "x"}, "done_reason": "stop"}
    OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=SCHEMA)
    path, body = server["received"]
    assert path == "/api/chat"
    assert body["stream"] is False and body["think"] is False
    assert body["format"] == SCHEMA
    assert body["keep_alive"] == "30m"
    assert body["options"] == {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.0, "seed": 7}


def test_maps_counts_and_durations(server):
    server["reply"] = {
        "message": {"content": "hola"}, "done_reason": "stop",
        "prompt_eval_count": 11, "eval_count": 22,
        "load_duration": 1_500_000_000, "total_duration": 4_000_000_000,
    }
    r = OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert (r.text, r.prompt_tokens, r.completion_tokens) == ("hola", 11, 22)
    assert r.load_seconds == 1.5 and r.total_seconds == 4.0
    assert r.truncated is False


def test_truncated_when_done_reason_is_length(server):
    server["reply"] = {"message": {"content": "cortado"}, "done_reason": "length"}
    r = OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert r.truncated is True


def test_http_500_raises_server_error(server):
    server["status"] = 500
    with pytest.raises(EngineError) as e:
        OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert e.value.kind == "server"


def test_http_500_message_keeps_server_error_body(server):
    server["status"] = 500
    server["reply"] = {"error": "llama runner process has terminated"}
    with pytest.raises(EngineError) as e:
        OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert e.value.kind == "server"
    assert "llama runner process has terminated" in str(e.value)


def test_token_repeat_abort_is_a_truncated_model_output(server):
    server["status"] = 500
    server["reply"] = {"error": "prediction aborted, token repeat limit reached"}
    r = OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert r.truncated is True
    assert r.text == ""


def test_connection_refused_raises_connection_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(EngineError) as e:
        OllamaEngine(f"http://127.0.0.1:{port}", timeout_s=5).chat(
            MSGS, model="m", options=OPTS, json_schema=None
        )
    assert e.value.kind == "connection"


def test_unload_posts_empty_chat_with_keep_alive_zero(server):
    server["reply"] = {"model": "m", "done": True, "done_reason": "unload"}
    assert OllamaEngine(server["url"]).unload("m") is None
    path, body = server["received"]
    assert path == "/api/chat"
    assert body == {"model": "m", "messages": [], "keep_alive": 0}


def test_unload_http_500_raises_server_error(server):
    server["status"] = 500
    with pytest.raises(EngineError) as e:
        OllamaEngine(server["url"]).unload("m")
    assert e.value.kind == "server"


def test_404_model_not_found_raises_model_missing(server):
    server["status"] = 404
    server["reply"] = {"error": "model 'm' not found"}
    with pytest.raises(EngineError) as e:
        OllamaEngine(server["url"]).chat(MSGS, model="m", options=OPTS, json_schema=None)
    assert e.value.kind == "model_missing"
