from __future__ import annotations

import json
import time
from typing import Any

from ..auth import GeminiAuth
from ..config import config
from ..exceptions import ProviderError
from ..utils import create_session, json_dumps
from .gemini_stream import stream_responses_loop


class GeminiProvider:
    def __init__(self) -> None:
        self.auth = GeminiAuth()
        self.session = create_session()

    def handle_request(self, data: dict[str, Any], handler: Any) -> None:
        api_key = self.auth.get_api_key()
        model = data.get("model") or config.models[0]
        contents: list[dict[str, Any]] = []
        system_text: list[str] = []

        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            if role == "system":
                if msg.get("content"):
                    system_text.append(str(msg["content"]))
                continue
            if role == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": {"name": msg.get("name", "tool"), "response": {"result": msg.get("content", "")}, "id": msg.get("tool_call_id")}}}],
                })
            elif "function_call" in msg:
                fc = msg["function_call"]
                try:
                    args = json.loads(fc.get("args", "{}")) if isinstance(fc.get("args"), str) else fc.get("args", {})
                except json.JSONDecodeError:
                    args = {}
                contents.append({"role": "model", "parts": [{"functionCall": {"name": fc.get("name", ""), "args": args, "id": fc.get("id")}}]})
            else:
                contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": str(msg.get("content", ""))}]})

        body: dict[str, Any] = {"contents": contents}
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_text)}]}

        # Gemini 3.8 Flash uses thinking_level. Deprecated sampling knobs are omitted.
        level = str((data.get("reasoning") or {}).get("effort") or config.default_reasoning_level).lower()
        if level == "minimal":
            level = "low"
        body["generationConfig"] = {"thinkingConfig": {"includeThoughts": True, "thinkingLevel": level}}

        tools = data.get("tools") or []
        if tools:
            declarations = []
            for tool in tools:
                if tool.get("name"):
                    declarations.append(tool)
            if declarations:
                body["tools"] = [{"functionDeclarations": declarations}]

        url = f"{config.gemini_api_public}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
        try:
            with self.session.post(url, data=json_dumps(body), headers={"Content-Type": "application/json"}, stream=True, timeout=(config.request_timeout_connect, config.request_timeout_read)) as resp:
                if resp.status_code != 200:
                    raise ProviderError(f"Gemini API returned HTTP {resp.status_code}: {resp.text[:500]}")
                handler.send_response(200)
                handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
                handler.send_header("Connection", "keep-alive")
                handler.end_headers()
                stream_responses_loop(resp, handler, model, int(time.time()), data)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
