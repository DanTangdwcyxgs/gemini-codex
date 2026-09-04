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
        return [b'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}', b'data: [DONE]']


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


class DummyHandler:
    def __init__(self):
        self.events = []
        self.wfile = self

    def send_response(self, status):
        self.events.append(("status", status))

    def send_header(self, key, value):
        self.events.append((key, value))

    def end_headers(self):
        self.events.append(("headers_done", None))

    def flush(self):
        pass

    def write(self, data):
        self.events.append(("body", data))


def test_gemini_38_request_uses_thinking_level_and_api_header(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "test-key")
    monkeypatch.setattr(config, "default_reasoning_level", "high")
    provider = GeminiProvider()
    session = DummySession()
    provider.session = session
    handler = DummyHandler()

    provider.handle_request(
        {"model": "gemini-3.8-flash", "messages": [{"role": "user", "content": "hello"}]},
        handler,
    )

    assert session.headers["x-goog-api-key"] == "test-key"
    assert "?alt=sse" in session.url
    body = json.loads(session.body)
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "high"
    assert "temperature" not in body["generationConfig"]
    assert "topP" not in body["generationConfig"]
    assert "topK" not in body["generationConfig"]
