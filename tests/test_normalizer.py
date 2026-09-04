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
