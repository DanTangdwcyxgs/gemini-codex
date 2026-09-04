import http.client
import json
import threading

import codex_proxy.server as server_module
from codex_proxy.server import ProxyRequestHandler


class FakeProvider:
    def __init__(self):
        self.requests = []

    def handle_request(self, data, handler):
        self.requests.append(data)
        body = json.dumps({"ok": True, "model": data["model"]}).encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


def _request(method, path, payload=None):
    httpd = server_module.ThreadingHTTPServer(("localhost", 0), ProxyRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("localhost", httpd.server_port, timeout=5)
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        data = json.loads(raw) if raw else None
        return response.status, data
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()


def test_http_responses_routes_and_normalizes_gemini(monkeypatch):
    gemini = FakeProvider()
    deepseek = FakeProvider()
    monkeypatch.setattr(server_module, "_GEMINI_PROVIDER", gemini)
    monkeypatch.setattr(server_module, "_DEEPSEEK_PROVIDER", deepseek)

    status, data = _request(
        "POST",
        "/v1/responses",
        {
            "model": "gemini-3.8-flash",
            "instructions": "be concise",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        },
    )

    assert status == 200
    assert data["model"] == "gemini-3.8-flash"
    assert gemini.requests[0]["messages"][0] == {"role": "system", "content": "be concise"}
    assert gemini.requests[0]["messages"][1] == {"role": "user", "content": "hello"}
    assert deepseek.requests == []


def test_http_responses_keeps_deepseek_body_unmodified(monkeypatch):
    gemini = FakeProvider()
    deepseek = FakeProvider()
    monkeypatch.setattr(server_module, "_GEMINI_PROVIDER", gemini)
    monkeypatch.setattr(server_module, "_DEEPSEEK_PROVIDER", deepseek)

    payload = {
        "model": "deepseek-v4-flash",
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}],
        "stream": True,
        "store": False,
    }
    status, data = _request("POST", "/v1/responses", payload)

    assert status == 200
    assert data["model"] == "deepseek-v4-flash"
    forwarded = deepseek.requests[0]
    assert forwarded["model"] == payload["model"]
    assert forwarded["input"] == payload["input"]
    assert forwarded["tools"] == payload["tools"]
    assert forwarded["stream"] is True
    assert forwarded["store"] is False
    assert "messages" not in forwarded
    assert "tool_output_types" not in forwarded
    assert gemini.requests == []


def test_health_and_models_endpoints_expose_configured_models():
    status, health = _request("GET", "/health")
    assert status == 200
    assert health["status"] == "ok"
    assert "gemini-3.8-flash" in health["models"]
    assert "deepseek-v4-flash" in health["models"]

    status, models = _request("GET", "/v1/models")
    assert status == 200
    ids = [item["id"] for item in models["data"]]
    assert "gemini-3.8-flash" in ids
    assert "deepseek-v4-flash" in ids


def test_unsupported_model_returns_proxy_error():
    status, body = _request(
        "POST",
        "/v1/responses",
        {"model": "not-a-supported-model", "input": [{"role": "user", "content": "hello"}]},
    )
    assert status == 502
    assert body["error"]["type"] == "proxy_error"
    assert "Unsupported model provider" in body["error"]["message"]


def test_empty_request_returns_invalid_request():
    status, body = _request("POST", "/v1/responses")
    assert status == 400
    assert body["error"]["type"] == "invalid_request_error"
