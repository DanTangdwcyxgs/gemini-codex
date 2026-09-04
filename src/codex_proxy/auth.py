from __future__ import annotations

from .config import config
from .exceptions import AuthenticationError


class GeminiAuth:
    """Public Gemini API-key authentication used by this Codex adapter."""

    def get_api_key(self) -> str:
        if not config.gemini_api_key:
            raise AuthenticationError(
                "CODEX_PROXY_GEMINI_API_KEY is not set. Create a Gemini API key and export it before starting the proxy."
            )
        return config.gemini_api_key
