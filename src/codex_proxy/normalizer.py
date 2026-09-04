from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text"):
                out.append(str(part.get("text", "")))
        return "".join(out)
    return ""


def normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for tool in tools or []:
        if tool.get("type") == "function":
            fn = tool.get("function", {})
            if fn.get("name"):
                result.append(fn)
    return result


def normalize_responses_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI Responses input items into a compact internal request."""
    messages: List[Dict[str, Any]] = []
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
                messages.append({"role": role, "content": content})
        elif typ in ("function_call", "custom_tool_call"):
            messages.append({
                "role": "assistant",
                "function_call": {
                    "name": item.get("name", ""),
                    "args": item.get("arguments", "{}"),
                    "id": item.get("call_id") or item.get("id"),
                },
            })
        elif typ in ("function_call_output", "custom_tool_call_output", "tool"):
            messages.append({
                "role": "tool",
                "tool_call_id": item.get("call_id") or item.get("id"),
                "content": _text_content(item.get("output", item.get("content", ""))),
            })
        elif typ in ("local_shell_call", "command_execution"):
            messages.append({"role": "assistant", "content": _text_content(item.get("command", ""))})

    result = dict(data)
    result["messages"] = messages
    result["tools"] = normalize_tools(data.get("tools") or [])
    result["model"] = data.get("model") or "gemini-3.8-flash"
    return result
