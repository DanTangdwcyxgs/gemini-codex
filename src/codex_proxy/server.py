from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import config
from .exceptions import ProxyError
from .normalizer import encode_proxy_compaction, normalize_responses_request
from .providers.deepseek import DeepSeekProvider
from .providers.gemini import GeminiProvider


_GEMINI_PROVIDER = GeminiProvider()
_DEEPSEEK_PROVIDER = DeepSeekProvider()


def provider_key_for_model(model: str) -> str:
    for prefix, provider_key in config.model_prefixes.items():
        if model.startswith(prefix):
            if provider_key in {"deepseek", "gemini"}:
                return provider_key
    raise ProxyError(f"Unsupported model provider for '{model}'. Use a deepseek-* or gemini-* model.")


def provider_for_model(model: str):
    provider_key = provider_key_for_model(model)
    return _DEEPSEEK_PROVIDER if provider_key == "deepseek" else _GEMINI_PROVIDER


def has_compaction_trigger(data: dict[str, Any]) -> bool:
    return any(
        isinstance(item, dict) and item.get("type") == "compaction_trigger"
        for item in data.get("input") or []
    )


def _compaction_text(message: dict[str, Any]) -> str:
    """Serialize non-text model history so compaction does not erase tool context."""
    pieces: list[str] = []
    if message.get("content"):
        pieces.append(str(message["content"]))
    if message.get("reasoning_content"):
        pieces.append(f"[reasoning]\n{message['reasoning_content']}")
    if message.get("function_call"):
        pieces.append("[function_call]\n" + json.dumps(message["function_call"], ensure_ascii=False))
    if message.get("tool_calls"):
        pieces.append("[tool_calls]\n" + json.dumps(message["tool_calls"], ensure_ascii=False))
    if message.get("tool_call_id"):
        pieces.append(f"[tool_result id={message['tool_call_id']}]\n{message.get('content', '')}")
    return "\n".join(pieces)


class ProxyRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/health", "/"):
            self._json(200, {"status": "ok", "models": config.models})
            return
        if self.path in ("/v1/models", "/models"):
            providers = {"deepseek": "deepseek", "gemini": "google"}
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": model,
                            "object": "model",
                            "owned_by": providers.get(model.split("-", 1)[0], "proxy"),
                        }
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
            data = json.loads(self.rfile.read(length))
            model = data.get("model") or config.models[0]

            if self.path.endswith("/compact"):
                normalized = normalize_responses_request(data)
                self._handle_compact(normalized)
                return

            if has_compaction_trigger(data):
                normalized = normalize_responses_request(data)
                self._handle_compact_v2(normalized, model)
                return

            provider_key = provider_key_for_model(model)
            provider = _DEEPSEEK_PROVIDER if provider_key == "deepseek" else _GEMINI_PROVIDER
            if provider_key == "deepseek":
                provider.handle_request(dict(data, model=model), self)
            else:
                normalized = normalize_responses_request(data)
                normalized["model"] = model
                provider.handle_request(normalized, self)
        except ProxyError as exc:
            self._json(502, {"error": {"message": str(exc), "type": "proxy_error"}})
        except Exception as exc:
            self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})

    def _compact_with_gemini(self, data: dict[str, Any]) -> str:
        api_key = _GEMINI_PROVIDER.auth.get_api_key()
        model = config.compaction_model
        instruction = (
            data.get("instructions")
            or "Summarize the conversation for a coding agent. Preserve decisions, constraints, "
            "unfinished work, tool results, file paths, and facts needed to continue the task."
        )

        contents: list[dict[str, Any]] = []
        for message in data.get("messages", []):
            role = message.get("role", "user")
            if role == "system":
                continue
            text = _compaction_text(message)
            if not text:
                continue
            gemini_role = "model" if role == "assistant" else "user"
            if contents and contents[-1]["role"] == gemini_role:
                contents[-1]["parts"][0]["text"] += "\n\n" + text
            else:
                contents.append({"role": gemini_role, "parts": [{"text": text}]})

        if not contents or contents[-1]["role"] == "model":
            contents.append({"role": "user", "parts": [{"text": instruction}]})
        else:
            contents[-1]["parts"][0]["text"] += "\n\n" + instruction

        body = {
            "contents": contents,
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}},
        }
        url = f"{config.gemini_api_public}/v1beta/models/{model}:generateContent"
        with _GEMINI_PROVIDER.session.post(
            url,
            data=json.dumps(body, ensure_ascii=False),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=(config.request_timeout_connect, config.request_timeout_read),
        ) as resp:
            if resp.status_code != 200:
                raise ProxyError(
                    f"Gemini compaction returned HTTP {resp.status_code}: {resp.text[:500]}"
                )
            payload = resp.json()

        texts: list[str] = []
        for candidate in payload.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                if isinstance(part, dict) and part.get("text") and not part.get("thought"):
                    texts.append(part["text"])
        return "".join(texts)

    def _handle_compact(self, data: dict[str, Any]) -> None:
        summary = self._compact_with_gemini(data)
        self._json(
            200,
            {
                "object": "response",
                "status": "completed",
                "output": [{"type": "compaction", "encrypted_content": encode_proxy_compaction(summary)}],
            },
        )

    def _handle_compact_v2(self, data: dict[str, Any], requested_model: str) -> None:
        summary = self._compact_with_gemini(data)
        encoded = encode_proxy_compaction(summary)
        created_ts = int(time.time())
        response_id = f"resp_compact_{created_ts}"
        item = {
            "id": f"cmp_{created_ts}",
            "type": "compaction",
            "status": "completed",
            "encrypted_content": encoded,
        }

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def emit(event_type: str, payload: dict[str, Any]) -> None:
            event = {
                "id": f"evt_{created_ts}_{event_type}",
                "object": "response.event",
                "type": event_type,
                "created_at": created_ts,
                **payload,
            }
            self.wfile.write(
                f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
            )
            self.wfile.flush()

        emit(
            "response.created",
            {
                "response": {
                    "id": response_id,
                    "object": "response",
                    "model": requested_model,
                    "status": "in_progress",
                    "output": [],
                }
            },
        )
        emit(
            "response.output_item.added",
            {"response_id": response_id, "output_index": 0, "item": item},
        )
        emit(
            "response.output_item.done",
            {"response_id": response_id, "output_index": 0, "item": item},
        )
        emit(
            "response.completed",
            {
                "response": {
                    "id": response_id,
                    "object": "response",
                    "status": "completed",
                    "model": requested_model,
                    "created_at": created_ts,
                    "output": [item],
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                }
            },
        )

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
