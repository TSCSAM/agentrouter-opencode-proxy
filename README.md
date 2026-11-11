<div dir="rtl">

# پروکسی AgentRouter برای OpenCode و ۹روتر

یک پروکسی سبک و خودمیزبان با **FastAPI** که هم به زبان **Anthropic Messages** و هم به زبان **OpenAI Chat Completions** پاسخ می‌دهد و درخواست‌ها را به [AgentRouter](https://agentrouter.org) می‌فرستد.

با این پروکسی می‌توانید **OpenCode**، پنل **۹روتر** و هر کلاینت سازگار با OpenAI یا Anthropic را به AgentRouter وصل کنید، روی **Railway** اجرا کنید و کلید AgentRouter را در همان کلاینت نگه دارید؛ پروکسی می‌تواند کلید را از خود درخواست بردارد و هیچ کلیدی روی سرور ذخیره نشود.

---

## این پروژه چیست؟

AgentRouter سرویس واسطی است که دسترسی به مدل‌هایی مثل `claude-opus-4-6`، `gpt-4o`، `deepseek-chat` و چند مدل دیگر را فراهم می‌کند. اما درگاه آن پشت فایروال برنامه‌ای (WAF) آلی‌بابا قرار دارد و فقط کلاینت‌های مشخصی را می‌پذیرد. نتیجه این است که ابزارهای Node.js مثل OpenCode و پنل‌هایی مثل ۹روتر با خطای زیر رد می‌شوند:

```
unauthorized client detected, contact support
```

این پروکسی بین کلاینت شما و AgentRouter می‌نشیند:

- درخواست را با فرمت Anthropic یا OpenAI می‌گیرد.
- آن را با **SDK پایتون anthropic** (که همان اثر انگشت مجاز را دارد) به `https://agentrouter.org/v1/messages` می‌فرستد.
- پاسخ یا جریان SSE را دوباره به فرمت کلاینت برمی‌گرداند.

---

## چرا پروکسی لازم است؟ (نتیجه آزمایش زنده)

فیلتر AgentRouter بر اساس **هدرهای درخواست** تصمیم می‌گیرد، نه بر اساس TLS. آزمایش زنده روی سرویس اصلی نشان داد:

- درخواستی که هدرهای `User-Agent: Anthropic/Python ...` و `x-stainless-lang: python` را داشته باشد، از فیلتر عبور می‌کند.
- همین هدرها با `httpx` نسخه ۰.x و `httpx2` نسخه ۲.x، هر دو، پذیرفته می‌شوند.
- `curl`، `fetch` در Node.js و SDKهای غیرپایتونی رد می‌شوند.
- SDK پایتونی **async** هم رد می‌شود؛ چون هدر آن `AsyncAnthropic/Python ...` است.

به همین دلیل این پروکسی از SDK **sync** پایتون استفاده می‌کند و فراخوانی‌ها را در thread pool اجرا می‌کند تا event loop بلاک نشود.

---

## معماری

```
┌──────────────────────────────────────────────┐
│ Client                                       │
│   OpenCode / 9Router / Cline / curl / ...    │
│   Anthropic JSON  or  OpenAI JSON            │
└──────────────────────┬───────────────────────┘
                       │  HTTPS
                       ▼
┌──────────────────────────────────────────────┐
│ This proxy (FastAPI + uvicorn)               │
│   /v1/messages          /v1/chat/completions │
│   translation layer                          │
└──────────────────────┬───────────────────────┘
                       │  anthropic (sync SDK)
                       │  UA: Anthropic/Python ...
                       ▼
┌──────────────────────────────────────────────┐
│ https://agentrouter.org  (Aliyun WAF)        │
└──────────────────────────────────────────────┘
```

---

## چه کارهایی انجام می‌دهد؟

| قابلیت | توضیح |
|---|---|
| ترجمه OpenAI ↔ Anthropic | بدنه `chat/completions` را به `messages` تبدیل می‌کند و پاسخ را برمی‌گرداند |
| استریم سازگار با OpenAI | رویدادهای SSE آنتروپیک را به `chat.completion.chunk` و در پایان `data: [DONE]` تبدیل می‌کند |
| عبور کلید (Key Relay) | اگر `AGENTROUTER_API_KEY` تنظیم نشده باشد، کلید از هدر `Authorization` یا `x-api-key` درخواست خوانده می‌شود |
| حذف پیشوند مدل | نام‌هایی مثل `agentrouter/gpt-4o` یا `new-provider/claude-opus-4-6` به `gpt-4o` و `claude-opus-4-6` تبدیل می‌شوند |
| فیلتر رویدادهای اضافی | رویداد `billing_summary` که پارسر کلاینت‌ها را می‌شکند حذف می‌شود |
| حذف فیلدهای مشکل‌ساز | `thinking` و `output_config` از بدنه حذف می‌شوند |
| فهرست مدل محلی | `GET /v1/models` بدون تماس با upstream پاسخ می‌دهد |
| Health Check | `GET /health` برای بررسی سلامت سرویس روی Railway |

---

## نقاط انتهایی (Endpoints)

| متد | مسیر | کاربرد |
|---|---|---|
| `GET` | `/health` | بررسی سلامت؛ بدون تماس با upstream |
| `GET` | `/v1/models` و `/models` | فهرست مدل‌ها به فرمت OpenAI |
| `POST` | `/v1/messages` و `/messages` | Anthropic Messages API (با پشتیبانی از `stream`) |
| `POST` | `/v1/chat/completions` و `/chat/completions` | OpenAI Chat Completions API (با پشتیبانی از `stream`) |

---

## متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `AGENTROUTER_TARGET` | `https://agentrouter.org` | آدرس upstream؛ بدون `/v1` |
| `HOST` | `0.0.0.0` | آدرس bind |
| `PORT` | `7187` | پورت listen؛ Railway خودش مقدار می‌دهد |
| `AGENTROUTER_API_KEY` | خالی | اگر خالی باشد، کلید از هدر درخواست خوانده می‌شود |
| `PROXY_AUTH_TOKEN` | خالی | توکن اختصاصی پروکسی (وقتی حالت relay را غیرفعال می‌کنید) |
| `PROXY_ALLOW_ANONYMOUS` | `true` | اجازه عبور بدون توکن پروکسی |
| `PROXY_MODEL_IDS` | `claude-opus-4-6,gpt-4o,gpt-4o-mini,deepseek-chat` | فهرست مدل‌ها برای `/v1/models` |
| `PROXY_CONNECT_TIMEOUT` | `10` | تایم‌اوت اتصال (ثانیه) |
| `PROXY_READ_TIMEOUT` | `120` | تایم‌اوت خواندن (ثانیه) |
| `PROXY_WRITE_TIMEOUT` | `30` | تایم‌اوت نوشتن (ثانیه) |
| `PROXY_CHUNK_TIMEOUT` | `120` | حداکثر فاصله بین دو chunk استریم |
| `PROXY_CALL_WORKERS` | `16` | تعداد thread برای درخواست‌های غیراستریم |
| `PROXY_STREAM_WORKERS` | `32` | تعداد thread برای درخواست‌های استریم |
| `PROXY_STREAM_ERROR_STATUS` | `false` | برگرداندن کد خطای واقعی upstream در حالت استریم |
| `LOG_LEVEL` | `info` | سطح لاگ uvicorn |

همچنین اگر فایل `~/.config/opencode/api_keys/AGENT_ROUTER_API_KEY` وجود داشته باشد و متغیر محیطی خالی باشد، کلید از همان فایل خوانده می‌شود.

---

## استقرار روی Railway

### گام ۱ — مخزن را روی گیت‌هاب داشته باشید

این مخزن را در حساب خودتان نگه دارید. Railway از همان مخزن می‌سازد و با هر push دوباره دیپلوی می‌کند.

### گام ۲ — پروژه بسازید

در [railway.app](https://railway.app) وارد شوید:

1. **New Project**
2. **Deploy from GitHub repo**
3. مخزن `agentrouter-opencode-proxy` را انتخاب کنید

### گام ۳ — تنظیمات ساخت

هیچ تنظیم دستی لازم نیست. فایل‌های همراه مخزن کار را انجام می‌دهند:

| فایل | نقش |
|---|---|
| `requirements.txt` | نصب وابستگی‌ها؛ Nixpacks آن را ترجیح می‌دهد |
| `.python-version` | پایتون ۳.۱۲ |
| `railway.json` | دستور شروع، مسیر healthcheck و سیاست restart |
| `Procfile` | دستور شروع جایگزین |
| `ar_proxy.py` | نقطه ورود سازگار برای دستورهای شروع قدیمی |

دستور شروع برابر است با:

```
uvicorn proxy:app --host 0.0.0.0 --port $PORT --log-level info --timeout-keep-alive 30
```

> اگر مخزن گیت‌هاب را از نو ساخته‌اید، در Railway به **Settings → Source** بروید و مخزن جدید را دوباره وصل کنید؛ چون شناسه مخزن عوض شده است.

### گام ۴ — متغیرها

برای حالت پیش‌فرض (کلید در کلاینت) **هیچ متغیری لازم نیست**. اگر می‌خواهید کلید روی سرور باشد:

| متغیر | مقدار |
|---|---|
| `AGENTROUTER_API_KEY` | `sk-...` |
| `PROXY_ALLOW_ANONYMOUS` | `false` |
| `PROXY_AUTH_TOKEN` | یک رمز تصادفی قوی |

### گام ۵ — دامنه

در تب **Networking** روی **Generate Domain** بزنید. آدرسی مثل `https://<your-app>.up.railway.app` دریافت می‌کنید.

### گام ۶ — تأیید

در **Deployments → Logs** باید این خط را ببینید:

```
Uvicorn running on http://0.0.0.0:8080
```

سپس:

```bash
curl -s https://<your-app>.up.railway.app/health
# {"status":"ok"}
```

---

## اتصال به ۹روتر

1. در پنل ۹روتر وارد بخش **Providers** شوید و یک provider جدید از نوع **OpenAI Compatible** بسازید.
2. مقدار **Base URL** را برابر دامنه Railway به‌همراه `/v1` بگذارید:

```
https://<your-app>.up.railway.app/v1
```

3. مقدار **API Key** را همان کلید AgentRouter بگذارید:

```
sk-...
```

4. مدل‌ها را اضافه کنید. هر دو شکل نام مدل پذیرفته می‌شود:

```
claude-opus-4-6
agentrouter/claude-opus-4-6
```

5. ذخیره کنید و یک درخواست آزمایشی بفرستید.

نکته‌های مهم:

- ۹روتر به `/v1/chat/completions` درخواست می‌فرستد؛ پروکسی آن را به `/v1/messages` ترجمه می‌کند.
- کلید را در پنل ۹روتر نگه دارید و روی پروکسی `AGENTROUTER_API_KEY` را تنظیم **نکنید**؛ در این حالت پروکسی کلید هر درخواست را عبور می‌دهد.
- اگر در ۹روتر نام مدل را با پیشوند گروه می‌نویسید (مثل `agentrouter/...`)، پروکسی پیشوند را حذف می‌کند و نام واقعی را به AgentRouter می‌فرستد.
- در خطاهای سمت upstream، بدنه خطای AgentRouter به شکل `{"error": {...}}` برگردانده می‌شود تا در پنل ۹روتر دیده شود.

---

## پیکربندی OpenCode

فایل `~/.config/opencode/opencode.json` را باز کنید و provider را به پروکسی وصل کنید:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "anthropic": {
      "options": {
        "baseURL": "https://<your-app>.up.railway.app",
        "apiKey": "{env:AGENTROUTER_API_KEY}"
      },
      "models": {
        "claude-opus-4-6": {
          "name": "Claude Opus 4.6 (AgentRouter)"
        }
      }
    }
  },
  "model": "anthropic/claude-opus-4-6"
}
```

سپس کلید را در محیط تعریف کنید:

```bash
export AGENTROUTER_API_KEY=sk-...
```

یا به‌جای `{env:AGENTROUTER_API_KEY}` مستقیم مقدار کلید را در فایل بگذارید.

نکته‌ها:

- آدرس `baseURL` را **بدون** `/v1` بگذارید. OpenCode خودش مسیر `/messages` را می‌سازد و پروکسی هر دو مسیر `/messages` و `/v1/messages` را پشتیبانی می‌کند. اگر بعد از تنظیم، خطای ۴۰۴ گرفتید، یک‌بار `baseURL` را با `/v1` امتحان کنید.
- اگر OpenCode را روی همان ماشینی اجرا می‌کنید که پروکسی روی آن است، می‌توانید `baseURL` را `http://127.0.0.1:7187` بگذارید.
- برای اجرای محلی پروکسی:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

