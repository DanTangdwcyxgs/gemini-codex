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

## External real-API evidence from 2026-09-03

A separate local Cline/GLM 5.3 run reported:

- 110 tests passed, 6 skipped
- Real Gemini 3.8 Flash text streaming through the proxy passed
- Real Gemini function calling through the proxy passed
- `thoughtsTokenCount` was observed in real responses
- A second-turn 400 was traced to a missing `thoughtSignature`; the propagation fix was then implemented

The same run could not re-test the second turn after a network change blocked direct Google API access.

## Current CI

The repository CI runs the same pytest suite on Python 3.13. Recent regression runs have passed after tool mapping and security-test changes.

## Remaining acceptance

The only validation that cannot be completed from the GitHub connector is the user's real local environment:

1. Gemini real API second-turn function-call continuation
2. Actual Codex CLI 0.153.0-alpha.5 coding-agent E2E with shell/file changes
3. Real compaction initiated by Codex and followed by a continuation turn
4. Final comparison against the user's existing DeepSeek setup

See `docs/E2E_CHECKLIST.md` for the exact final test sequence.
