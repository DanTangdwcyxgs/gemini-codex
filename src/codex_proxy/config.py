from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.getenv("CODEX_PROXY_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("CODEX_PROXY_PORT", "8765")))
    gemini_api_public: str = field(
        default_factory=lambda: os.getenv(
            "CODEX_PROXY_GEMINI_API_PUBLIC",
            "https://generativelanguage.googleapis.com",
        )
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_GEMINI_API_KEY", "")
    )
    models: list[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.getenv("CODEX_PROXY_MODELS", "gemini-3.8-flash,gemini-flash-latest").split(",")
            if m.strip()
        ]
    )
    request_timeout_connect: int = 10
    request_timeout_read: int = 600
    default_reasoning_level: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_GEMINI_THINKING_LEVEL", "medium")
    )
    debug_mode: bool = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_DEBUG", "false").lower() == "true"
    )


config = Config()
