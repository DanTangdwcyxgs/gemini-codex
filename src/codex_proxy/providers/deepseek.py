from __future__ import annotations

import json
from typing import Any

from ..config import config
from ..exceptions import AuthenticationError, ProviderError
from ..utils import create_session, json_dumps


class DeepSeekProvider:
    """Pass OpenAI Responses requests through to the official DeepSeek Responses API."""

    def __init__(self) -> None:
        self.session = create_session()

    def handle_request(self, data: dict[str, Any], handler: Any) -> None:
        if not config.deepseek_api_key:
            raise AuthenticationError(
                "CODEX_PROXY_DEEPSEEK_API_KEY is not set."
            )

        body = dict(data)
        # DeepSeek Responses is stateless; Codex history is already present in input.
        body.pop("_headers", None)
        body.pop("previous_response_id", None)
        body.pop("messages", None)
        body.pop("_is_responses_api", None)
        body["model"] = data.get("model") or config.deepseek_default_model
        body["stream"] = True

        url = f"{config.deepseek_api_base.rstrip('/')}/responses"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.deepseek_api_key}",
        }

        try:
            with self.session.post(
                url,
                data=json_dumps(body),
                headers=headers,
                stream=True,
                timeout=(config.request_timeout_connect, config.request_timeout_read),
            ) as resp:
                if resp.status_code != 200:
                    raise ProviderError(
                        f"DeepSeek API returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )
                handler.send_response(200)
                handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
                handler.send_header("Connection", "keep-alive")
                handler.end_headers()
                for line in resp.iter_lines():
                    if line:
                        handler.wfile.write(line + b"\n")
                        handler.wfile.write(b"\n")
                        handler.wfile.flush()
        except (ProviderError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
