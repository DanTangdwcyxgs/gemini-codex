import json

from codex_proxy.config import config
from codex_proxy.providers.gemini import GeminiProvider


class DummyResponse:
    status_code = 200
    text = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_lines(self):
        return [b'data: {"candidates":[{"content":{"parts":[{"text":"42"}]}}]}', b'data: [DONE]']


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
        pass

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


def test_second_turn_preserves_function_call_signature_and_result(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "test-key")
    provider = GeminiProvider()
    session = DummySession()
    provider.session = session

    provider.handle_request(
        {
            "model": "gemini-3.8-flash",
            "messages": [
                {
                    "role": "assistant",
                    "function_call": {
                        "name": "calculator",
                        "args": '{"expression":"21*2"}',
                        "id": "call_42",
                        "thought_signature": "sig-42",
                    },
                },
                {
                    "role": "tool",
                    "name": "calculator",
                    "tool_call_id": "call_42",
                    "content": "42",
                },
            ],
        },
        DummyHandler(),
    )

    body = json.loads(session.body)
    parts = body["contents"]
    function_call = next(
        part["functionCall"]
        for message in parts
        for part in message.get("parts", [])
        if "functionCall" in part
    )
    function_call_part = next(
        part
        for message in parts
        for part in message.get("parts", [])
        if "functionCall" in part
    )
    function_response = next(
        part["functionResponse"]
        for message in parts
        for part in message.get("parts", [])
        if "functionResponse" in part
    )

    assert function_call["name"] == "calculator"
    assert function_call["id"] == "call_42"
    assert function_call_part["thoughtSignature"] == "sig-42"
    assert function_response["name"] == "calculator"
    assert function_response["id"] == "call_42"
    assert function_response["response"]["result"] == "42"
