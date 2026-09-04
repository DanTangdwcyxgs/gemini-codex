from __future__ import annotations

from typing import Any


_UNSUPPORTED_SCHEMA_KEYS = {
    "additionalProperties",
    "title",
    "default",
    "minItems",
    "maxItems",
    "uniqueItems",
}


def sanitize_params(params: Any) -> Any:
    """Strip schema keywords Gemini function declarations do not need."""
    if isinstance(params, dict):
        return {
            key: sanitize_params(value)
            for key, value in params.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(params, list):
        return [sanitize_params(value) for value in params]
    return params


def normalize_function_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert flat or legacy nested Responses function tools to Gemini declarations."""
    declarations: list[dict[str, Any]] = []
    for tool in tools or []:
        nested = tool.get("function")
        if isinstance(nested, dict):
            fn = nested
        else:
            fn = tool
        name = fn.get("name")
        if not name:
            continue
        declarations.append(
            {
                "name": name,
                "description": fn.get("description", ""),
                "parameters": sanitize_params(fn.get("parameters", {})),
            }
        )
    return declarations
