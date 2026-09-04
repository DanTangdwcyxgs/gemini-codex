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


def test_http_responses_routes_and_normalizes_gemini(monkeypatch):
    gemini = FakeProvider()
    deepseek = FakeProvider()
    monkeypatch.setattr(server_module, "_GEMINI_PROVIDER", gemini)
    monkeypatch.setattr(server_module, "_DEEPSEEK_PROVIDER", deepseek)

    httpd = server_module.ThreadingHTTPServer(("localhost", 0), ProxyRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("localhost", httpd.server_port, timeout=5)
        payload = {
            "model": "gemini-3.8-flash",
            "instructions": "be concise",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        }
        conn.request("POST", "/v1/responses", body=json.dumps(payload), headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read())
        conn.close()

        assert response.status == 200
        assert data["model"] == "gemini-3.8-flash"
        assert gemini.requests[0]["messages"][0] == {"role": "system", "content": "be concise"}
        assert gemini.requests[0]["messages"][1] == {"role": "user", "content": "hello"}
        assert deepseek.requests == []
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()
