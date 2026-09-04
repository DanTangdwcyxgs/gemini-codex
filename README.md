# Gemini Codex

A Codex-compatible local proxy for using Gemini through the OpenAI Responses API.

## Goal

Add Gemini as a selectable backend while preserving the existing DeepSeek/Codex setup.

Target architecture:

```text
Codex CLI -> OpenAI Responses API -> local proxy (127.0.0.1:8765) -> Gemini API
```

Initial target: Gemini 3.x Flash, with the model configurable rather than hardcoded.

## Development status

- Repository initialized
- Source audit and compatibility work in progress
