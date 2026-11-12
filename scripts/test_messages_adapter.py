"""Test the Anthropic /v1/messages adapter, including streaming tool calls."""

import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("PROXY_URL", "http://127.0.0.1:7190")
KEY = os.environ["AGENTROUTER_KEY"]
MODEL = "gpt-6.1-sol"
TOOLS = [{
    "name": "get_secret_code",
    "description": "Return the secret code",
    "input_schema": {"type": "object", "properties": {}},
}]


def post(body: dict) -> str:
    request = urllib.request.Request(
        BASE + "/v1/messages",
        data=json.dumps(body).encode(),
        method="POST",
    )
    request.add_header("content-type", "application/json")
    request.add_header("x-api-key", KEY)
    request.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}: " + exc.read().decode("utf-8", "replace")[:600]


print("== messages tools non-stream ==")
raw = post({
    "model": MODEL,
    "max_tokens": 400,
    "messages": [{"role": "user", "content": "Use the get_secret_code tool."}],
    "tools": TOOLS,
})
try:
    payload = json.loads(raw)
    print("stop_reason:", payload.get("stop_reason"))
    for block in payload.get("content", []):
        print("block:", block.get("type"), json.dumps(block, ensure_ascii=False)[:300])
except json.JSONDecodeError:
    print(raw[:600])

print("\n== messages tools stream ==")
raw = post({
    "model": MODEL,
    "max_tokens": 400,
    "stream": True,
    "messages": [{"role": "user", "content": "Use the get_secret_code tool."}],
    "tools": TOOLS,
})
events = []
text = ""
tool_name = None
tool_json = ""
stop_reason = None
for line in raw.splitlines():
    if line.startswith("event: "):
        events.append(line[7:])
    elif line.startswith("data: "):
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        kind = data.get("type")
        if kind == "content_block_start" and data.get("content_block", {}).get("type") == "tool_use":
            tool_name = data["content_block"].get("name")
        elif kind == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                text += delta.get("text", "")
            elif delta.get("type") == "input_json_delta":
                tool_json += delta.get("partial_json", "")
        elif kind == "message_delta":
            stop_reason = data.get("delta", {}).get("stop_reason")
print(json.dumps({
    "events": sorted(set(events)),
    "text": text,
    "tool_name": tool_name,
    "tool_args": tool_json,
    "stop_reason": stop_reason,
}, ensure_ascii=False))

print("\n== messages tool result follow-up ==")
raw = post({
    "model": MODEL,
    "max_tokens": 500,
    "messages": [
        {"role": "user", "content": "Use the get_secret_code tool and tell me the code."},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_test_1", "name": "get_secret_code", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_test_1", "content": "The secret code is ZEBRA-42."}]},
    ],
    "tools": TOOLS,
})
try:
    payload = json.loads(raw)
    print("stop_reason:", payload.get("stop_reason"))
    print("text:", "".join(b.get("text", "") for b in payload.get("content", []))[:300])
except json.JSONDecodeError:
    print(raw[:600])
