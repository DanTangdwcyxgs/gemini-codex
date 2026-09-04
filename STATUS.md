# Status

## Current stage

Gemini 3.8 Flash compatibility work is implemented and protected by Python 3.13 CI.

## Code-validated

- Public Gemini SSE top-level `candidates` / `usageMetadata`
- `thoughtsTokenCount` and `totalTokenCount`
- Gemini 3.x `thinkingLevel` (`low` / `medium` / `high`)
- `x-goog-api-key`
- Function call `name` / `id` / `call_id`
- Gemini 3 thought-signature preservation
- Stable Responses `output_index` assignment
- Function-result round-trip reconstruction for a second model turn
- Codex `local_shell` -> Gemini declaration -> native `local_shell_call`
- Codex `local_shell_call_output` reconstruction for the next Gemini turn
- Full `local_shell_call.action` fields: command, env, working directory, timeout, user
- Codex `apply_patch` -> Gemini declaration -> native `apply_patch_call`
- `apply_patch_call_output` round-trip as tool output
- Malformed upstream SSE produces `response.failed` rather than false completion
- Proxy-generated compaction summary round-trip via a proxy-owned compatibility envelope
- Opaque provider-specific encrypted content is not forwarded to Gemini
- DeepSeek Responses pass-through remains isolated from Gemini normalization
- Model-name routing
- `/v1/models`
- HTTP-level Responses routing
- Configurable compaction model
- Windows startup helper without storing API keys
- Repository regression scan for obvious secrets and personal paths

## Latest local validation — 2026-09-04

Environment: Windows Server (win32), Python 3.13.13, Codex CLI 0.153.0-alpha.5.

- `python -m pytest -q` → **40 passed**
- Gemini API key validation against the model catalog → HTTP 200
- `gemini-3.8-flash` is available
- `gemini-flash-latest` resolved to `gemini-3.8-flash`
- Direct Gemini text generation succeeded
- Direct Gemini public SSE streaming succeeded with Gemini 3 thinking enabled
- Local proxy `/health` and `/v1/models` succeeded
- Codex CLI resolved `model=gemini-3.8-flash`, `provider=gemini-proxy`
- Codex reached the proxy through `POST /v1/responses`
- The local Codex `models.json` entry removed the missing-model-metadata warning

The final fresh Codex generation attempt was blocked by Gemini HTTP 429 `RESOURCE_EXHAUSTED` after the free-tier request quota for `gemini-3.8-flash` was exhausted. This is an upstream quota limitation rather than a repository test failure.

## External real-API evidence from 2026-09-03

A separate local Cline/GLM 5.3 run reported:

- 110 tests passed, 6 skipped
- Real Gemini 3.8 Flash text streaming through the proxy passed
- Real Gemini function calling through the proxy passed
- `thoughtsTokenCount` was observed in real responses
- A second-turn 400 was traced to a missing `thoughtSignature`; the propagation fix was then implemented

The same run could not re-test the second turn after a network change blocked direct Google API access.

## Current CI

The repository test suite is covered by Python 3.13 CI. Recent regression work added coverage for Gemini tool mapping, output ordering, standalone thought signatures, malformed streams, and output-token-limit mapping.

## Remaining acceptance

After Gemini quota reset, the only remaining validation is the user's real local acceptance:

1. Fresh real Codex text completion through the proxy.
2. Multi-turn tool continuation with real Gemini `thoughtSignature` propagation.
3. Actual Codex coding-agent shell/file execution and a second tool round.
4. Compaction followed by a continuation turn.
5. One regression check using the existing DeepSeek setup.

See `docs/E2E_CHECKLIST.md` and `docs/E2E_RESULTS_2026-09-04.md`.
