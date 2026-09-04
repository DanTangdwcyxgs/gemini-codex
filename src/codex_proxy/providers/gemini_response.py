"""Normalize Gemini native streaming payloads across public/internal APIs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class GeminiChunk:
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None


def unwrap_gemini_chunk(data: Dict[str, Any]) -> GeminiChunk:
    """Accept both public Gemini and legacy/internal wrapped response shapes.

    Public Gemini streaming emits ``candidates`` and ``usageMetadata`` at the
    top level. Some internal endpoints wrap those fields under ``response``.
    """
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


def usage_to_responses_usage(usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Map Gemini token counters to the proxy's Responses usage shape."""
    if not usage:
        return None

    input_tokens = int(usage.get("promptTokenCount", 0) or 0)
    output_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    reasoning_tokens = int(
        usage.get("thoughtsTokenCount", usage.get("thinkingTokenCount", 0)) or 0
    )
    cached_tokens = int(usage.get("cachedContentTokenCount", 0) or 0)

    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": cached_tokens},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
        "total_tokens": input_tokens + output_tokens + reasoning_tokens,
    }


def iter_parts(chunk: GeminiChunk) -> Iterable[Dict[str, Any]]:
    """Yield candidate content parts while tolerating incomplete chunks."""
    for candidate in chunk.candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict):
                yield part
