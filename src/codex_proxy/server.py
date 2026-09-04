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
        if self.path in ("/health", "/"):
            payload = {"status": "ok", "models": config.models}
            self._json(200, payload)
            return
        if self.path == "/v1/models" or self.path == "/models":
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": model, "object": "model", "owned_by": "google"}
                        for model in config.models
                    ],
                },
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in (
            "/v1/responses",
            "/responses",
            "/v1/responses/compact",
            "/responses/compact",
        ):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not length:
                raise ValueError("empty request body")
            raw = self.rfile.read(length)
            data = json.loads(raw)
            normalized = normalize_responses_request(data)
            if self.path.endswith("/compact"):
                self._handle_compact(normalized)
            else:
                _PROVIDER.handle_request(normalized, self)
        except ProxyError as exc:
            self._json(502, {"error": {"message": str(exc), "type": "proxy_error"}})
        except Exception as exc:
            self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})

    def _handle_compact(self, data: dict) -> None:
        """Return a Responses-compatible compaction item using Gemini text output."""
        summary_request = dict(data)
        summary_request["instructions"] = (
            data.get("instructions")
            or "Summarize the conversation for a coding agent. Preserve decisions, constraints, "
            "unfinished work, tool results, file paths, and facts needed to continue the task."
        )
        # The provider's normal stream path is deliberately not reused: compaction must
        # produce one normal JSON response rather than SSE.
        api_key = _PROVIDER.auth.get_api_key()
        model = config.models[0]
        contents = []
        for message in data.get("messages", []):
            role = message.get("role", "user")
            if role == "system":
                continue
            text = message.get("content", "")
            if text:
                contents.append(
                    {"role": "model" if role == "assistant" else "user", "parts": [{"text": str(text)}]}
                )
        contents.append({"role": "user", "parts": [{"text": summary_request["instructions"]}]})

        body = {
            "contents": contents,
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}},
        }
        url = f"{config.gemini_api_public}/v1beta/models/{model}:generateContent"
        with _PROVIDER.session.post(
            url,
            data=json.dumps(body, ensure_ascii=False),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=(config.request_timeout_connect, config.request_timeout_read),
        ) as resp:
            if resp.status_code != 200:
                raise ProxyError(f"Gemini compaction returned HTTP {resp.status_code}: {resp.text[:500]}")
            payload = resp.json()

        texts: list[str] = []
        for candidate in payload.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                if isinstance(part, dict) and part.get("text") and not part.get("thought"):
                    texts.append(part["text"])
        result = {
            "object": "response",
            "status": "completed",
            "output": [{"type": "compaction", "encrypted_content": "".join(texts)}],
        }
        self._json(200, result)

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
