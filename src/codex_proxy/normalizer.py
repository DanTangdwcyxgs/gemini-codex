from __future__ import annotations

import json
from typing import Any


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
            and part.get("type") in ("text", "input_text", "output_text")
        )
    return ""


def normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for tool in tools or []:
        if tool.get("type") == "function":
            fn = tool.get("function", {})
            if fn.get("name"):
                result.append(fn)
    return result


def normalize_responses_request(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI Responses input items into Gemini-oriented messages."""
    messages: list[dict[str, Any]] = []
    function_names: dict[str, str] = {}
    instructions = data.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    for item in data.get("input") or []:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if not isinstance(item, dict):
            continue

        typ = item.get("type")
        if typ in (None, "message"):
            role = item.get("role", "user")
            content = _text_content(item.get("content", item.get("text", "")))
            if content:
                messages.append({"role": "assistant" if role == "assistant" else role, "content": content})
        elif typ in ("function_call", "custom_tool_call"):
            call_id = item.get("call_id") or item.get("id")
            name = item.get("name", "")
            if call_id and name:
                function_names[call_id] = name
            messages.append({
                "role": "assistant",
                "function_call": {
                    "name": name,
                    "args": item.get("arguments", "{}"),
                    "id": call_id,
                },
            })
        elif typ in ("function_call_output", "custom_tool_call_output", "tool"):
            call_id = item.get("call_id") or item.get("id")
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": item.get("name") or function_names.get(call_id, "tool"),
                "content": _text_content(item.get("output", item.get("content", ""))),
            })
        elif typ in ("local_shell_call", "command_execution"):
            command = item.get("command", "")
            if isinstance(command, list):
                command = " ".join(str(x) for x in command)
            messages.append({"role": "assistant", "content": str(command)})

    result = dict(data)
    result["messages"] = messages
    result["tools"] = normalize_tools(data.get("tools") or [])
    result["model"] = data.get("model") or "gemini-3.8-flash"
    return result
