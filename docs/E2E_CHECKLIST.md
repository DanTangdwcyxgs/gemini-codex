# Gemini Codex E2E checklist

This checklist is for the final local acceptance test with Codex CLI 0.153.0-alpha.5.

## Local validation — 2026-09-04

The latest local run verified:

- `python -m pytest -q` → **40 passed**
- Gemini API key is valid and the model catalog is reachable
- `gemini-3.8-flash` is available
- `gemini-flash-latest` resolves to `gemini-3.8-flash`
- Direct Gemini text generation works
- Direct Gemini public SSE streaming works with Gemini 3 thinking enabled
- Proxy `/health` and `/v1/models` work
- Codex CLI resolves `model=gemini-3.8-flash` and reaches `POST /v1/responses`
- Codex model metadata warning was removed with a local `models.json` entry

The final fresh Codex response was blocked by Gemini free-tier HTTP 429 quota exhaustion. This is an upstream quota limit, not a known proxy failure.

## Final local acceptance after quota reset

1. Start the proxy with a real Gemini API key:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\proxy_start.ps1 -ApiKeyFile C:\path\to\gemini-api-key.txt
```

2. Confirm the proxy is alive:

```powershell
curl.exe http://localhost:8765/health
curl.exe http://localhost:8765/v1/models
```

3. Keep the provider block in `%USERPROFILE%\.codex\config.toml` and copy `gemini.config.toml.example` to `%USERPROFILE%\.codex\gemini.config.toml`. Do not use the old `[profiles.gemini]` table.

4. Run a real Codex task with the Gemini profile. The acceptance task should force both shell and file tooling:

```text
Inspect a small file in the current workspace, make one safe change to it, run a command that verifies the change, then explain what changed.
```

5. Confirm the trace reaches all of these stages:

```text
Codex
  -> /v1/responses
  -> Gemini 3.8 Flash
  -> function_call / local_shell_call / apply_patch_call
  -> local tool execution by Codex
  -> function_call_output / local_shell_call_output / apply_patch_call_output
  -> Gemini continuation
  -> final answer
```

6. Repeat with another small coding task to make sure the second tool round is not a one-off success and that the model does not repeat an already-completed call.

7. Exercise `/v1/responses/compact` from Codex or a direct request. Verify that the returned `compaction` item is accepted on the next Gemini request and that the task can continue after compaction. The proxy's `encrypted_content` value is a proxy-owned compatibility envelope, not proof of OpenAI-compatible encryption semantics.

8. Switch back to the existing DeepSeek profile and run one small request. The DeepSeek body should continue to use the native Responses pass-through without Gemini normalization.

For a simple text-only smoke test, run:

```powershell
python .\scripts\test_proxy_e2e.py
```

## Pass criteria

- Text streaming works.
- Reasoning output does not break the response stream.
- Function call IDs and names survive across turns.
- Gemini 3.x `thoughtSignature` survives into the next function-call request.
- `local_shell_call` contains a valid `action.type=exec`, command array, and env object.
- `apply_patch_call` contains a valid create/update/delete operation.
- Shell/file tools execute normally in Codex.
- A second tool round continues instead of repeating the same call forever.
- Existing DeepSeek usage remains unchanged.
- Compaction does not corrupt the conversation state.
