from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_models(value: str) -> list[str]:
    return [m.strip() for m in value.split(",") if m.strip()]


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.getenv("CODEX_PROXY_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("CODEX_PROXY_PORT", "8765")))
    max_body_bytes: int = field(default_factory=lambda: int(os.getenv("CODEX_PROXY_MAX_BODY_BYTES", "16777216")))

    gemini_api_public: str = field(
        default_factory=lambda: os.getenv(
            "CODEX_PROXY_GEMINI_API_PUBLIC",
            "https://generativelanguage.googleapis.com",
        )
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_GEMINI_API_KEY", "")
    )

    deepseek_api_base: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_DEEPSEEK_API_BASE", "https://api.deepseek.com")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_DEEPSEEK_API_KEY", "")
    )
    deepseek_default_model: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_DEEPSEEK_MODEL", "deepseek-v4-flash")
    )

    models: list[str] = field(
        default_factory=lambda: _split_models(
            os.getenv(
                "CODEX_PROXY_MODELS",
                "deepseek-v4-flash,deepseek-v4-pro,gemini-3.8-flash,gemini-flash-latest",
            )
        )
    )
    compaction_model: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_COMPACTION_MODEL", "gemini-3.8-flash")
    )

    model_prefixes: dict[str, str] = field(
        default_factory=lambda: {
            "gemini": "gemini",
            "deepseek": "deepseek",
        }
    )

    request_timeout_connect: int = 10
    request_timeout_read: int = 600
    default_reasoning_level: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_GEMINI_THINKING_LEVEL", "medium")
    )
    debug_mode: bool = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_DEBUG", "false").lower() == "true"
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("CODEX_PROXY_LOG_LEVEL", "INFO").upper()
    )


config = Config()
