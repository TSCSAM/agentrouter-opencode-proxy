<div dir="rtl">

# راهنمای AgentRouter

این راهنما آماده‌سازی حساب **AgentRouter**، گرفتن کلید، انتخاب مدل، و اتصال **۹روتر** به پروکسی را توضیح می‌دهد.

## AgentRouter چیست

یک سرویس واسط که دسترسی به چند مدل زبانی را با یک کلید و یک آدرس پایه فراهم می‌کند. صورتحساب و سهمیه در پنل خود سرویس مدیریت می‌شود.

## ساخت حساب و کلید

1. در سایت AgentRouter ثبت‌نام کنید.
2. وارد بخش **Console → Token** شوید.
3. یک کلید جدید بسازید.
4. کلید را کپی کنید. با `sk-` شروع می‌شود.

کلید را فقط یک‌بار نشان می‌دهند؛ در جای امن نگه دارید.

## آدرس پایه

برای کلاینت‌هایی که خودشان مسیر آنتروپیک را می‌سازند، آدرس پایه ریشه دامنه است:

```
https://agentrouter.org
```

برای کلاینت‌های سازگار با OpenAI، آدرس با `/v1` است:

```
https://agentrouter.org/v1
```

اگر در حالت اول `/v1` اضافه کنید، مسیر به `/v1/v1/messages` تبدیل می‌شود و خطای ۴۰۴ می‌گیرید.

## مدل‌ها

فهرست مدل‌ها در پنل AgentRouter است و ممکن است تغییر کند. مدل‌های رایج:

```
claude-opus-4-6
gpt-4o
gpt-4o-mini
deepseek-chat
```

اگر پاسخ زیر گرفتید، ظرفیت آن مدل در آن لحظه تمام شده است:

```
503 no available channel
```

مدل دیگر را امتحان کنید یا کمی بعد دوباره تلاش کنید.

## فیلتر کلاینت

AgentRouter درخواست‌ها را بر اساس هدر کلاینت بررسی می‌کند. نتیجه تست زنده:

```
opencode/...                       allowed
claude-cli/...                     allowed
Anthropic/Python + x-stainless     allowed
curl / node / axios / ai-sdk       blocked
```

کلاینت‌های مجاز مستقیم وصل می‌شوند. کلاینت‌های عمومی، از جمله ۹روتر، با خطای زیر رد می‌شوند:

```
unauthorized client detected
```

پروکسی این شکاف را پر می‌کند: درخواست را با SDK پایتون آنتروپیک می‌فرستد که هدرهایش مجاز است.

## اتصال ۹روتر

1. در پنل ۹روتر وارد بخش **Providers** شوید.
2. یک provider جدید از نوع **OpenAI Compatible** بسازید.
3. مقادیر زیر را وارد کنید:

```
Base URL   https://<your-app>.up.railway.app/v1
API Key    sk-...
```

4. مدل را اضافه کنید:

```
claude-opus-4-6
```

یا با پیشوند گروه:

```
agentrouter/claude-opus-4-6
```

5. ذخیره کنید و یک درخواست آزمایشی بفرستید.

نکته‌ها:

- ۹روتر به مسیر `/v1/chat/completions` درخواست می‌فرستد؛ پروکسی آن را به `/v1/messages` ترجمه می‌کند.
- کلید را در پنل ۹روتر نگه دارید و روی پروکسی متغیر `AGENTROUTER_API_KEY` را تنظیم نکنید.
- اگر نام مدل پیشوند دارد، پروکسی پیشوند را حذف می‌کند.
- خطاهای upstream به شکل `{"error": {...}}` برمی‌گردند تا در پنل دیده شوند.

## محدودیت ورودی فارسی

فیلتر محتوای AgentRouter متن ورودی فارسی را رد می‌کند:

```json
{
  "error": {
    "code": "content-blocked"
  }
}
```

این رفتار از سمت AgentRouter است، نه پروکسی. راه‌حل: پرسش را انگلیسی بنویسید و در system prompt پاسخ فارسی بخواهید.

```json
{
  "model": "claude-opus-4-6",
  "system": "Always answer in Persian (Farsi).",
  "messages": [
    { "role": "user", "content": "Explain what a reverse proxy is, in three sentences." }
  ]
}
```

مدل پاسخ فارسی می‌دهد و فیلتر فعال نمی‌شود.

## تنظیم کلید روی پروکسی

دو حالت وجود دارد:

**حالت اول، کلید در کلاینت.** هیچ متغیری روی پروکسی تنظیم نمی‌کنید و پروکسی کلید هر درخواست را عبور می‌دهد. این حالت پیشنهادی است.

