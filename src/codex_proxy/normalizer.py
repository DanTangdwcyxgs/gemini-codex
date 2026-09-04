from __future__ import annotations

import json
from typing import Any


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and part.get("type") in (
                "text",
                "input_text",
                "output_text",
                "reasoning_text",
            ):
                chunks.append(str(part.get("text", "")))
        return "".join(chunks)
    if isinstance(content, dict):
        return str(content.get("content") or content.get("text") or "")
    return ""


def _signature(item: dict[str, Any]) -> str | None:
    return item.get("thought_signature") or item.get("thoughtSignature")


def _tool_call(item: dict[str, Any]) -> tuple[str, str, Any, str | None]:
    typ = item.get("type")
    call_id = item.get("call_id") or item.get("id") or ""
    name = item.get("name") or ""
    args: Any = item.get("arguments") or item.get("input") or {}

    if not name:
        name = {
            "commandExecution": "run_shell_command",
            "local_shell_call": "local_shell_command",
            "fileChange": "write_file",
            "web_search_call": "web_search",
        }.get(typ, "tool")

    if not args and typ == "commandExecution":
        args = {
            "command": item.get("command", ""),
            "cwd": item.get("cwd", "."),
        }
    elif not args and typ == "local_shell_call":
        action = item.get("action") or {}
        exec_data = action.get("exec") or action.get("execute") or action
        args = {
            "command": exec_data.get("command", []),
            "working_directory": exec_data.get("working_directory")
            or exec_data.get("cwd"),
        }
    elif not args and typ == "fileChange":
        changes = item.get("changes") or []
        args = {
            "file_path": changes[0].get("path", "") if changes else "",
            "changes": changes,
        }
    elif not args and typ == "web_search_call":
        args = item.get("action") or {}

    return call_id, name, args, _signature(item)


def normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tool in tools or []:
        if tool.get("type") != "function":
            continue
        fn = tool.get("function") or tool
        if fn.get("name"):
            result.append(fn)
    return result


def normalize_responses_request(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI Responses input items into Gemini-oriented messages."""
    messages: list[dict[str, Any]] = []
    function_names: dict[str, str] = {}
    function_signatures: dict[str, str] = {}

    instructions = data.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": _text_content(instructions)})

    for item in data.get("input") or []:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if not isinstance(item, dict):
            continue

        typ = item.get("type")

        if typ in (None, "message", "agentMessage"):
            role = item.get("role", "user")
            if role == "developer":
                role = "system"
            content = item.get("content", item.get("text", ""))
            text = _text_content(content)
            reasoning = ""
            if isinstance(content, list):
                reasoning = "".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "reasoning_text"
                )
            reasoning += str(item.get("reasoning_content") or "")
            sig = _signature(item)

            if role in ("assistant", "model"):
                msg: dict[str, Any] = {"role": "assistant", "content": text}
                if reasoning:
                    msg["reasoning_content"] = reasoning
                if sig:
                    msg["thought_signature"] = sig
                if text or reasoning or sig:
                    messages.append(msg)
            elif text:
                messages.append({"role": role, "content": text})
            continue

        if typ in (
            "function_call",
            "custom_tool_call",
            "commandExecution",
            "local_shell_call",
            "fileChange",
            "web_search_call",
        ):
            call_id, name, args, sig = _tool_call(item)
            if call_id:
                function_names[call_id] = name
                if sig:
                    function_signatures[call_id] = sig
            fc = {
                "name": name,
                "args": args,
                "id": call_id,
            }
            if sig:
                fc["thought_signature"] = sig
            messages.append({"role": "assistant", "function_call": fc})
            continue

        if typ in (
            "function_call_output",
            "custom_tool_call_output",
            "commandExecutionOutput",
            "fileChangeOutput",
            "tool",
        ):
            call_id = item.get("call_id") or item.get("id") or ""
            name = item.get("name") or function_names.get(call_id, "tool")
            output = item.get("output", item.get("content", item.get("stdout", "")))
            if isinstance(output, (dict, list)):
                output = json.dumps(output, ensure_ascii=False)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "thought_signature": function_signatures.get(call_id),
                    "content": str(output or ""),
                }
            )

    result = dict(data)
    result["messages"] = messages
    result["tools"] = normalize_tools(data.get("tools") or [])
    result["model"] = data.get("model") or "gemini-3.8-flash"
    return result
