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

    @staticmethod
    def _response_part(msg: dict[str, Any]) -> dict[str, Any]:
        """Build a Gemini FunctionResponse and preserve required call metadata."""
        response: dict[str, Any] = {
            "name": msg.get("name", "tool"),
            "response": {"result": msg.get("content", "")},
        }
        call_id = msg.get("tool_call_id")
        if call_id:
            response["id"] = call_id
        return {"functionResponse": response}

    @staticmethod
    def _function_call_part(fc: dict[str, Any]) -> dict[str, Any]:
        try:
            args = json.loads(fc.get("args", "{}")) if isinstance(fc.get("args"), str) else fc.get("args", {})
        except json.JSONDecodeError:
            args = {}
        call = {
            "name": fc.get("name", ""),
            "args": args,
        }
        if fc.get("id"):
            call["id"] = fc["id"]
        part: dict[str, Any] = {"functionCall": call}
        signature = fc.get("thought_signature") or fc.get("thoughtSignature")
        if signature:
            part["thoughtSignature"] = signature
        return part

    @staticmethod
    def _message_parts(msg: dict[str, Any]) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        content = msg.get("content", "")
        signature = msg.get("thought_signature") or msg.get("thoughtSignature")
        reasoning = msg.get("reasoning_content")
        if reasoning:
            thought_part: dict[str, Any] = {"text": reasoning, "thought": True}
            if signature:
                thought_part["thoughtSignature"] = signature
            parts.append(thought_part)

        if isinstance(content, str) and content:
            text_part: dict[str, Any] = {"text": content}
            if signature:
                text_part["thoughtSignature"] = signature
            parts.append(text_part)
        elif isinstance(content, list):
            for cp in content:
                if not isinstance(cp, dict):
                    continue
                ctype = cp.get("type")
                if ctype in ("text", "input_text", "output_text") and cp.get("text"):
                    p: dict[str, Any] = {"text": cp["text"]}
                    sig = cp.get("thought_signature") or cp.get("thoughtSignature")
                    if sig:
                        p["thoughtSignature"] = sig
                    parts.append(p)
        return parts

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
                contents.append({"role": "user", "parts": [self._response_part(msg)]})
                continue

            parts = []
            if "function_call" in msg:
                parts.append(self._function_call_part(msg["function_call"]))
            parts.extend(self._message_parts(msg))
            if not parts:
                continue

            gemini_role = "model" if role == "assistant" else "user"
            if contents and contents[-1]["role"] == gemini_role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": gemini_role, "parts": parts})

        body: dict[str, Any] = {"contents": contents}
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_text)}]}

        level = str(
            (data.get("reasoning") or {}).get("effort")
            or config.default_reasoning_level
        ).lower()
        if level == "minimal":
            level = "low"
        if level not in {"low", "medium", "high"}:
            level = "medium"
        body["generationConfig"] = {
            "thinkingConfig": {"includeThoughts": True, "thinkingLevel": level}
        }

        tools = data.get("tools") or []
        declarations = [tool for tool in tools if tool.get("name")]
        if declarations:
            body["tools"] = [{"functionDeclarations": declarations}]

        url = f"{config.gemini_api_public}/v1beta/models/{model}:streamGenerateContent?alt=sse"
        try:
            with self.session.post(
                url,
                data=json_dumps(body),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                stream=True,
                timeout=(config.request_timeout_connect, config.request_timeout_read),
            ) as resp:
                if resp.status_code != 200:
                    raise ProviderError(
                        f"Gemini API returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )
                handler.send_response(200)
                handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
                handler.send_header("Connection", "keep-alive")
                handler.end_headers()
                stream_responses_loop(resp, handler, model, int(time.time()), data)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
