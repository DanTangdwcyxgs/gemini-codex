from __future__ import annotations

import json
import threading
import urllib.request

import codex_proxy.server as server_module
from codex_proxy.server import ProxyRequestHandler


def _start_server():
    server = server_module.ThreadingHTTPServer(("127.0.0.1", 0), ProxyRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_http_responses_route_deepseek_without_gemini_normalization(monkeypatch):
    seen = {}

    def deepseek(data, handler):
        seen["provider"] = "deepseek"
        seen["data"] = data
        handler._json(200, {"ok": True})

    monkeypatch.setattr(server_module._DEEPSEEK_PROVIDER, "handle_request", deepseek)
    server = _start_server()
    try:
        payload = {"model": "deepseek-v4-flash", "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]}
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/responses",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
            assert json.loads(response.read()) == {"ok": True}
        assert seen["provider"] == "deepseek"
        assert seen["data"] == {**payload, "model": "deepseek-v4-flash"}
    finally:
        server.shutdown()
        server.server_close()


def test_http_responses_normalize_gemini_input_before_provider(monkeypatch):
    seen = {}

    def gemini(data, handler):
        seen["provider"] = "gemini"
        seen["data"] = data
        handler._json(200, {"ok": True})

    monkeypatch.setattr(server_module._GEMINI_PROVIDER, "handle_request", gemini)
    server = _start_server()
    try:
        payload = {
            "model": "gemini-3.8-flash",
            "instructions": "Be concise",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/responses",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
            assert json.loads(response.read()) == {"ok": True}
        assert seen["provider"] == "gemini"
        assert seen["data"]["model"] == "gemini-3.8-flash"
        assert seen["data"]["messages"] == [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "hello"},
        ]
    finally:
        server.shutdown()
        server.server_close()
