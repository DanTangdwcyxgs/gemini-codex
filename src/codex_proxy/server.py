from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import config
from .exceptions import ProxyError
from .normalizer import normalize_responses_request
from .providers.gemini import GeminiProvider


_PROVIDER = GeminiProvider()


class ProxyRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health" or self.path == "/":
            payload = {"status": "ok", "models": config.models}
            self._json(200, payload)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in ("/v1/responses", "/responses"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not length:
                raise ValueError("empty request body")
            raw = self.rfile.read(length)
            data = json.loads(raw)
            normalized = normalize_responses_request(data)
            _PROVIDER.handle_request(normalized, self)
        except ProxyError as exc:
            self._json(502, {"error": {"message": str(exc), "type": "proxy_error"}})
        except Exception as exc:
            self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def run_server() -> None:
    server = ThreadingHTTPServer((config.host, config.port), ProxyRequestHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
