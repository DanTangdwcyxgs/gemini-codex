from codex_proxy.normalizer import (
    decode_proxy_compaction,
    encode_proxy_compaction,
    normalize_responses_request,
)


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
                    "working_directory": "workspace",
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


def test_managed_shell_call_and_output_use_current_responses_shapes():
    data = {
        "model": "gemini-3.8-flash",
        "tools": [{"type": "shell"}],
        "input": [
            {
                "type": "shell_call",
                "id": "shell_2",
                "call_id": "shell_2",
                "action": {
                    "commands": ["pwd", "python -V"],
                    "max_output_length": 4000,
                    "timeout_ms": 5000,
                },
            },
            {
                "type": "shell_call_output",
                "call_id": "shell_2",
                "output": [{"stdout": "Python 3.x", "stderr": "", "outcome": {"type": "exit", "exit_code": 0}}],
            },
        ],
    }
    normalized = normalize_responses_request(data)
    assert normalized["tool_output_types"]["shell_command"] == "shell_call"
    assert normalized["messages"][0]["function_call"]["args"]["commands"] == ["pwd", "python -V"]
    assert normalized["messages"][0]["function_call"]["args"]["timeout_ms"] == 5000
    assert normalized["messages"][1]["tool_call_id"] == "shell_2"
    assert "Python 3.x" in normalized["messages"][1]["content"]


def test_reasoning_item_is_not_dropped_from_history():
    normalized = normalize_responses_request(
        {
            "model": "gemini-3.8-flash",
            "input": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "checked the failing test"}],
                }
            ],
        }
    )
    assert normalized["messages"] == [
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "",
        }
    ]


def test_apply_patch_tool_uses_native_operation_shape():
    data = {
        "model": "gemini-3.8-flash",
        "tools": [{"type": "apply_patch"}],
        "input": [
            {
                "type": "apply_patch_call",
                "id": "patch_1",
                "call_id": "patch_1",
                "operation": {
                    "type": "update_file",
                    "path": "src/demo.py",
                    "diff": "@@ -1 +1 @@\n-old\n+new",
                },
            },
            {
                "type": "apply_patch_call_output",
                "call_id": "patch_1",
                "output": "updated",
            },
        ],
    }
    normalized = normalize_responses_request(data)
    schema = normalized["tools"][0]["parameters"]
    assert schema["required"] == ["operation"]
    assert normalized["tool_output_types"]["apply_patch"] == "apply_patch_call"
    assert normalized["messages"][0]["function_call"]["args"]["type"] == "update_file"
    assert normalized["messages"][0]["function_call"]["args"]["path"] == "src/demo.py"
    assert normalized["messages"][1]["tool_call_id"] == "patch_1"


def test_proxy_compaction_is_round_trip_safe_and_opaque_provider_ciphertext_is_dropped():
    summary = "keep the selected files and continue the unfinished shell test"
    encoded = encode_proxy_compaction(summary)
    assert encoded.startswith("gemini-codex-v1:")
    assert decode_proxy_compaction(encoded) == summary
    assert decode_proxy_compaction("opaque-provider-ciphertext") is None

    normalized = normalize_responses_request(
        {"model": "gemini-3.8-flash", "input": [{"type": "compaction", "encrypted_content": encoded}]}
    )
    assert normalized["messages"] == [
        {"role": "user", "content": "[prior compaction summary]\n" + summary}
    ]

    opaque = normalize_responses_request(
        {"model": "gemini-3.8-flash", "input": [{"type": "compaction", "encrypted_content": "opaque-provider-ciphertext"}]}
    )
    assert opaque["messages"] == []
