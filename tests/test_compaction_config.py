from codex_proxy.config import config


def test_compaction_model_is_separate_from_active_model_list():
    assert config.compaction_model == "gemini-3.8-flash"
    assert config.compaction_model in config.models
