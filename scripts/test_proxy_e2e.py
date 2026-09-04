"""Small real-network smoke test for the local Gemini proxy.

Requires the proxy to be running and CODEX_PROXY_GEMINI_API_KEY to be set in
that proxy process. This test does not read, print, or store the Gemini key.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        data_lines = [line[6:] for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        try:
            events.append(json.loads("\n".join(data_lines)))
        except json.JSONDecodeError:
            continue
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--model", default="gemini-flash-latest")
    args = parser.parse_args()

    payload = {
        "model": args.model,
        "stream": True,
        "input": [{"role": "user", "content": "Say PROXY-WORKS in one word."}],
    }

    request = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 2

    events = parse_sse(body)
    completed = next((event for event in events if event.get("type") == "response.completed"), None)
    failed = next((event for event in events if event.get("type") == "response.failed"), None)

    if status != 200 or failed or not completed:
        print(body, file=sys.stderr)
        return 1

    output_text: list[str] = []
    for event in events:
        if event.get("type") != "response.output_text.delta":
            continue
        delta = event.get("delta")
        if isinstance(delta, str):
            output_text.append(delta)

    response_obj = completed.get("response", {})
    print(f"MODEL: {response_obj.get('model', args.model)}")
    print(f"REPLY: {''.join(output_text).strip()}")
    print("PASS: response.completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