**حالت دوم، کلید روی سرور.** این متغیرها را تنظیم می‌کنید:

```
AGENTROUTER_API_KEY   sk-...
PROXY_ALLOW_ANONYMOUS false
PROXY_AUTH_TOKEN      یک رمز تصادفی
```

در این حالت کلاینت رمز پروکسی را می‌فرستد، نه کلید AgentRouter را.

## امنیت

- کلید را در مخزن گیت، فایل کامیت‌شده یا تاریخچه قرار ندهید.
- روی دامنه عمومی، حالت اول را با احتیاط استفاده کنید و مصرف را پایش کنید.
- در صورت لو رفتن کلید، همان لحظه در پنل AgentRouter آن را باطل کنید.

## تست سریع

```bash
curl -s https://agentrouter.org/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}'
```

اگر پاسخ JSON با متن گرفتید، کلید و مدل درست هستند.

</div>

---

<div dir="ltr">

# AgentRouter Guide

This guide covers setting up an **AgentRouter** account, issuing a key, choosing a model, and connecting **9Router** to the proxy.

## What AgentRouter is

A gateway service that provides access to several language models behind one key and one base URL. Billing and quota live in its own panel.

## Account and key

1. Sign up on the AgentRouter site.
2. Open **Console → Token**.
3. Create a new key.
4. Copy it. It starts with `sk-`.

The key is shown once; store it somewhere safe.

## Base URL

For clients that build the Anthropic path themselves, the base URL is the bare domain:

```
https://agentrouter.org
```

For OpenAI-compatible clients the base URL carries `/v1`:

```
https://agentrouter.org/v1
```

Adding `/v1` in the first case produces `/v1/v1/messages` and a 404.

## Models

The model list lives in the AgentRouter panel and can change. Common ids:

```
claude-opus-4-6
gpt-4o
gpt-4o-mini
deepseek-chat
```

If you get:

```
503 no available channel
```

the pool for that model is exhausted at that moment. Try another model or retry later.

## Client filter

AgentRouter inspects the client headers. Live test results:

```
opencode/...                       allowed
claude-cli/...                     allowed
Anthropic/Python + x-stainless     allowed
curl / node / axios / ai-sdk       blocked
```

Allowlisted clients connect directly. Generic clients, including 9Router, are rejected with:

```
unauthorized client detected
```

The proxy closes that gap: it re-issues the request with the Python Anthropic SDK, whose headers are allowed.

## Connecting 9Router

1. Open **Providers** in the 9Router panel.
2. Add a new **OpenAI Compatible** provider.
3. Enter:

```
Base URL   https://<your-app>.up.railway.app/v1
API Key    sk-...
```

4. Add a model:

```
claude-opus-4-6
```

Or with a group prefix:

```
agentrouter/claude-opus-4-6
```

5. Save and send a test request.

Notes:

- 9Router calls `/v1/chat/completions`; the proxy translates it to `/v1/messages`.
- Keep the key in 9Router and do not set `AGENTROUTER_API_KEY` on the proxy.
- If the model name has a prefix, the proxy strips it.
- Upstream errors come back as `{"error": {...}}` so the panel can display them.

## Persian input limitation

The AgentRouter content filter rejects Persian input text:

```json
{
  "error": {
    "code": "content-blocked"
  }
}
```

This comes from AgentRouter, not from the proxy. Workaround: write the prompt in English and request a Persian answer in the system prompt.

```json
{
  "model": "claude-opus-4-6",
  "system": "Always answer in Persian (Farsi).",
  "messages": [
    { "role": "user", "content": "Explain what a reverse proxy is, in three sentences." }
  ]
}
```

The model answers in Persian and the filter stays quiet.

## Key placement

Two modes:

**Key on the client.** No variable is set on the proxy; it relays each request's key. This is the recommended mode.

**Key on the server.** Set:

```
AGENTROUTER_API_KEY   sk-...
PROXY_ALLOW_ANONYMOUS false
PROXY_AUTH_TOKEN      a random secret
```

In this mode the client sends the proxy token, not the AgentRouter key.

## Security

- Never put the key in git, a committed file, or history.
- On a public domain, use the first mode carefully and watch usage.
- If the key leaks, revoke it in the AgentRouter panel immediately.

## Quick test

```bash
curl -s https://agentrouter.org/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-..." \
  -d '{"model":"claude-opus-4-6","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}'
```

A JSON answer with text means the key and model are correct.

</div>
