#!/usr/bin/env python3
"""
agentrouter-proxy: thin reverse-proxy for agentrouter.org.

Supports both:
  1) Anthropic Messages API (/v1/messages and /messages)
  2) OpenAI Chat Completions API (/v1/chat/completions and /chat/completions)

AgentRouter's Aliyun WAF fingerprints the client that issues the request.
Requests that do not look like a Python Anthropic SDK client are rejected with
"unauthorized client detected" before the API key is even evaluated.

Key relay behavior:
  If AGENTROUTER_API_KEY is configured on the proxy, that key is used.
  If AGENTROUTER_API_KEY is NOT set, the proxy automatically extracts the API key
  from the incoming request's Authorization / x-api-key header and uses it for
  the upstream call to AgentRouter. This allows callers (like 9Router Proxy) to
  manage their own AgentRouter keys.
"""
import asyncio
import hmac
import json
import os
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


# ── Config ────────────────────────────────────────────────────────────────────


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    return _env_str(name, str(default)).lower() in {"1", "true", "yes", "on"}


TARGET             = _env_str("AGENTROUTER_TARGET", "https://agentrouter.org").rstrip("/")
HOST               = _env_str("HOST", "0.0.0.0")
PORT               = _env_int("PORT", 7187)
KEY_FILE           = Path.home() / ".config/opencode/api_keys/AGENT_ROUTER_API_KEY"
AUTH_TOKEN         = _env_str("PROXY_AUTH_TOKEN", "")
ALLOW_ANONYMOUS    = _env_bool("PROXY_ALLOW_ANONYMOUS", True)  # default True so key relay works out of the box
MODEL_IDS          = [m for m in (x.strip() for x in _env_str("PROXY_MODEL_IDS", "claude-opus-4-6,gpt-4o,gpt-4o-mini,deepseek-chat").split(",")) if m]
CONNECT_TIMEOUT    = _env_float("PROXY_CONNECT_TIMEOUT", 10.0)
READ_TIMEOUT       = _env_float("PROXY_READ_TIMEOUT", 120.0)
WRITE_TIMEOUT      = _env_float("PROXY_WRITE_TIMEOUT", 30.0)
CHUNK_TIMEOUT      = _env_float("PROXY_CHUNK_TIMEOUT", 120.0)
CALL_WORKERS       = max(1, _env_int("PROXY_CALL_WORKERS", 16))
STREAM_WORKERS     = max(1, _env_int("PROXY_STREAM_WORKERS", 32))
STREAM_ERROR_STATUS = _env_bool("PROXY_STREAM_ERROR_STATUS", False)

_TIMEOUT = anthropic.Timeout(
    connect=CONNECT_TIMEOUT,
    read=READ_TIMEOUT,
    write=WRITE_TIMEOUT,
    pool=CONNECT_TIMEOUT,
)

_CALL_EXECUTOR   = ThreadPoolExecutor(max_workers=CALL_WORKERS, thread_name_prefix="ar-call")
_STREAM_EXECUTOR = ThreadPoolExecutor(max_workers=STREAM_WORKERS, thread_name_prefix="ar-stream")


def _resolve_api_key(request: Request) -> str:
    """Return configured key or extract presented key from incoming request."""
    env_key = os.environ.get("AGENTROUTER_API_KEY", "").strip()
    if not env_key and KEY_FILE.exists():
        env_key = KEY_FILE.read_text().strip()
    if env_key:
        return env_key

    # Extract key from incoming headers (bearer token or x-api-key)
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        req_key = header[7:].strip()
        if req_key:
            return req_key
    x_key = request.headers.get("x-api-key", "").strip()
    if x_key:
        return x_key

    raise RuntimeError("No AgentRouter API key provided in environment or request headers.")


