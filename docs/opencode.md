<div dir="rtl">

# راهنمای OpenCode

این راهنما اتصال **OpenCode** به **AgentRouter** را توضیح می‌دهد. دو روش وجود دارد: از طریق پروکسی، یا مستقیم.

## روش پیشنهادی: از طریق پروکسی

### پیش‌نیازها

- پروکسی روی Railway در حال اجرا باشد.
- کلید AgentRouter از پنل AgentRouter گرفته شده باشد.

### پیکربندی

فایل `~/.config/opencode/opencode.json` را باز کنید:

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

اگر نمی‌خواهید از متغیر محیطی استفاده کنید، مقدار کلید را مستقیم در `apiKey` بگذارید.

### اجرا

```bash
opencode run --model anthropic/claude-opus-4-6 "hello"
```

یا رابط تعاملی را باز کنید و مدل را از فهرست انتخاب کنید.

### اجرای محلی پروکسی

اگر پروکسی را روی همان سیستم اجرا می‌کنید:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

و در پیکربندی:

```json
"baseURL": "http://127.0.0.1:7187"
```

### چرا مسیر بدون v1

اپن‌کد مسیر زیر را صدا می‌زند:

```
/messages
```

پروکسی هر دو مسیر زیر را می‌شناسد:

```
/messages
/v1/messages
```

پس آدرس پایه نباید `/v1` داشته باشد.

## روش دوم: اتصال مستقیم

امروز هدر اپن‌کد در فهرست مجاز AgentRouter است، بنابراین اتصال مستقیم هم می‌تواند عبور کند. اما آدرس پایه باید `/v1` داشته باشد:

```json
{
  "provider": {
    "anthropic": {
      "options": {
        "baseURL": "https://agentrouter.org/v1",
        "apiKey": "{env:AGENTROUTER_API_KEY}"
      }
    }
  }
}
```

بدون `/v1`، درخواست به مسیر اشتباه می‌رود و صفحه HTML برمی‌گردد، نه پاسخ مدل.

سه محدودیت اتصال مستقیم:

- رویداد `billing_summary` که AgentRouter در جریان پاسخ تزریق می‌کند، پارسر اپن‌کد را می‌شکند.
- فیلدهای `thinking` و `output_config` ممکن است فیلتر محتوای AgentRouter را فعال کنند.
- فهرست مجاز کلاینت‌ها ممکن است بدون اطلاع تغییر کند.

پروکسی هر سه مورد را مدیریت می‌کند.

## عیب‌یابی

| نشانه | علت | راه‌حل |
|---|---|---|
| پاسخ HTML یا ۴۰۴ | آدرس پایه اشتباه | در حالت مستقیم `/v1` را اضافه کنید؛ در حالت پروکسی حذف کنید |
| `unauthorized client detected` | هدر کلاینت مجاز نیست | از پروکسی استفاده کنید |
| `400 content-blocked` | متن ورودی فارسی | پرسش را انگلیسی بنویسید و در system prompt پاسخ فارسی بخواهید |
| `503 no available channel` | ظرفیت مدل در AgentRouter | مدل دیگر یا تلاش دوباره |
| قطع شدن استریم | رویدادهای اضافی upstream | از پروکسی استفاده کنید |

## تست سریع

```bash
curl -s https://<your-app>.up.railway.app/health
```

```bash
curl -s https://<your-app>.up.railway.app/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
```

</div>

---

<div dir="ltr">

# OpenCode Guide

This guide connects **OpenCode** to **AgentRouter**. There are two ways: through the proxy, or directly.

## Recommended: through the proxy

### Prerequisites

- The proxy is running on Railway.
- You have an AgentRouter key from the AgentRouter panel.

### Configuration

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

If you prefer not to use an environment variable, put the key directly in `apiKey`.

### Run

```bash
opencode run --model anthropic/claude-opus-4-6 "hello"
```

Or open the interactive interface and pick the model from the list.

### Run the proxy locally

If the proxy runs on the same machine:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

Then in the config:

```json
"baseURL": "http://127.0.0.1:7187"
```

### Why no /v1

OpenCode calls:

```
/messages
```

The proxy serves both:

```
/messages
/v1/messages
```

So the base URL must not carry `/v1`.

## Option two: direct connection

OpenCode's User-Agent is on AgentRouter's allowlist today, so a direct connection can pass. The base URL must include `/v1`:

```json
{
  "provider": {
    "anthropic": {
      "options": {
        "baseURL": "https://agentrouter.org/v1",
        "apiKey": "{env:AGENTROUTER_API_KEY}"
      }
    }
  }
}
```

Without `/v1`, the request hits the wrong path and returns an HTML page instead of a model answer.

Three limits of the direct mode:

- The `billing_summary` event injected by AgentRouter breaks OpenCode's stream parser.
- The `thinking` and `output_config` fields may trigger AgentRouter's content filter.
- The client allowlist can change without notice.

The proxy handles all three.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HTML response or 404 | Wrong base URL | Add `/v1` in direct mode; remove it in proxy mode |
| `unauthorized client detected` | Client header not allowlisted | Use the proxy |
| `400 content-blocked` | Persian input text | Send an English prompt and ask for a Persian answer in the system prompt |
| `503 no available channel` | Model capacity upstream | Try another model or retry |
| Stream breaks | Extra upstream events | Use the proxy |

## Quick test

```bash
curl -s https://<your-app>.up.railway.app/health
```

```bash
curl -s https://<your-app>.up.railway.app/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
```

</div>
