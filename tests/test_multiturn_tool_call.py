import json

from codex_proxy.config import config
from codex_proxy.normalizer import normalize_responses_request
from codex_proxy.providers.gemini import GeminiProvider


class DummyResponse:
    status_code = 200
    text = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_lines(self):
        return [b"data: {\"candidates\":[]}", b"data: [DONE]"]


class DummySession:
    def __init__(self):
        self.body = None

    def post(self, url, data, headers, stream, timeout):
        self.body = data
        return DummyResponse()


class DummyWFile:
    def write(self, data):
        pass

    def flush(self):
        pass


class DummyHandler:
    def __init__(self):
        self.wfile = DummyWFile()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


def test_second_turn_reconstructs_function_call_result_with_signature(monkeypatch):
    request = {
        "model": "gemini-3.8-flash",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Read a.txt and tell me its contents."}],
            },
            {
                "type": "function_call",
                "id": "call_1",
                "call_id": "call_1",
                "name": "read_file",
                "arguments": '{"path":"a.txt"}',
                "thought_signature": "sig-123",
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "hello from file",
            },
        ],
    }

    normalized = normalize_responses_request(request)
    assert normalized["messages"][1]["function_call"]["thought_signature"] == "sig-123"
    assert normalized["messages"][2]["name"] == "read_file"
    assert normalized["messages"][2]["tool_call_id"] == "call_1"

    monkeypatch.setattr(config, "gemini_api_key", "test-key")
    provider = GeminiProvider()
    session = DummySession()
    provider.session = session
    provider.handle_request(normalized, DummyHandler())

    body = json.loads(session.body)
    model_call = body["contents"][1]["parts"][0]["functionCall"]
    assert model_call["id"] == "call_1"
    assert model_call["name"] == "read_file"
    assert model_call["args"] == {"path": "a.txt"}
    assert body["contents"][1]["parts"][0]["thoughtSignature"] == "sig-123"

    function_response = body["contents"][2]["parts"][0]["functionResponse"]
    assert function_response["id"] == "call_1"
    assert function_response["name"] == "read_file"
    assert function_response["response"]["result"] == "hello from file"
