# Gemini Codex

A small local proxy that lets the current Codex CLI use Gemini through the OpenAI Responses API, while keeping DeepSeek available through the same endpoint.

## Architecture

```text
Codex CLI
   |
   | OpenAI Responses API
   v
127.0.0.1:8765
   |
   +-- deepseek-* --> https://api.deepseek.com/responses
   |
   `-- gemini-*   --> Google Gemini native GenerateContent SSE
```

The proxy routes by model name, so changing the Codex model changes the upstream provider without modifying Codex itself.

## Models

Default model list:

- `deepseek-v4-flash`
- `deepseek-v4-pro`
- `gemini-3.8-flash`
- `gemini-flash-latest`

Set `CODEX_PROXY_MODELS` to override the list.

## Environment

Gemini:

```text
CODEX_PROXY_GEMINI_API_KEY=...
CODEX_PROXY_GEMINI_THINKING_LEVEL=medium
```

DeepSeek:

```text
CODEX_PROXY_DEEPSEEK_API_KEY=...
CODEX_PROXY_DEEPSEEK_API_BASE=https://api.deepseek.com
CODEX_PROXY_DEEPSEEK_MODEL=deepseek-v4-flash
```

Server:

```text
CODEX_PROXY_HOST=127.0.0.1
CODEX_PROXY_PORT=8765
```

## Current compatibility work

Gemini 3.x support includes native `thinkingLevel`, thought-signature preservation, top-level public SSE parsing, usage mapping, function calls, function results, and stable Responses output indexes.

DeepSeek is passed through in its native Responses API format. DeepSeek's current API is stateless for Responses, so the client must provide the conversation history needed for each request.

## Testing

```bash
python -m pytest -q
```

The test suite covers Gemini response parsing, Gemini 3.x request construction, tool-call metadata, multi-turn normalization, and DeepSeek/Gemini routing.
