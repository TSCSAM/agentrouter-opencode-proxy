"""Tool results that carry an image must stay visible to the model on both routes."""

import base64
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("PROXY_URL", "http://127.0.0.1:7190")
KEY = os.environ["AGENTROUTER_KEY"]
MODEL = "gpt-6.1-sol"


def png(width: int, height: int, rgb: tuple[int, int, int]) -> str:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(body).decode()


IMAGE = png(64, 64, (255, 0, 0))
TOOL = {
    "type": "function",
    "function": {
        "name": "screenshot",
        "description": "Capture the screen",
        "parameters": {"type": "object", "properties": {}},
    },
}


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST")
    request.add_header("content-type", "application/json")
    request.add_header("authorization", f"Bearer {KEY}")
    request.add_header("x-api-key", KEY)
    request.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return {"http_error": exc.code, "body": exc.read().decode("utf-8", "replace")[:600]}
    try:
        payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    except json.JSONDecodeError:
        return {"raw": raw[:600]}
    return payload


print("== OpenAI path: tool result with image ==")
payload = post("/v1/chat/completions", {
    "model": MODEL,
    "max_tokens": 500,
    "messages": [
        {"role": "user", "content": "Use the screenshot tool."},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_shot_1", "type": "function", "function": {"name": "screenshot", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_call_id": "call_shot_1", "content": [
            {"type": "text", "text": "Screenshot captured."},
            {"type": "image_url", "image_url": {"url": IMAGE}},
        ]},
        {"role": "user", "content": "What color dominates the screenshot? Answer with one word."},
    ],
    "tools": [TOOL],
})
message = ((payload.get("choices") or [{}])[0]).get("message") or {}
print(json.dumps({"finish": (payload.get("choices") or [{}])[0].get("finish_reason"), "content": message.get("content")}, ensure_ascii=False)[:500])

print("\n== Anthropic path: tool_result with image ==")
payload = post("/v1/messages", {
    "model": MODEL,
    "max_tokens": 500,
    "messages": [
        {"role": "user", "content": "Use the screenshot tool."},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_shot_1", "name": "screenshot", "input": {}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_shot_1", "content": [
                {"type": "text", "text": "Screenshot captured."},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": IMAGE.split(",", 1)[1]}},
            ]},
            {"type": "text", "text": "What color dominates the screenshot? Answer with one word."},
        ]},
    ],
    "tools": [{
        "name": "screenshot",
        "description": "Capture the screen",
        "input_schema": {"type": "object", "properties": {}},
    }],
})
print(json.dumps({
    "stop_reason": payload.get("stop_reason"),
    "text": "".join(block.get("text", "") for block in payload.get("content") or [] if block.get("type") == "text"),
}, ensure_ascii=False)[:500])