def _get_client_for_request(request: Request) -> anthropic.Anthropic:
    """Create an Anthropic SDK client using the key for this request."""
    api_key = _resolve_api_key(request)
    kwargs = {
        "api_key": api_key,
        "base_url": TARGET,
        "timeout": _TIMEOUT,
        "max_retries": 0,
    }
    if hasattr(anthropic, "DefaultHttpxClient"):
        kwargs["http_client"] = anthropic.DefaultHttpxClient(timeout=_TIMEOUT)
    return anthropic.Anthropic(**kwargs)


# ── Request translation ───────────────────────────────────────────────────────

_SKIP  = {"stream"}
_STRIP = {"thinking", "output_config"}


def _kwargs(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _SKIP and k not in _STRIP}


def _image_part(part: dict) -> dict | None:
    """Convert an OpenAI image_url part into an Anthropic image block."""
    image = part.get("image_url")
    url = image.get("url", "") if isinstance(image, dict) else (image or "")
    if not url:
        return None
    if url.startswith("data:"):
        header, _, data = url.partition(",")
        media_type = header[5:].split(";")[0] or "image/png"
        return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
    return {"type": "image", "source": {"type": "url", "url": url}}


def _content_blocks(content) -> list:
    """Convert OpenAI message content into Anthropic content blocks."""
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    blocks = []
    for part in content:
        if isinstance(part, str):
            blocks.append({"type": "text", "text": part})
            continue
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype in ("text", "input_text"):
            text = part.get("text", "")
            if text:
                blocks.append({"type": "text", "text": text})
        elif ptype in ("image_url", "input_image"):
            block = _image_part(part)
            if block:
                blocks.append(block)
    return blocks


def _tool_use_blocks(message: dict) -> list:
    """Convert OpenAI assistant tool_calls into Anthropic tool_use blocks."""
    calls = list(message.get("tool_calls") or [])
    if not calls and isinstance(message.get("function_call"), dict):
        calls = [{"function": message["function_call"]}]
    blocks = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        raw = fn.get("arguments", "{}")
        if isinstance(raw, str):
            try:
                arguments = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                arguments = {"value": raw}
        elif isinstance(raw, dict):
            arguments = raw
        else:
            arguments = {}
        blocks.append({
            "type": "tool_use",
            "id": call.get("id") or f"toolu_{uuid.uuid4().hex[:16]}",
            "name": name,
            "input": arguments,
        })
    return blocks


def _tool_result_block(message: dict) -> dict:
    content = message.get("content")
    if isinstance(content, str):
        return {
            "type": "tool_result",
            "tool_use_id": message.get("tool_call_id", ""),
            "content": content,
        }
    blocks = []
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype in ("text", "input_text"):
                text = part.get("text", "")
                if text:
                    blocks.append({"type": "text", "text": text})
            elif ptype in ("image_url", "input_image"):
                image = _image_part(part)
                if image:
                    blocks.append(image)
    elif content:
        blocks.append({"type": "text", "text": str(content)})
    return {
        "type": "tool_result",
        "tool_use_id": message.get("tool_call_id", ""),
        "content": blocks,
    }


def _is_tool_result_only(message: dict) -> bool:
    content = message.get("content")
    return (
        message.get("role") == "user"
        and isinstance(content, list)
        and bool(content)
        and all(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)
    )


def _convert_tools(tools) -> list:
    converted = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") not in (None, "function"):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = fn.get("name")
        if not name:
            continue
        schema = fn.get("parameters") or fn.get("input_schema")
        if not isinstance(schema, dict) or not schema:
            schema = {"type": "object", "properties": {}}
        item = {
            "name": name,
            "input_schema": schema,
        }
        if fn.get("description"):
            item["description"] = fn["description"]
        converted.append(item)
    return converted


def _convert_tool_choice(choice) -> dict | None:
    if isinstance(choice, str):
        if choice == "auto":
            return {"type": "auto"}
        if choice in ("required", "any"):
            return {"type": "any"}
        return None
    if isinstance(choice, dict):
        ctype = choice.get("type")
        if ctype in ("function", "tool"):
            name = (choice.get("function") or {}).get("name") or choice.get("name")
            if name:
                return {"type": "tool", "name": name}
        elif ctype in ("auto", "any"):
            return {"type": ctype}
    return None


