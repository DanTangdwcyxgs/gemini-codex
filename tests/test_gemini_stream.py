import json

from codex_proxy.providers.gemini_stream import stream_responses_loop


class DummyWFile:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data

    def flush(self):
        pass


class DummyHandler:
    def __init__(self):
        self.wfile = DummyWFile()


def _events(handler):
    chunks = handler.wfile.data.decode("utf-8").strip().split("\n\n")
    result = []
    for chunk in chunks:
        lines = chunk.splitlines()
        if len(lines) >= 2:
            result.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return result


def _response(raw):
    class Resp:
        headers = {}

        def iter_lines(self):
            return raw

    return Resp()


def test_stream_preserves_function_signature_and_unique_output_indices():
    signature = "signed-thought"
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"read_file","args":{"path":"a.txt"},"id":"call_1"},"thoughtSignature":"' + signature.encode() + b'"}]}}]}',
        b'data: {"candidates":[{"content":{"parts":[{"thought":true,"text":"thinking"}]}}]}',
        b'data: {"candidates":[{"content":{"parts":[{"text":"done"}]}}],"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":4,"thoughtsTokenCount":6,"totalTokenCount":20}}',
        b'data: [DONE]',
    ]

    handler = DummyHandler()
    stream_responses_loop(_response(raw), handler, "gemini-3.8-flash", 123)
    events = _events(handler)

    done_items = [payload["item"] for event, payload in events if event == "response.output_item.done"]
    assert done_items[0]["type"] == "function_call"
    assert done_items[0]["thought_signature"] == signature

    indices = [
        payload["output_index"]
        for event, payload in events
        if event in ("response.output_item.added", "response.output_item.done")
    ]
    assert indices == [0, 0, 1, 2, 1, 2]

    completed = next(payload["response"] for event, payload in events if event == "response.completed")
    assert completed["usage"]["total_tokens"] == 20


def test_shell_function_maps_to_local_shell_call():
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"shell","args":{"command":["python","-c","print(42)"],"working_directory":"workspace"},"id":"shell_1"}}]}}]}',
        b'data: [DONE]',
    ]
    handler = DummyHandler()
    stream_responses_loop(_response(raw), handler, "gemini-3.8-flash", 456)
    events = _events(handler)
    item = next(payload["item"] for event, payload in events if event == "response.output_item.done")

    assert item["type"] == "local_shell_call"
    assert item["call_id"] == "shell_1"
    assert item["action"]["type"] == "exec"
    assert item["action"]["command"] == ["python", "-c", "print(42)"]
    assert item["action"]["env"] == {}
    assert item["action"]["working_directory"] == "workspace"


def test_managed_shell_function_maps_to_native_shell_call():
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"shell_command","args":{"commands":["pwd","python -V"],"max_output_length":4000,"timeout_ms":5000},"id":"shell_2"}}]}}]}',
        b'data: [DONE]',
    ]
    handler = DummyHandler()
    stream_responses_loop(
        _response(raw),
        handler,
        "gemini-3.8-flash",
        458,
        {"tool_output_types": {"shell_command": "shell_call"}},
    )
    events = _events(handler)
    item = next(payload["item"] for event, payload in events if event == "response.output_item.done")

    assert item["type"] == "shell_call"
    assert item["call_id"] == "shell_2"
    assert item["action"]["commands"] == ["pwd", "python -V"]
    assert item["action"]["max_output_length"] == 4000
    assert item["action"]["timeout_ms"] == 5000


def test_mcp_function_maps_back_to_mcp_call():
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"mcp__docs__search","args":{"query":"hello"},"id":"mcp_1"}}]}}]}',
        b'data: [DONE]',
    ]
    handler = DummyHandler()
    stream_responses_loop(
        _response(raw),
        handler,
        "gemini-3.8-flash",
        459,
        {
            "tool_output_types": {"mcp__docs__search": "mcp_call"},
            "tool_output_metadata": {
                "mcp__docs__search": {
                    "type": "mcp_call",
                    "server_label": "docs",
                    "original_name": "search",
                }
            },
        },
    )
    events = _events(handler)
    item = next(payload["item"] for event, payload in events if event == "response.output_item.done")
    assert item["type"] == "mcp_call"
    assert item["name"] == "search"
    assert item["server_label"] == "docs"
    assert item["arguments"] == '{"query": "hello"}'


def test_apply_patch_function_maps_to_native_apply_patch_call():
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"apply_patch","args":{"operation":{"type":"update_file","path":"src/demo.py","diff":"@@ -1 +1 @@\\n-old\\n+new"}},"id":"patch_1"}}]}}]}',
        b'data: [DONE]',
    ]
    handler = DummyHandler()
    stream_responses_loop(
        _response(raw),
        handler,
        "gemini-3.8-flash",
        457,
        {"tool_output_types": {"apply_patch": "apply_patch_call"}},
    )
    events = _events(handler)
    item = next(payload["item"] for event, payload in events if event == "response.output_item.done")

    assert item["type"] == "apply_patch_call"
    assert item["call_id"] == "patch_1"
    assert item["operation"]["type"] == "update_file"
    assert item["operation"]["path"] == "src/demo.py"
    assert item["operation"]["diff"].startswith("@@ -1 +1 @@")


def test_invalid_upstream_chunk_emits_failed_not_completed():
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"text":"before failure"}]}}]}',
        b'data: {invalid-json',
    ]
    handler = DummyHandler()
    stream_responses_loop(_response(raw), handler, "gemini-3.8-flash", 789)
    events = _events(handler)

    assert any(event == "response.failed" for event, _ in events)
    assert not any(event == "response.completed" for event, _ in events)
    failed = next(payload["response"] for event, payload in events if event == "response.failed")
    assert failed["error"]["code"] == "invalid_upstream_chunk"
