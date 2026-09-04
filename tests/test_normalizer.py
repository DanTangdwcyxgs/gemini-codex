from codex_proxy.normalizer import normalize_responses_request


def test_function_call_and_result_keep_name_call_id_and_signature():
    data = {
        "model": "gemini-3.8-flash",
        "input": [
            {
                "type": "function_call",
                "id": "call_123",
                "call_id": "call_123",
                "name": "read_file",
                "arguments": '{"path":"a.txt"}',
                "thought_signature": "sig-abc",
            },
            {
                "type": "function_call_output",
                "call_id": "call_123",
                "output": "hello",
            },
        ],
    }
    normalized = normalize_responses_request(data)
    assert normalized["messages"][0]["function_call"]["id"] == "call_123"
    assert normalized["messages"][0]["function_call"]["thought_signature"] == "sig-abc"
    assert normalized["messages"][1]["name"] == "read_file"
    assert normalized["messages"][1]["tool_call_id"] == "call_123"


def test_local_shell_tool_gets_realistic_gemini_schema_and_round_trips_output():
    data = {
        "model": "gemini-3.8-flash",
        "tools": [{"type": "local_shell"}],
        "input": [
            {
                "type": "local_shell_call",
                "id": "shell_1",
                "call_id": "shell_1",
                "action": {
                    "type": "exec",
                    "command": ["python", "-V"],
                    "working_directory": "C:/repo",
                    "env": {"MODE": "test"},
                },
            },
            {
                "type": "local_shell_call_output",
                "id": "shell_1",
                "output": "Python 3.x",
            },
        ],
    }
    normalized = normalize_responses_request(data)
    schema = normalized["tools"][0]["parameters"]
    assert schema["properties"]["command"]["type"] == "array"
    assert schema["required"] == ["command"]
    assert normalized["messages"][0]["function_call"]["args"]["command"] == ["python", "-V"]
    assert normalized["messages"][0]["function_call"]["args"]["env"] == {"MODE": "test"}
    assert normalized["messages"][1]["tool_call_id"] == "shell_1"
    assert normalized["messages"][1]["content"] == "Python 3.x"
