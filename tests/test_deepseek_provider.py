import json

from codex_proxy.config import config
from codex_proxy.providers.deepseek import DeepSeekProvider


class DummyResponse:
    status_code = 200
    text = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_lines(self):
        return [
            b'data: {"type":"response.completed","response":{"id":"resp_ds"}}',
            b'data: [DONE]',
        ]


class DummySession:
    def __init__(self):
        self.url = None
        self.headers = None
        self.body = None

    def post(self, url, data, headers, stream, timeout):
        self.url = url
        self.headers = headers
        self.body = data
        return DummyResponse()


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

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


def test_deepseek_forwards_native_responses_request(monkeypatch):
    monkeypatch.setattr(config, "deepseek_api_key", "test-key")
    monkeypatch.setattr(config, "deepseek_api_base", "https://api.deepseek.com")
    provider = DeepSeekProvider()
    session = DummySession()
    provider.session = session
    handler = DummyHandler()

    provider.handle_request(
        {
            "model": "deepseek-v4-flash",
            "input": [{"role": "user", "content": "hello"}],
            "instructions": "You are a coding agent.",
            "previous_response_id": "old-response-id",
        },
        handler,
    )

    assert session.url == "https://api.deepseek.com/responses"
    assert session.headers["Authorization"] == "Bearer test-key"
    body = json.loads(session.body)
    assert body["model"] == "deepseek-v4-flash"
    assert body["input"][0]["content"] == "hello"
    assert body["stream"] is True
    assert "previous_response_id" not in body
    assert "messages" not in body
