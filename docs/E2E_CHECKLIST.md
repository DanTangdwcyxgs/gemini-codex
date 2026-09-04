# Gemini Codex E2E checklist

This checklist is for the final local acceptance test with Codex CLI 0.153.0-alpha.5.

## Known-good baseline from the 2026-09-03 external run

The external validation report recorded:

- 110 tests passed, 6 skipped
- Real Gemini 3.8 Flash text streaming through the proxy passed
- Real Gemini function calling through the proxy passed
- Public SSE shape confirmed as top-level `candidates` + `usageMetadata`
- `thoughtsTokenCount` confirmed in real responses
- Missing `thoughtSignature` was identified as the cause of the second-turn tool-call failure

The remaining external work was blocked by a network change that made direct access to the public Gemini API time out.

## Final local acceptance

1. Start the proxy with a real Gemini API key:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\proxy_start.ps1
```

2. Confirm the proxy is alive:

```powershell
curl.exe http://localhost:8765/health
curl.exe http://localhost:8765/v1/models
```

3. Add `codex_gemini_profile.toml.example` to `%USERPROFILE%\.codex\config.toml` without removing the existing DeepSeek configuration.

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
