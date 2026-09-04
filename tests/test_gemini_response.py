from codex_proxy.providers.gemini_response import (
    iter_parts,
    unwrap_gemini_chunk,
    usage_to_responses_usage,
)


def test_public_gemini_chunk_is_unwrapped():
    chunk = unwrap_gemini_chunk(
        {
            "candidates": [
                {"content": {"parts": [{"text": "hello"}]}}
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "thoughtsTokenCount": 6,
                "cachedContentTokenCount": 2,
            },
        }
    )
    assert list(iter_parts(chunk)) == [{"text": "hello"}]
    assert chunk.usage["thoughtsTokenCount"] == 6


def test_internal_wrapped_chunk_is_supported():
    chunk = unwrap_gemini_chunk(
        {
            "response": {
                "candidates": [{"content": {"parts": [{"text": "hello"}]}}],
                "usageMetadata": {"promptTokenCount": 3},
            }
        }
    )
    assert [p["text"] for p in iter_parts(chunk)] == ["hello"]
    assert chunk.usage["promptTokenCount"] == 3


def test_thoughts_token_count_has_priority_but_legacy_name_is_supported():
    usage = usage_to_responses_usage(
        {
            "promptTokenCount": 100,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 30,
            "thinkingTokenCount": 9,
        }
    )
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["output_tokens_details"]["reasoning_tokens"] == 30
    assert usage["total_tokens"] == 150

    legacy = usage_to_responses_usage(
        {
            "promptTokenCount": 1,
            "candidatesTokenCount": 2,
            "thinkingTokenCount": 3,
        }
    )
    assert legacy["output_tokens_details"]["reasoning_tokens"] == 3
    assert legacy["total_tokens"] == 6
