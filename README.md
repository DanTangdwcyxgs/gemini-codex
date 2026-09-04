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
- Codex `local_shell` is converted to a Gemini function declaration and returned as a native `local_shell_call`
- `local_shell_call_output` is reconstructed as a Gemini `functionResponse` on the next turn
- Codex `apply_patch` / `apply_patch_call` is represented as a native `apply_patch_call` response item
- malformed or interrupted Gemini streams produce `response.failed` instead of a false `response.completed`
- proxy-generated compaction summaries are wrapped in a private `gemini-codex-v1:` compatibility envelope so the same proxy can safely restore them later

The last compaction item is intentionally not treated as real OpenAI encryption. Opaque encrypted content from another provider is not forwarded to Gemini because Gemini cannot decrypt provider-specific ciphertext.

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
C:\path\to\gemini-api-key.txt
```

Then start the proxy with the key file explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\proxy_start.ps1 -ApiKeyFile C:\path\to\gemini-api-key.txt
```

The script reads the key, sets the environment variable for the current proxy process, and never writes the key to the repository.

## Codex profile

The current Codex CLI profile format keeps the provider block in `%USERPROFILE%\.codex\config.toml` and puts the selected model/auth settings in a separate `%USERPROFILE%\.codex\gemini.config.toml` file. Do not use the removed legacy `[profiles.gemini]` table.

Add this provider block to `%USERPROFILE%\.codex\config.toml` while keeping the existing DeepSeek configuration intact:

```toml
[model_providers.gemini-proxy]
name = "gemini-proxy"
base_url = "http://127.0.0.1:8765/v1"
wire_api = "responses"
experimental_bearer_token = "local-proxy"
```

Then copy `gemini.config.toml.example` to `%USERPROFILE%\.codex\gemini.config.toml`.

Use:

```text
codex --profile gemini
```

A local `models.json` entry may also be needed for Codex builds that do not know the Gemini model metadata yet.

## Testing

```bash
python -m pytest -q
```

The repository test suite covers protocol, stream, tool-call, compaction, security-scan, model-routing, and HTTP-level regression behavior. CI runs the same pytest suite on Python 3.13.

For final real-machine acceptance, see `docs/E2E_CHECKLIST.md` and the latest local results in `docs/E2E_RESULTS_2026-09-04.md`.
