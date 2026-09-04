"""Normalize Gemini native streaming payloads across public/internal APIs."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeminiChunk:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] | None = None


def unwrap_gemini_chunk(data: dict[str, Any]) -> GeminiChunk:
    """Accept both public Gemini and legacy/internal wrapped response shapes."""
    response = data.get("response")
    if isinstance(response, dict):
        candidates = response.get("candidates")
        usage = response.get("usageMetadata")
        if candidates is not None or usage is not None:
            return GeminiChunk(
                candidates=list(candidates or []),
                usage=usage if isinstance(usage, dict) else None,
            )

    candidates = data.get("candidates")
    usage = data.get("usageMetadata")
    return GeminiChunk(
        candidates=list(candidates or []),
        usage=usage if isinstance(usage, dict) else None,
    )


def usage_to_responses_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    """Map Gemini token counters to the proxy's Responses usage shape."""
    if not usage:
        return None

    input_tokens = int(usage.get("promptTokenCount", 0) or 0)
    output_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    reasoning_tokens = int(
        usage.get("thoughtsTokenCount", usage.get("thinkingTokenCount", 0)) or 0
    )
    cached_tokens = int(usage.get("cachedContentTokenCount", 0) or 0)
    total_tokens = int(
        usage.get("totalTokenCount", input_tokens + output_tokens + reasoning_tokens) or 0
    )

    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": cached_tokens},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
        "total_tokens": total_tokens,
    }


def iter_parts(chunk: GeminiChunk) -> Iterable[dict[str, Any]]:
    """Yield candidate content parts while tolerating incomplete chunks."""
    for candidate in chunk.candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict):
                yield part
