from __future__ import annotations

import base64
import json
from typing import Any


_COMPACTION_PREFIX = "gemini-codex-v1:"


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and part.get("type") in {
                "text",
                "input_text",
                "output_text",
                "reasoning_text",
                "summary_text",
            }:
                chunks.append(str(part.get("text", "")))
        return "".join(chunks)
    if isinstance(content, dict):
        return str(content.get("content") or content.get("text") or "")
    return ""


def encode_proxy_compaction(text: str) -> str:
    """Encode this proxy's compaction payload for opaque Responses transport."""
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return _COMPACTION_PREFIX + encoded


def decode_proxy_compaction(value: Any) -> str | None:
    """Decode only payloads emitted by this proxy."""
    if not isinstance(value, str) or not value.startswith(_COMPACTION_PREFIX):
        return None
    encoded = value[len(_COMPACTION_PREFIX) :]
    if not encoded:
        return ""
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _signature(item: dict[str, Any]) -> str | None:
    return item.get("thought_signature") or item.get("thoughtSignature")


def _tool_name(tool: dict[str, Any]) -> str | None:
    fn = tool.get("function") or tool
    if fn.get("name"):
        return str(fn["name"])
    return {
        "local_shell": "local_shell_command",
        "command_execution": "run_shell_command",
        "commandExecution": "run_shell_command",
        "shell": "shell_command",
        "shell_call": "shell_command",
        "local_shell_call": "local_shell_command",
        "file_change": "write_file",
        "fileChange": "write_file",
        "apply_patch": "apply_patch",
        "apply_patch_call": "apply_patch",
    }.get(str(tool.get("type") or ""))


def _builtin_parameters(tool: dict[str, Any], name: str) -> dict[str, Any]:
    fn = tool.get("function") or tool
    parameters = fn.get("parameters") or tool.get("parameters")
    if isinstance(parameters, dict) and parameters:
        return parameters
    if name == "local_shell_command":
        return {
            "type": "object",
            "properties": {
                "command": {"type": "array", "items": {"type": "string"}},
                "working_directory": {"type": "string"},
                "env": {"type": "object", "additionalProperties": {"type": "string"}},
                "timeout_ms": {"type": "integer"},
                "user": {"type": "string"},
            },
            "required": ["command"],
        }
    if name == "shell_command":
        return {
            "type": "object",
            "properties": {
                "commands": {"type": "array", "items": {"type": "string"}},
                "max_output_length": {"type": "integer"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["commands"],
        }
    if name == "write_file":
        return {
            "type": "object",
            "properties": {"file_path": {"type": "string"}, "changes": {"type": "array"}},
            "required": ["file_path"],
        }
    if name == "apply_patch":
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["create_file", "delete_file", "update_file"]},
                        "path": {"type": "string"},
                        "diff": {"type": "string"},
                    },
                    "required": ["type", "path"],
                }
            },
            "required": ["operation"],
        }
    return {"type": "object", "properties": {}}


def _mcp_declarations(item: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    server_label = str(item.get("server_label", "mcp"))
    declarations: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}
    for tool in item.get("tools") or []:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        name = f"mcp__{server_label}__{tool['name']}"
        declarations.append(
            {
                "name": name,
                "description": tool.get("description") or str(tool["name"]),
                "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
            }
        )
        metadata[name] = {
            "type": "mcp_call",
            "server_label": server_label,
            "original_name": str(tool["name"]),
        }
    return declarations, metadata


def normalize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tool in tools or []:
        name = _tool_name(tool)
        if not name:
            continue
        fn = tool.get("function") or tool
        if tool.get("type") in ("function", None):
            result.append(fn)
            continue
        result.append(
            {
                "name": name,
                "description": fn.get("description") or tool.get("description") or name,
                "parameters": _builtin_parameters(tool, name),
            }
        )
    return result


def tool_output_types(
    tools: list[dict[str, Any]], mcp_metadata: dict[str, dict[str, Any]] | None = None
) -> dict[str, str]:
    result: dict[str, str] = {}
    for tool in tools or []:
        name = _tool_name(tool)
        if not name:
            continue
        typ = str(tool.get("type", "function"))
        if typ in ("local_shell", "local_shell_call", "command_execution", "commandExecution"):
            result[name] = "local_shell_call"
        elif typ in ("shell", "shell_call"):
            result[name] = "shell_call"
        elif typ in ("apply_patch", "apply_patch_call"):
            result[name] = "apply_patch_call"
        elif typ in ("function", "None"):
            result[name] = "function_call"
        elif typ in ("file_change", "fileChange"):
            result[name] = "file_change"
        else:
            result[name] = "function_call"
    for name in mcp_metadata or {}:
        result[name] = "mcp_call"
    return result


