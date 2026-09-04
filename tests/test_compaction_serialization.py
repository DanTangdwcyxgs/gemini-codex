from codex_proxy.server import _compaction_text


def test_compaction_serializes_function_call_and_tool_result():
    call = _compaction_text(
        {
            "role": "assistant",
            "function_call": {
                "name": "read_file",
                "args": {"path": "demo.txt"},
                "id": "call_1",
            },
        }
    )
    result = _compaction_text(
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "hello",
        }
    )

    assert "[function_call]" in call
    assert "read_file" in call
    assert "demo.txt" in call
    assert "[tool_result id=call_1]" in result
    assert "hello" in result
