# Status

## Current stage

Multi-provider Codex proxy implemented in the new repository.

Validated in code:

- Gemini public SSE top-level `candidates` / `usageMetadata`
- `thoughtsTokenCount` and `totalTokenCount`
- Gemini 3.x `thinkingLevel` (`low` / `medium` / `high`)
- `x-goog-api-key`
- Function call `name` / `id` / `call_id`
- Gemini 3 thought-signature preservation
- Stable Responses `output_index` assignment
- Gemini function-result round-trip mapping
- DeepSeek native Responses API pass-through
- Model-name routing between DeepSeek and Gemini
- `/v1/models` discovery endpoint
- Gemini compaction endpoint
- Python 3.13 CI configuration

## Important limitation

The connector environment cannot execute the user's local Codex CLI or access the user's Gemini API key. Final acceptance still requires a local E2E run with Codex CLI 0.153.0-alpha.5 and a real Gemini API key.

## Next validation

1. Run repository pytest/CI.
2. Run a real Gemini text + reasoning request.
3. Run a real function-call/tool-result continuation.
4. Run a real Codex coding-agent task with shell and file changes.
5. Compare behavior against the existing DeepSeek setup.
