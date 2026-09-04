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
            result.append((lines[0][len("event: "):], json.loads(lines[1][len("data: "):])) )
    return result


def test_stream_preserves_function_signature_and_unique_output_indices():
    signature = "signed-thought"
    raw = [
        b'data: {"candidates":[{"content":{"parts":[{"functionCall":{"name":"read_file","args":{"path":"a.txt"},"id":"call_1"},"thoughtSignature":"'+signature.encode()+b'"}]}}]}',
        b'data: {"candidates":[{"content":{"parts":[{"thought":true,"text":"thinking"}]}}]}',
        b'data: {"candidates":[{"content":{"parts":[{"text":"done"}]}}],"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":4,"thoughtsTokenCount":6,"totalTokenCount":20}}',
        b'data: [DONE]',
    ]

    class Resp:
        headers = {}
        def iter_lines(self):
            return raw

    handler = DummyHandler()
    stream_responses_loop(Resp(), handler, "gemini-3.8-flash", 123)
    events = _events(handler)

    done_items = [
        payload["item"]
        for event, payload in events
        if event == "response.output_item.done"
    ]
    assert done_items[0]["type"] == "function_call"
    assert done_items[0]["thought_signature"] == signature
    indices = [
        payload["output_index"]
        for event, payload in events
        if event in ("response.output_item.added", "response.output_item.done")
    ]
    assert indices == [0, 1, 1, 2, 2, 0]
    completed = next(payload["response"] for event, payload in events if event == "response.completed")
    assert completed["usage"]["total_tokens"] == 20