def _merge_roles(messages: list) -> list:
    """Anthropic expects alternating turns; merge adjacent messages with the same role."""
    merged = []
    for message in messages:
        if merged and merged[-1]["role"] == message["role"]:
            previous = merged[-1]
            prev_blocks = previous["content"] if isinstance(previous["content"], list) else _content_blocks(previous["content"])
            new_blocks = message["content"] if isinstance(message["content"], list) else _content_blocks(message["content"])
            previous["content"] = prev_blocks + new_blocks
        else:
            merged.append(dict(message))
    return merged


def _openai_to_anthropic(body: dict) -> dict:
    model = body.get("model", "claude-opus-4-6")
    # Strip optional group/provider prefix like "agentrouter/" or "new-provider/"
    if "/" in model:
        model = model.split("/", 1)[1]

    max_tokens = body.get("max_tokens") or body.get("max_completion_tokens") or 4096

    system_parts = []
    messages = []

    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content")

        if role in ("system", "developer"):
            if isinstance(content, str) and content:
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in ("text", "input_text"):
                        system_parts.append(part.get("text", ""))
            continue

        if role == "tool":
            block = _tool_result_block(msg)
            if messages and _is_tool_result_only(messages[-1]):
                messages[-1]["content"].append(block)
            else:
                messages.append({"role": "user", "content": [block]})
            continue

        if role == "function":
            name = msg.get("name", "function")
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            messages.append({"role": "user", "content": [{"type": "text", "text": f"[{name} result] {text}"}]})
            continue

        if role == "assistant":
            blocks = _content_blocks(content) + _tool_use_blocks(msg)
            blocks = [b for b in blocks if not (b.get("type") == "text" and not b.get("text"))]
            if blocks:
                messages.append({"role": "assistant", "content": blocks})
            continue

        blocks = _content_blocks(content)
        if blocks:
            messages.append({"role": "user", "content": blocks})

    messages = _merge_roles(messages)

    kw = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages or [{"role": "user", "content": "hi"}],
    }
    if system_parts:
        kw["system"] = "\n\n".join(part for part in system_parts if part)
    if "temperature" in body:
        kw["temperature"] = body["temperature"]
    if "top_p" in body:
        kw["top_p"] = body["top_p"]
    if body.get("stop"):
        stop = body["stop"]
        kw["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)

    tools = [] if body.get("tool_choice") == "none" else _convert_tools(body.get("tools"))
    if tools:
        kw["tools"] = tools
        choice = _convert_tool_choice(body.get("tool_choice"))
        if choice:
            kw["tool_choice"] = choice

    if body.get("user"):
        kw["metadata"] = {"user_id": str(body["user"])}

    return kw


_STOP_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def _anthropic_to_openai_response(msg: anthropic.types.Message) -> dict:
    texts = []
    tool_calls = []
    for block in msg.content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            texts.append(getattr(block, "text", ""))
        elif block_type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input or {}, ensure_ascii=False),
                },
            })

    finish_reason = _STOP_REASONS.get(msg.stop_reason, msg.stop_reason or "stop")
    if tool_calls:
        finish_reason = "tool_calls"

    message = {
        "role": "assistant",
        "content": "".join(texts) or None,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": f"chatcmpl-{msg.id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": msg.model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": msg.usage.input_tokens if msg.usage else 0,
            "completion_tokens": msg.usage.output_tokens if msg.usage else 0,
            "total_tokens": (msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0,
        },
    }


# ── Authentication ────────────────────────────────────────────────────────────


def _presented_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-api-key", "").strip()


def _authorized(request: Request) -> bool:
    if ALLOW_ANONYMOUS:
        return True
    if not AUTH_TOKEN:
        return False
    return hmac.compare_digest(_presented_token(request), AUTH_TOKEN)


# ── Streaming helper ──────────────────────────────────────────────────────────

_SKIP_EVENTS: set[bytes] = {b"billing_summary"}


def _filter_sse(buffer: bytes) -> tuple[bytes, bytes]:
    out = b""
    skip_block = False
    while True:
        nl = buffer.find(b"\n")
        if nl == -1:
            break
        line = buffer[: nl + 1]
        buffer = buffer[nl + 1:]
        stripped = line.rstrip(b"\r\n")

        if stripped.startswith(b"event:"):
            event_name = stripped[6:].strip()
            skip_block = event_name in _SKIP_EVENTS
            if skip_block:
                continue
        elif skip_block:
            if stripped == b"":
                skip_block = False
            continue

        out += line
    return out, buffer


def _stream_worker(client: anthropic.Anthropic, kw: dict, loop: asyncio.AbstractEventLoop, q: asyncio.Queue, stop: threading.Event) -> None:
    def _emit(kind: str, payload) -> None:
        loop.call_soon_threadsafe(q.put_nowait, (kind, payload))

    try:
        with client.messages.with_streaming_response.create(**kw) as resp:
            _emit("ready", resp)
            buf = b""
            for raw_chunk in resp.iter_bytes(chunk_size=1024):
                if stop.is_set():
                    break
                buf += raw_chunk
                keep, buf = _filter_sse(buf)
                if keep:
                    _emit("chunk", keep)
            if buf and not stop.is_set():
                _emit("chunk", buf)
    except Exception as exc:
        _emit("error", exc)
    finally:
        _emit("done", None)


async def _stream_gen(q: asyncio.Queue, stop: threading.Event):
    while True:
        try:
            kind, payload = await asyncio.wait_for(q.get(), timeout=CHUNK_TIMEOUT)
        except asyncio.TimeoutError:
            stop.set()
            raise TimeoutError(
                f"No chunk received from agentrouter.org in {CHUNK_TIMEOUT}s — upstream stalled"
            )
        if kind == "ready":
            continue
        if kind == "done":
            break
        if kind == "error":
            if isinstance(payload, anthropic.APIStatusError):
                message = json.dumps(payload.body) if payload.body else str(payload)
            else:
                message = str(payload)
            err = json.dumps({"type": "error", "error": {"type": "api_error", "message": message}})
            yield f"event: error\ndata: {err}\n\n".encode()
            break
        yield payload


async def _openai_stream_gen(client: anthropic.Anthropic, kw: dict):
    cmpl_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    model = kw.get("model", "claude-opus-4-6")

    def _chunk(delta: dict, finish_reason=None) -> bytes:
        payload = {
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    yield _chunk({"role": "assistant"})

    def _stream_call():
        return client.messages.create(**kw, stream=True)

    tool_indices: dict[int, int] = {}
    next_tool_index = 0
    saw_tool = False

    try:
        stream = await asyncio.get_running_loop().run_in_executor(_CALL_EXECUTOR, _stream_call)
        for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                if getattr(block, "type", "") == "tool_use":
                    block_index = getattr(event, "index", -1)
                    tool_indices[block_index] = next_tool_index
                    saw_tool = True
                    yield _chunk({"tool_calls": [{
                        "index": next_tool_index,
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": ""},
                    }]})
                    next_tool_index += 1
            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                delta_type = getattr(delta, "type", "")
                if delta_type == "text_delta":
                    text = getattr(delta, "text", "")
                    if text:
                        yield _chunk({"content": text})
                elif delta_type == "input_json_delta":
                    partial = getattr(delta, "partial_json", "")
                    tool_index = tool_indices.get(getattr(event, "index", -1))
                    if partial and tool_index is not None:
                        yield _chunk({"tool_calls": [{
                            "index": tool_index,
                            "function": {"arguments": partial},
                        }]})
            elif event_type == "message_delta":
                stop_reason = getattr(getattr(event, "delta", None), "stop_reason", None)
                finish_reason = "tool_calls" if saw_tool else _STOP_REASONS.get(stop_reason, "stop")
                yield _chunk({}, finish_reason)
        yield b"data: [DONE]\n\n"
    except Exception as exc:
        err_msg = json.dumps({"error": {"message": str(exc), "type": "proxy_error"}})
        yield f"data: {err_msg}\n\n".encode()


# ── Routes ────────────────────────────────────────────────────────────────────

app = FastAPI(title="agentrouter-opencode-proxy")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
@app.get("/models")
async def models():
    return {
        "object": "list",
        "data": [{"id": model_id, "object": "model"} for model_id in MODEL_IDS],
    }


@app.post("/v1/messages")
@app.post("/messages")
async def messages(request: Request):
    if not _authorized(request):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "type": "authentication_error",
                    "message": "missing or invalid proxy token",
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "invalid_request_error", "message": "request body must be JSON"}},
        )

    kw = _kwargs(body)

    try:
        client = _get_client_for_request(request)
    except Exception as exc:
        return JSONResponse(
            status_code=401,
            content={"error": {"type": "authentication_error", "message": str(exc)}},
        )

    if body.get("stream", False):
        kw["stream"] = True
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()
        _STREAM_EXECUTOR.submit(_stream_worker, client, kw, loop, q, stop)

        if STREAM_ERROR_STATUS:
            try:
                kind, payload = await asyncio.wait_for(q.get(), timeout=CHUNK_TIMEOUT)
            except asyncio.TimeoutError:
                stop.set()
                return JSONResponse(
                    status_code=504,
                    content={"error": {"type": "proxy_timeout", "message": "upstream did not respond in time"}},
                )
            if kind == "error":
                stop.set()
                if isinstance(payload, anthropic.APIStatusError):
                    return Response(
                        content=json.dumps(payload.body) if payload.body else b"",
                        status_code=payload.status_code,
                        media_type="application/json",
                    )
                return JSONResponse(
                    status_code=502,
                    content={"error": {"type": "proxy_error", "message": str(payload)}},
                )

        return StreamingResponse(
            _stream_gen(q, stop),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    def _run():
        return client.messages.create(**kw)

    try:
        msg = await asyncio.get_running_loop().run_in_executor(_CALL_EXECUTOR, _run)
        return Response(content=msg.model_dump_json(), media_type="application/json")
    except anthropic.APIStatusError as e:
        return Response(
            content=json.dumps(e.body) if e.body else b"",
            status_code=e.status_code,
            media_type="application/json",
        )
    except Exception as e:
        return Response(
            content=json.dumps({"error": {"message": str(e), "type": "proxy_error"}}),
            status_code=500,
            media_type="application/json",
        )


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request):
    """OpenAI /v1/chat/completions adapter: translates OpenAI requests to Anthropic shape and back."""
    if not _authorized(request):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "type": "authentication_error",
                    "message": "missing or invalid proxy token",
                }
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "invalid_request_error", "message": "request body must be JSON"}},
        )

    kw = _openai_to_anthropic(body)

    try:
        client = _get_client_for_request(request)
    except Exception as exc:
        return JSONResponse(
            status_code=401,
            content={"error": {"type": "authentication_error", "message": str(exc)}},
        )

    if body.get("stream", False):
        return StreamingResponse(
            _openai_stream_gen(client, kw),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    def _run():
        return client.messages.create(**kw)

    try:
        msg = await asyncio.get_running_loop().run_in_executor(_CALL_EXECUTOR, _run)
        openai_res = _anthropic_to_openai_response(msg)
        return JSONResponse(content=openai_res)
    except anthropic.APIStatusError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"message": str(e.body), "type": "upstream_error"}},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "proxy_error"}},
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"AgentRouter proxy  →  {TARGET}")
    print(f"Listening on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level=_env_str("LOG_LEVEL", "info"))
