from __future__ import annotations

import json
import time
from typing import Any

from .gemini_response import iter_parts, unwrap_gemini_chunk, usage_to_responses_usage


_SHELL_NAMES = {
    "shell",
    "shell_command",
    "container.exec",
    "local_shell",
    "local_shell_command",
    "run_shell_command",
}


def stream_responses_loop(
    resp: Any,
    handler: Any,
    model: str,
    created_ts: int,
    request_metadata: dict[str, Any] | None = None,
) -> None:
    """Translate Gemini GenerateContent SSE chunks into Responses SSE events."""
    response_id = f"resp_{created_ts}"
    seq = 0
    output: list[dict[str, Any]] = []
    next_output_index = 0
    message_item: dict[str, Any] | None = None
    message_index: int | None = None
    reasoning_item: dict[str, Any] | None = None
    reasoning_index: int | None = None
    usage: dict[str, Any] | None = None
    metadata = request_metadata or {}
    tool_output_types = metadata.get("tool_output_types") or {}

    def emit(event_type: str, payload: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        event = {
            "id": f"evt_{int(time.time() * 1000)}_{seq}",
            "object": "response.event",
            "type": event_type,
            "created_at": int(time.time()),
            "sequence_number": seq,
            **payload,
        }
        handler.wfile.write(
            f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
        )
        handler.wfile.flush()

    def ensure_reasoning() -> tuple[dict[str, Any], int]:
        nonlocal reasoning_item, reasoning_index, next_output_index
        if reasoning_item is None:
            reasoning_index = next_output_index
            next_output_index += 1
            reasoning_item = {
                "id": f"rs_{created_ts}",
                "type": "reasoning",
                "status": "in_progress",
                "summary": [],
                "content": [{"type": "reasoning_text", "text": ""}],
            }
            emit(
                "response.output_item.added",
                {"response_id": response_id, "output_index": reasoning_index, "item": reasoning_item},
            )
        return reasoning_item, reasoning_index  # type: ignore[arg-type]

    def ensure_message() -> tuple[dict[str, Any], int]:
        nonlocal message_item, message_index, next_output_index
        if message_item is None:
            message_index = next_output_index
            next_output_index += 1
            message_item = {
                "id": f"msg_{created_ts}",
                "type": "message",
                "role": "assistant",
                "status": "in_progress",
                "content": [{"type": "output_text", "text": ""}],
            }
            emit(
                "response.output_item.added",
                {"response_id": response_id, "output_index": message_index, "item": message_item},
            )
        return message_item, message_index  # type: ignore[arg-type]

    emit(
        "response.created",
        {
            "response": {
                "id": response_id,
                "object": "response",
                "model": model,
                "status": "in_progress",
                "output": [],
            }
        },
    )

    for line in resp.iter_lines():
        if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
            continue
        try:
            data = json.loads(line[6:])
            chunk = unwrap_gemini_chunk(data)
            mapped_usage = usage_to_responses_usage(chunk.usage)
            if mapped_usage:
                usage = mapped_usage

            for part in iter_parts(chunk):
                function_call = part.get("functionCall")
                if isinstance(function_call, dict):
                    name = str(function_call.get("name", ""))
                    call_id = function_call.get("id") or f"call_{created_ts}_{next_output_index}"
                    raw_args = function_call.get("args", {})
                    item_type = tool_output_types.get(name)
                    if not item_type:
                        item_type = "local_shell_call" if name in _SHELL_NAMES else "function_call"

                    item: dict[str, Any] = {
                        "id": call_id,
                        "type": item_type,
                        "status": "completed",
                        "name": name,
                        "arguments": json.dumps(raw_args, ensure_ascii=False),
                        "call_id": call_id,
                    }
                    signature = part.get("thoughtSignature") or part.get("thought_signature")
                    if signature:
                        item["thought_signature"] = signature

                    if item_type == "local_shell_call":
                        args = raw_args if isinstance(raw_args, dict) else {"command": raw_args}
                        command = args.get("command", [])
                        if isinstance(command, str):
                            command = [command]
                        exec_action: dict[str, Any] = {
                            "type": "exec",
                            "command": command,
                            "env": args.get("env", {}) or {},
                        }
                        working_directory = args.get("working_directory") or args.get("cwd")
                        if working_directory:
                            exec_action["working_directory"] = working_directory
                        for key in ("timeout_ms", "user"):
                            if args.get(key) is not None:
                                exec_action[key] = args[key]
                        item["action"] = exec_action

                    idx = next_output_index
                    next_output_index += 1
                    emit(
                        "response.output_item.added",
                        {"response_id": response_id, "output_index": idx, "item": item},
                    )
                    emit(
                        "response.output_item.done",
                        {"response_id": response_id, "output_index": idx, "item": item},
                    )
                    output.append(item)
                    continue

                text = part.get("text")
                thought = part.get("thought")
                signature = part.get("thoughtSignature") or part.get("thought_signature")

                if thought is True or isinstance(thought, str):
                    thought_text = text if thought is True else thought
                    if thought_text:
                        item, idx = ensure_reasoning()
                        item["content"][0]["text"] += thought_text
                        if signature:
                            item["thought_signature"] = signature
                        emit(
                            "response.reasoning_text.delta",
                            {
                                "response_id": response_id,
                                "item_id": item["id"],
                                "output_index": idx,
                                "content_index": 0,
                                "delta": thought_text,
                            },
                        )
                    continue

                if text:
                    item, idx = ensure_message()
                    item["content"][0]["text"] += text
                    if signature:
                        item["thought_signature"] = signature
                    emit(
                        "response.output_text.delta",
                        {
                            "response_id": response_id,
                            "item_id": item["id"],
                            "output_index": idx,
                            "content_index": 0,
                            "delta": text,
                        },
                    )
        except Exception:
            continue

    if reasoning_item is not None and reasoning_index is not None:
        reasoning_item["status"] = "completed"
        emit(
            "response.output_item.done",
            {"response_id": response_id, "output_index": reasoning_index, "item": reasoning_item},
        )
        output.append(reasoning_item)

    if message_item is not None and message_index is not None:
        message_item["status"] = "completed"
        emit(
            "response.output_item.done",
            {"response_id": response_id, "output_index": message_index, "item": message_item},
        )
        output.append(message_item)

    if usage:
        total_usage = {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "reasoning_output_tokens": usage["output_tokens_details"]["reasoning_tokens"],
            "total_tokens": usage["total_tokens"],
        }
        emit("token_count", {"info": {"total_token_usage": total_usage}})

    emit(
        "response.completed",
        {
            "response": {
                "id": response_id,
                "object": "response",
                "status": "completed",
                "model": model,
                "created_at": created_ts,
                "output": output,
                "usage": usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "store": metadata.get("store", False),
                "metadata": metadata.get("metadata", {}),
            }
        },
    )
