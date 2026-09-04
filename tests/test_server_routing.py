from codex_proxy.server import provider_for_model, provider_key_for_model
from codex_proxy.providers.deepseek import DeepSeekProvider
from codex_proxy.providers.gemini import GeminiProvider


def test_model_prefix_routes_to_correct_provider():
    assert provider_key_for_model("deepseek-v4-flash") == "deepseek"
    assert provider_key_for_model("deepseek-v4-pro") == "deepseek"
    assert provider_key_for_model("gemini-3.8-flash") == "gemini"
    assert provider_key_for_model("gemini-flash-latest") == "gemini"
    assert isinstance(provider_for_model("deepseek-v4-flash"), DeepSeekProvider)
    assert isinstance(provider_for_model("gemini-3.8-flash"), GeminiProvider)


def test_unknown_model_is_rejected():
    try:
        provider_key_for_model("unknown-model")
    except Exception as exc:
        assert "Unsupported model provider" in str(exc)
    else:
        raise AssertionError("unknown model should be rejected")
