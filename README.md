# Gemini Codex

A local OpenAI Responses-compatible proxy for running Gemini 3.x Flash from the current Codex CLI, with an optional DeepSeek Responses pass-through.

## Architecture

```text
Codex CLI
   |
   | OpenAI Responses API
   v
localhost:8765
   |
   +-- deepseek-* --> https://api.deepseek.com/responses
   `-- gemini-*   --> Google Gemini native GenerateContent SSE
```

The proxy routes by model name. Codex itself does not need to be patched.

## Gemini 3.x compatibility

The adapter handles the important differences between Codex/OpenAI Responses and Gemini native GenerateContent:

- public Gemini SSE uses top-level `candidates` and `usageMetadata`
- Gemini 3.x reasoning uses `thinkingLevel`
- `thoughtsTokenCount` is mapped to Responses reasoning usage
- Gemini `thoughtSignature` is preserved across function-call turns
- function-call `name`, `id`, and `call_id` survive the round trip
- Responses `output_index` values remain stable across reasoning, tool, and message items
- tool schemas are normalized before being sent to Gemini

## Models

Default list:

- `deepseek-v4-flash`
- `deepseek-v4-pro`
- `gemini-3.8-flash`
- `gemini-flash-latest`

Override with `CODEX_PROXY_MODELS`.

## Environment

Gemini:

```text
CODEX_PROXY_GEMINI_API_KEY=...
CODEX_PROXY_GEMINI_THINKING_LEVEL=medium
CODEX_PROXY_COMPACTION_MODEL=gemini-3.8-flash
```

DeepSeek pass-through:

```text
CODEX_PROXY_DEEPSEEK_API_KEY=...
CODEX_PROXY_DEEPSEEK_API_BASE=https://api.deepseek.com
CODEX_PROXY_DEEPSEEK_MODEL=deepseek-v4-flash
```

Server:

```text
CODEX_PROXY_HOST=localhost
CODEX_PROXY_PORT=8765
```

## Windows

Store the Gemini key outside Git, for example in a local file such as:

```text
<your-local-key-file>
```

Then start the proxy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\proxy_start.ps1
```

The script reads the key, sets the environment variable for the current proxy process, and never writes the key to the repository.

## Codex profile

Copy `codex_gemini_profile.toml.example` into `%USERPROFILE%\.codex\config.toml` while keeping the existing DeepSeek configuration intact.

Then use:

```text
codex --profile gemini
```

## Testing

```bash
python -m pytest -q
```

CI runs the same pytest suite on Python 3.13.

For the final real-machine acceptance test, see `docs/E2E_CHECKLIST.md`.