---

## آماده‌سازی AgentRouter

1. در [agentrouter.org](https://agentrouter.org) ثبت‌نام کنید.
2. وارد بخش **Console → Token** شوید و یک کلید بسازید. کلید با `sk-` شروع می‌شود.
3. مدل موردنظر را انتخاب کنید. در زمان نگارش این مستند، `claude-opus-4-6` پایدارترین گزینه بود.
4. موجودی و سهمیه حساب را بررسی کنید.
5. کلید را در ۹روتر یا OpenCode قرار دهید — نه در مخزن گیت‌هاب.

آدرس پایه برای SDK و کلاینت‌ها باید ریشه دامنه باشد:

```
https://agentrouter.org
```

اگر `/v1` اضافه کنید، SDK مسیر `/v1/v1/messages` را می‌سازد و خطای ۴۰۴ می‌گیرید.

مدل‌های نمونه:

```
claude-opus-4-6
gpt-4o
gpt-4o-mini
deepseek-chat
```

اگر پاسخ `503 no available channel` گرفتید، یعنی ظرفیت آن مدل در استخر AgentRouter تمام شده است؛ مدل دیگری را امتحان کنید یا کمی بعد دوباره تلاش کنید.

---

## تست سریع

```bash
# سلامت سرویس
curl -s https://<your-app>.up.railway.app/health

# فهرست مدل‌ها
curl -s https://<your-app>.up.railway.app/v1/models

# مسیر OpenAI
curl -s https://<your-app>.up.railway.app/v1/chat/completions \
  -H "content-type: application/json" \
  -H "authorization: Bearer sk-..." \
  -d '{"model":"claude-opus-4-6","messages":[{"role":"user","content":"say hello"}],"max_tokens":50}'

# مسیر Anthropic
curl -s https://<your-app>.up.railway.app/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":50,"messages":[{"role":"user","content":"say hello"}]}'
```

---

## عیب‌یابی

| نشانه | علت | راه‌حل |
|---|---|---|
| `404 Not Found` روی `/chat/completions` | درخواست به مسیر دیگری رفته یا نسخه قدیمی پروکسی اجراست | مسیر کامل `/v1/chat/completions` را صدا بزنید و آخرین نسخه را دیپلوی کنید |
| `unauthorized client detected` | درخواست از پروکسی عبور نکرده | مطمئن شوید کلاینت به دامنه Railway یا `127.0.0.1:7187` وصل است، نه به `agentrouter.org` |
| `401 authentication_error` | کلید ارسال نشده یا خالی است | هدر `Authorization: Bearer sk-...` یا `x-api-key` را بفرستید |
| `503 no available channel` | ظرفیت مدل در AgentRouter | مدل دیگر یا تلاش دوباره |
| `400 content-blocked` | فیلتر محتوای AgentRouter روی متن ورودی | بخش «محدودیت شناخته‌شده» را ببینید |
| `Invalid http_client argument` | نسخه ناسازگار anthropic/httpx | `requirements.txt` این مخزن را نصب کنید |
| `can't open file '/app/ar_proxy.py'` | دستور شروع به فایل موجود اشاره نمی‌کند | `railway.json` و `ar_proxy.py` را در مخزن نگه دارید |
| سرویس بالا می‌آید ولی دامنه ۵۰۲ می‌دهد | bind روی `127.0.0.1` | دستور شروع را `--host 0.0.0.0` بدهید |

---

## محدودیت شناخته‌شده: ورودی فارسی

فیلتر محتوای AgentRouter روی **متن ورودی** حساس است. اگر متن پیام کاربر با خط فارسی نوشته شده باشد، درگاه AgentRouter پیش از رسیدن درخواست به مدل، آن را با این پاسخ رد می‌کند:

```json
{
  "type": "agent_router_api_error",
  "error": {
    "type": "agent_router_api_error",
    "code": "content-blocked",
    "message": "..."
  }
}
```

این رفتار از سمت **AgentRouter** است، نه از پروکسی و نه از انکودینگ. آزمایش‌ها نشان داد:

- برای همه مدل‌ها یکسان است.
- با UTF-8 خام و با `\u06xx` فرار داده‌شده هر دو رخ می‌دهد.
- کلمات کوتاه مثل «سلام» عبور می‌کنند، اما جمله‌هایی مثل «سلام چطوری» رد می‌شوند.
- پرسش انگلیسی که از مدل می‌خواهد فارسی جواب بدهد، عبور می‌کند.

راه‌حل پیشنهادی: متن پرسش را انگلیسی بنویسید و در system prompt بخواهید پاسخ فارسی باشد:

```json
{
  "model": "claude-opus-4-6",
  "system": "Always answer in Persian (Farsi).",
  "messages": [
    { "role": "user", "content": "Explain what a reverse proxy is, in three sentences." }
  ]
}
```

مدل پاسخ را فارسی می‌دهد و فیلتر هم فعال نمی‌شود.

---

## نکات امنیتی

- اگر دامنه Railway عمومی است، حتماً کلید را در سمت کلاینت نگه دارید یا `PROXY_AUTH_TOKEN` را فعال کنید.
- هیچ کلیدی را در مخزن، فایل `.env` کامیت‌شده یا تاریخچه گیت قرار ندهید.
- در حالت پیش‌فرض، پروکسی کلید را ذخیره نمی‌کند و فقط آن را عبور می‌دهد.
- برای محدودکردن مصرف، فهرست مدل‌ها را با `PROXY_MODEL_IDS` تنظیم کنید.

</div>

---

<div dir="ltr">

# AgentRouter Proxy for OpenCode & 9Router

A small, self-hosted **FastAPI** proxy that speaks both the **Anthropic Messages API** and the **OpenAI Chat Completions API** and forwards every request to [AgentRouter](https://agentrouter.org).

Use it to connect **OpenCode**, the **9Router** panel, or any OpenAI/Anthropic-compatible client to AgentRouter, host it on **Railway**, and keep the AgentRouter key inside the client — the proxy can relay the key from the incoming request, so nothing has to be stored on the server.

---

## What this project is

AgentRouter provides access to models such as `claude-opus-4-6`, `gpt-4o`, `deepseek-chat` and others. Its gateway sits behind an Aliyun WAF that only accepts a specific set of clients. Node.js tools such as OpenCode and panels such as 9Router are rejected with:

```
unauthorized client detected, contact support
```

This proxy sits between the client and AgentRouter:

- It accepts Anthropic-shaped or OpenAI-shaped requests.
- It re-issues them with the **Python `anthropic` SDK**, which carries the accepted client fingerprint, to `https://agentrouter.org/v1/messages`.
- It translates the response — or the SSE stream — back into the client's format.

---

## Why the proxy is required (live verification)

The AgentRouter filter decides based on **request headers**, not on the TLS handshake. Testing against the live endpoint showed:

- A request carrying `User-Agent: Anthropic/Python ...` together with `x-stainless-lang: python` is accepted.
- The same header set passes over `httpx` 0.x and `httpx2` 2.x.
- `curl`, Node.js `fetch` and non-Python SDKs are rejected.
- The **async** Python SDK is rejected as well, because it advertises `AsyncAnthropic/Python ...`.

That is why this proxy uses the **sync** Python SDK and runs calls inside a thread pool, keeping the event loop free.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│ Client                                       │
│   OpenCode / 9Router / Cline / curl / ...    │
│   Anthropic JSON  or  OpenAI JSON            │
└──────────────────────┬───────────────────────┘
                       │  HTTPS
                       ▼
┌──────────────────────────────────────────────┐
│ This proxy (FastAPI + uvicorn)               │
│   /v1/messages          /v1/chat/completions │
│   translation layer                          │
└──────────────────────┬───────────────────────┘
                       │  anthropic (sync SDK)
                       │  UA: Anthropic/Python ...
                       ▼
┌──────────────────────────────────────────────┐
│ https://agentrouter.org  (Aliyun WAF)        │
└──────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| OpenAI ↔ Anthropic translation | Converts `chat/completions` bodies into `messages` and maps the answer back |
| OpenAI-compatible streaming | Turns Anthropic SSE events into `chat.completion.chunk` frames and a final `data: [DONE]` |
| Key relay | When `AGENTROUTER_API_KEY` is unset, the key is read from the request's `Authorization` or `x-api-key` header |
| Model prefix stripping | `agentrouter/gpt-4o` or `new-provider/claude-opus-4-6` become `gpt-4o` and `claude-opus-4-6` |
| SSE filtering | Drops the `billing_summary` event that breaks client parsers |
| Field filtering | Removes `thinking` and `output_config` from the request body |
| Local model list | `GET /v1/models` answers without touching the upstream |
| Health check | `GET /health` for the Railway probe |

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe, never calls upstream |
| `GET` | `/v1/models`, `/models` | Model list in OpenAI format |
| `POST` | `/v1/messages`, `/messages` | Anthropic Messages API, supports `stream` |
| `POST` | `/v1/chat/completions`, `/chat/completions` | OpenAI Chat Completions API, supports `stream` |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `AGENTROUTER_TARGET` | `https://agentrouter.org` | Upstream base URL, no `/v1` suffix |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `7187` | Listen port, Railway injects its own |
| `AGENTROUTER_API_KEY` | empty | If empty, the key is relayed from the request |
| `PROXY_AUTH_TOKEN` | empty | Proxy-specific token when relay mode is disabled |
| `PROXY_ALLOW_ANONYMOUS` | `true` | Allow requests without a proxy token |
| `PROXY_MODEL_IDS` | `claude-opus-4-6,gpt-4o,gpt-4o-mini,deepseek-chat` | Model ids returned by `/v1/models` |
| `PROXY_CONNECT_TIMEOUT` | `10` | Upstream connect timeout, seconds |
| `PROXY_READ_TIMEOUT` | `120` | Upstream read timeout, seconds |
| `PROXY_WRITE_TIMEOUT` | `30` | Upstream write timeout, seconds |
| `PROXY_CHUNK_TIMEOUT` | `120` | Maximum gap between two stream chunks |
| `PROXY_CALL_WORKERS` | `16` | Threads for non-streaming calls |
| `PROXY_STREAM_WORKERS` | `32` | Threads for streaming calls |
| `PROXY_STREAM_ERROR_STATUS` | `false` | Return the real upstream status on stream failures |
| `LOG_LEVEL` | `info` | uvicorn log level |

If `~/.config/opencode/api_keys/AGENT_ROUTER_API_KEY` exists and the environment variable is empty, the key is read from that file.

---

## Deploy on Railway

### Step 1 — Keep the repository on GitHub

Railway builds from the repository and redeploys on every push.

### Step 2 — Create the project

1. Open [railway.app](https://railway.app)
2. **New Project**
3. **Deploy from GitHub repo**
4. Select `agentrouter-opencode-proxy`

### Step 3 — Build settings

No manual configuration is needed:

| File | Purpose |
|---|---|
| `requirements.txt` | Dependencies; the Nixpacks Python provider prefers it |
| `.python-version` | Pins Python 3.12 |
| `railway.json` | Start command, healthcheck path, restart policy |
| `Procfile` | Fallback start command |
| `ar_proxy.py` | Compatibility entrypoint for older start commands |

The start command is:

```
uvicorn proxy:app --host 0.0.0.0 --port $PORT --log-level info --timeout-keep-alive 30
```

> If you recreated the GitHub repository, reconnect it under **Settings → Source** in Railway; the repository id has changed.

### Step 4 — Variables

The default relay mode needs **no variables**. To keep the key on the server instead:

| Variable | Value |
|---|---|
| `AGENTROUTER_API_KEY` | `sk-...` |
| `PROXY_ALLOW_ANONYMOUS` | `false` |
| `PROXY_AUTH_TOKEN` | a strong random secret |

### Step 5 — Domain

Open **Networking** and click **Generate Domain**. You get `https://<your-app>.up.railway.app`.

### Step 6 — Verify

In **Deployments → Logs** you should see:

```
Uvicorn running on http://0.0.0.0:8080
```

Then:

```bash
curl -s https://<your-app>.up.railway.app/health
# {"status":"ok"}
```

---

## Connect to 9Router

1. Open **Providers** in the 9Router panel and add an **OpenAI Compatible** provider.
2. Set **Base URL** to the Railway domain plus `/v1`:

```
https://<your-app>.up.railway.app/v1
```

3. Set **API Key** to your AgentRouter key:

```
sk-...
```

4. Add models. Both forms are accepted:

```
claude-opus-4-6
agentrouter/claude-opus-4-6
```

5. Save and send a test request.

Notes:

- 9Router calls `/v1/chat/completions`; the proxy translates it to `/v1/messages`.
- Keep the key in 9Router and do **not** set `AGENTROUTER_API_KEY` on the proxy; the proxy then relays each request's key untouched.
- If you use a provider/group prefix in the model name, the proxy strips it before calling AgentRouter.
- Upstream errors are returned as `{"error": {...}}` so they show up in the 9Router panel.

---

## OpenCode configuration

Edit `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "anthropic": {
      "options": {
        "baseURL": "https://<your-app>.up.railway.app",
        "apiKey": "{env:AGENTROUTER_API_KEY}"
      },
      "models": {
        "claude-opus-4-6": {
          "name": "Claude Opus 4.6 (AgentRouter)"
        }
      }
    }
  },
  "model": "anthropic/claude-opus-4-6"
}
```

Then export the key:

```bash
export AGENTROUTER_API_KEY=sk-...
```

Alternatively, put the key directly in the config file instead of `{env:AGENTROUTER_API_KEY}`.

Notes:

- Set `baseURL` **without** `/v1`. OpenCode appends `/messages`, and the proxy serves both `/messages` and `/v1/messages`. If you still get a 404, try `baseURL` with `/v1` once.
- If OpenCode runs on the same machine as the proxy, use `http://127.0.0.1:7187`.
- To run the proxy locally:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

---

## AgentRouter setup

1. Sign up at [agentrouter.org](https://agentrouter.org).
2. Open **Console → Token** and create a key. It starts with `sk-`.
3. Pick a model. At the time of writing, `claude-opus-4-6` had the most stable capacity.
4. Check your balance and quota.
5. Put the key in 9Router or OpenCode — never in the GitHub repository.

The base URL for SDKs and clients must be the bare domain:

```
https://agentrouter.org
```

Adding `/v1` makes the SDK request `/v1/v1/messages` and return 404.

Example models:

```
claude-opus-4-6
gpt-4o
gpt-4o-mini
deepseek-chat
```

A `503 no available channel` answer means the model pool is exhausted upstream; try another model or retry later.

---

## Quick tests

```bash
# health
curl -s https://<your-app>.up.railway.app/health

# models
curl -s https://<your-app>.up.railway.app/v1/models

# OpenAI route
curl -s https://<your-app>.up.railway.app/v1/chat/completions \
  -H "content-type: application/json" \
  -H "authorization: Bearer sk-..." \
  -d '{"model":"claude-opus-4-6","messages":[{"role":"user","content":"say hello"}],"max_tokens":50}'

# Anthropic route
curl -s https://<your-app>.up.railway.app/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":50,"messages":[{"role":"user","content":"say hello"}]}'
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `404 Not Found` on `/chat/completions` | Wrong path or an older proxy build | Use `/v1/chat/completions` and deploy the latest source |
| `unauthorized client detected` | The request bypassed the proxy | Point the client at the Railway domain or `127.0.0.1:7187`, not at `agentrouter.org` |
| `401 authentication_error` | Missing or empty key | Send `Authorization: Bearer sk-...` or `x-api-key` |
| `503 no available channel` | Upstream capacity | Try another model or retry |
| `400 content-blocked` | AgentRouter content filter | See the known limitation below |
| `Invalid http_client argument` | Incompatible anthropic/httpx pair | Install this repository's `requirements.txt` |
| `can't open file '/app/ar_proxy.py'` | Start command points at a missing file | Keep `railway.json` and `ar_proxy.py` in the repository |
| Service runs but the domain returns 502 | Bound to `127.0.0.1` | Start with `--host 0.0.0.0` |

---

## Known limitation: Persian input

The AgentRouter content filter inspects the **incoming text**. When the user message is written in Persian script, the gateway rejects it before it reaches the model:

```json
{
  "type": "agent_router_api_error",
  "error": {
    "type": "agent_router_api_error",
    "code": "content-blocked",
    "message": "..."
  }
}
```

This comes from **AgentRouter**, not from the proxy and not from encoding. Testing showed:

- It happens for every model.
- It happens with raw UTF-8 and with `\u06xx` escaped JSON.
- Short words such as «سلام» pass, but sentences such as «سلام چطوری» are blocked.
- An English prompt that asks the model to answer in Persian passes.

Recommended workaround: send the prompt in English and request Persian output in the system prompt:

```json
{
  "model": "claude-opus-4-6",
  "system": "Always answer in Persian (Farsi).",
  "messages": [
    { "role": "user", "content": "Explain what a reverse proxy is, in three sentences." }
  ]
}
```

The model still answers in Persian, and the filter stays quiet.

---

## Security notes

- On a public Railway URL, keep the key on the client side or enable `PROXY_AUTH_TOKEN`.
- Never commit a key to the repository, to a committed `.env`, or to git history.
- By default the proxy does not store the key; it only relays it.
- Limit spending by setting `PROXY_MODEL_IDS`.

</div>
