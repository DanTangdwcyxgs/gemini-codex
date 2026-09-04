from __future__ import annotations

import json
import time
from typing import Any

from .gemini_response import iter_parts, unwrap_gemini_chunk, usage_to_responses_usage


def stream_responses_loop(resp: Any, handler: Any, model: str, created_ts: int, request_metadata: dict[str, Any] | None = None) -> None:
    """Translate Gemini SSE chunks into OpenAI Responses SSE events."""
    metadata = request_metadata or {}
    response_id = f"resp_{created_ts}"
    seq = 0
    output: list[dict[str, Any]] = []
    message_item = None
    reasoning_item = None
    usage = None

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

    emit("response.created", {"response": {"id": response_id, "object": "response", "model": model, "status": "in_progress", "output": []}})

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
                if "functionCall" in part:
                    fc = part["functionCall"]
                    call_id = fc.get("id") or f"call_{int(time.time() * 1000)}"
                    item = {
                        "id": call_id,
                        "type": "function_call",
                        "status": "completed",
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False),
                        "call_id": call_id,
                    }
                    idx = len(output)
                    emit("response.output_item.added", {"response_id": response_id, "output_index": idx, "item": item})
                    emit("response.output_item.done", {"response_id": response_id, "output_index": idx, "item": item})
                    output.append(item)
                    continue

                text = part.get("text")
                thought = part.get("thought")
                if thought is True:
                    if text:
                        if reasoning_item is None:
                            reasoning_item = {"id": f"rs_{created_ts}", "type": "reasoning", "status": "in_progress", "summary": [], "content": [{"type": "reasoning_text", "text": ""}]}
                            emit("response.output_item.added", {"response_id": response_id, "output_index": len(output), "item": reasoning_item})
                        reasoning_item["content"][0]["text"] += text
                        emit("response.reasoning_text.delta", {"response_id": response_id, "item_id": reasoning_item["id"], "output_index": len(output), "content_index": 0, "delta": text})
                    continue
                if isinstance(thought, str):
                    if reasoning_item is None:
                        reasoning_item = {"id": f"rs_{created_ts}", "type": "reasoning", "status": "in_progress", "summary": [], "content": [{"type": "reasoning_text", "text": ""}]}
                        emit("response.output_item.added", {"response_id": response_id, "output_index": len(output), "item": reasoning_item})
                    reasoning_item["content"][0]["text"] += thought
                    emit("response.reasoning_text.delta", {"response_id": response_id, "item_id": reasoning_item["id"], "output_index": len(output), "content_index": 0, "delta": thought})
                elif text:
                    if message_item is None:
                        message_item = {"id": f"msg_{created_ts}", "type": "message", "role": "assistant", "status": "in_progress", "content": [{"type": "output_text", "text": ""}]}
                        emit("response.output_item.added", {"response_id": response_id, "output_index": len(output), "item": message_item})
                    message_item["content"][0]["text"] += text
                    emit("response.output_text.delta", {"response_id": response_id, "item_id": message_item["id"], "output_index": len(output), "content_index": 0, "delta": text})
        except Exception:
            continue

    if reasoning_item is not None:
        reasoning_item["status"] = "completed"
        emit("response.output_item.done", {"response_id": response_id, "output_index": len(output), "item": reasoning_item})
        output.append(reasoning_item)
    if message_item is not None:
        message_item["status"] = "completed"
        emit("response.output_item.done", {"response_id": response_id, "output_index": len(output), "item": message_item})
        output.append(message_item)
    if usage:
        emit("token_count", {"info": {"total_token_usage": {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"], "reasoning_output_tokens": usage["output_tokens_details"]["reasoning_tokens"], "total_tokens": usage["total_tokens"]}}})

    emit("response.completed", {"response": {"id": response_id, "object": "response", "status": "completed", "model": model, "created_at": created_ts, "output": output, "usage": usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}})