def _tool_call(item: dict[str, Any]) -> tuple[str, str, Any, str | None, dict[str, Any] | None]:
    typ = str(item.get("type") or "")
    call_id = str(item.get("call_id") or item.get("id") or "")
    name = str(item.get("name") or "")
    args: Any = item.get("arguments") or item.get("input") or {}
    tool_metadata: dict[str, Any] | None = None

    if typ == "mcp_call":
        server_label = str(item.get("server_label", "mcp"))
        original_name = str(item.get("name", "tool"))
        name = f"mcp__{server_label}__{original_name}"
        tool_metadata = {
            "type": "mcp_call",
            "server_label": server_label,
            "original_name": original_name,
        }

    if not name:
        name = {
            "commandExecution": "run_shell_command",
            "local_shell_call": "local_shell_command",
            "shell_call": "shell_command",
            "fileChange": "write_file",
            "apply_patch_call": "apply_patch",
            "web_search_call": "web_search",
        }.get(typ, "tool")

    if not args and typ == "commandExecution":
        args = {"command": item.get("command", ""), "cwd": item.get("cwd", ".")}
    elif not args and typ in ("local_shell_call", "shell_call"):
        action = item.get("action") or {}
        if not isinstance(action, dict):
            action = {}
        if typ == "shell_call":
            args = {
                "commands": action.get("commands", []),
                "max_output_length": action.get("max_output_length"),
                "timeout_ms": action.get("timeout_ms"),
            }
        else:
            exec_data = action.get("exec")
            if not isinstance(exec_data, dict):
                exec_data = action
            args = {
                "command": exec_data.get("command", []),
                "working_directory": exec_data.get("working_directory") or exec_data.get("cwd"),
                "env": exec_data.get("env", {}),
                "timeout_ms": exec_data.get("timeout_ms"),
                "user": exec_data.get("user"),
            }
        args = {key: value for key, value in args.items() if value is not None}
    elif not args and typ in ("fileChange", "apply_patch_call"):
        if typ == "apply_patch_call":
            args = item.get("operation") or {}
        else:
            changes = item.get("changes") or []
            args = {
                "file_path": item.get("file_path") or (changes[0].get("path", "") if changes else ""),
                "changes": changes,
            }
    elif not args and typ == "web_search_call":
        args = item.get("action") or {}

    return call_id, name, args, _signature(item), tool_metadata


def normalize_responses_request(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI Responses history into Gemini-compatible messages and tools."""
    messages: list[dict[str, Any]] = []
    function_names: dict[str, str] = {}
    function_signatures: dict[str, str] = {}
    mcp_metadata: dict[str, dict[str, Any]] = {}
    dropped_types: list[str] = []
    original_tools = data.get("tools") or []

    instructions = data.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": _text_content(instructions)})

    mcp_declarations: list[dict[str, Any]] = []
    for item in data.get("input") or []:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if not isinstance(item, dict):
            continue

        typ = str(item.get("type") or "")
        if typ == "compaction_trigger":
            continue

        if typ == "compaction":
            summary = decode_proxy_compaction(item.get("encrypted_content"))
            if summary:
                messages.append({"role": "user", "content": "[prior compaction summary]\n" + summary})
            elif isinstance(item.get("content"), (str, list, dict)):
                text = _text_content(item.get("content"))
                if text:
                    messages.append({"role": "user", "content": "[prior compaction summary]\n" + text})
            continue

        if typ == "mcp_list_tools":
            declarations, metadata = _mcp_declarations(item)
            mcp_declarations.extend(declarations)
            mcp_metadata.update(metadata)
            continue

        if typ == "reasoning":
            summary = _text_content(item.get("summary"))
            content = _text_content(item.get("content"))
            reasoning = "\n".join(part for part in (summary, content) if part)
            sig = _signature(item)
            if reasoning or sig:
                msg: dict[str, Any] = {"role": "assistant", "content": "", "reasoning_content": reasoning}
                if sig:
                    msg["thought_signature"] = sig
                messages.append(msg)
            continue

        if typ in ("message", "agentMessage", ""):
            role = str(item.get("role") or "user")
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
                msg = {"role": "assistant", "content": text}
                if reasoning:
                    msg["reasoning_content"] = reasoning
                if sig:
                    msg["thought_signature"] = sig
                if text or reasoning or sig:
                    messages.append(msg)
            elif text:
                messages.append({"role": role, "content": text})
            continue

        if typ in {
            "function_call",
            "custom_tool_call",
            "commandExecution",
            "local_shell_call",
            "shell_call",
            "fileChange",
            "apply_patch_call",
            "web_search_call",
            "mcp_call",
        }:
            call_id, name, args, sig, metadata = _tool_call(item)
            if metadata is not None:
                mcp_metadata[name] = metadata
            if call_id:
                function_names[call_id] = name
                if sig:
                    function_signatures[call_id] = sig
            fc: dict[str, Any] = {"name": name, "args": args, "id": call_id}
            if sig:
                fc["thought_signature"] = sig
            messages.append({"role": "assistant", "function_call": fc})

            if typ == "mcp_call" and (item.get("output") is not None or item.get("error") is not None):
                result_value: Any = item.get("output")
                if result_value is None:
                    result_value = {"error": item.get("error")}
                if isinstance(result_value, (dict, list)):
                    result_value = json.dumps(result_value, ensure_ascii=False)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "thought_signature": sig,
                        "content": str(result_value or ""),
                    }
                )
            continue

        if typ in {
            "function_call_output",
            "custom_tool_call_output",
            "commandExecutionOutput",
            "local_shell_call_output",
            "shell_call_output",
            "fileChangeOutput",
            "apply_patch_call_output",
            "tool",
        }:
            call_id = str(item.get("call_id") or item.get("id") or "")
            name = str(item.get("name") or function_names.get(call_id, "tool"))
            output = item.get("output", item.get("content", item.get("stdout", "")))
            if typ in ("local_shell_call_output", "shell_call_output") and not output:
                output = item.get("stderr", "")
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
            continue

        dropped_types.append(typ)

    gemini_tools = normalize_tools(original_tools)
    gemini_tools.extend(mcp_declarations)

    result = dict(data)
    result["messages"] = messages
    result["tools"] = gemini_tools
    result["tool_output_types"] = tool_output_types(original_tools, mcp_metadata)
    result["tool_output_metadata"] = mcp_metadata
    result["model"] = data.get("model") or "gemini-3.8-flash"
    result["dropped_input_types"] = dropped_types
    return result
