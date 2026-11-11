<div dir="rtl">

# راهنمای Claude Code

این راهنما اتصال **Claude Code** به **AgentRouter** را توضیح می‌دهد. دو روش وجود دارد: از طریق پروکسی، یا مستقیم.

## روش پیشنهادی: از طریق پروکسی

### متغیرهای محیطی

```bash
export ANTHROPIC_BASE_URL=https://<your-app>.up.railway.app
export ANTHROPIC_API_KEY=sk-...
```

سپس اجرا:

```bash
claude
```

کلید AgentRouter با هر درخواست به پروکسی می‌رسد و پروکسی آن را به upstream منتقل می‌کند.

### تنظیم دائمی

برای اینکه هر بار متغیرها را تعریف نکنید، فایل `~/.claude/settings.json` را بسازید یا ویرایش کنید:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://<your-app>.up.railway.app",
    "ANTHROPIC_API_KEY": "sk-..."
  }
}
```

### اجرای محلی پروکسی

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:7187
```

### نکته مسیر

کلاد کد خودش مسیر را کامل می‌سازد:

```
/v1/messages
```

پس `ANTHROPIC_BASE_URL` باید فقط ریشه دامنه باشد و `/v1` نداشته باشد.

## روش دوم: اتصال مستقیم

هدر کلاد کد امروز در فهرست مجاز AgentRouter است، بنابراین می‌توانید مستقیم وصل شوید:

```bash
export ANTHROPIC_BASE_URL=https://agentrouter.org
export ANTHROPIC_API_KEY=sk-...
```

محدودیت‌های این حالت:

- فهرست مجاز ممکن است تغییر کند.
- رویدادهای اضافی استریم ممکن است پردازش را مختل کنند.
- بعضی فیلدهای بدنه ممکن است فیلتر محتوای AgentRouter را فعال کنند.

پروکسی این موارد را پوشش می‌دهد و رفتار پایدارتری می‌دهد.

## انتخاب مدل

کلاد کد به‌طور پیش‌فرض نام مدل خودش را می‌فرستد که ممکن است در AgentRouter وجود نداشته باشد و پاسخ زیر را بگیرید:

```
503 no available channel
```

مدل را صریح تعیین کنید:

```bash
claude --model claude-opus-4-6
```

یا در همان فایل تنظیمات:

```json
{
  "env": {
    "ANTHROPIC_MODEL": "claude-opus-4-6"
  }
}
```

## عیب‌یابی

| نشانه | علت | راه‌حل |
|---|---|---|
| `404` یا پاسخ HTML | آدرس پایه اشتباه | در حالت مستقیم ریشه دامنه بدهید، نه `/v1` |
| `unauthorized client detected` | هدر کلاینت مجاز نیست | از پروکسی استفاده کنید |
| `503 no available channel` | مدل در AgentRouter موجود نیست یا ظرفیت ندارد | نام مدل را صریح تعیین کنید |
| `400 content-blocked` | متن ورودی فارسی | پرسش انگلیسی و پاسخ فارسی از طریق system prompt |
| `401` | کلید نامعتبر | کلید را از پنل AgentRouter دوباره بگیرید |

## تست سریع

```bash
claude -p "say hello" --model claude-opus-4-6
```

اگر پاسخ متنی گرفتید، مسیر کامل کار می‌کند.

## تفاوت با اپن‌کد

- کلاد کد از مسیر `/v1/messages` استفاده می‌کند، اپن‌کد از `/messages`.
- کلاد کد نام مدل پیش‌فرض خودش را می‌فرستد، اپن‌کد مدل را از پیکربندی می‌خواند.
- برای همین در کلاد کد تعیین صریح مدل مهم‌تر است.

</div>

---

<div dir="ltr">

# Claude Code Guide

This guide connects **Claude Code** to **AgentRouter**. There are two ways: through the proxy, or directly.

## Recommended: through the proxy

### Environment variables

```bash
export ANTHROPIC_BASE_URL=https://<your-app>.up.railway.app
export ANTHROPIC_API_KEY=sk-...
```

Then run:

```bash
claude
```

The AgentRouter key travels with each request and the proxy forwards it upstream.

### Permanent configuration

To avoid exporting variables every time, create or edit `~/.claude/settings.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://<your-app>.up.railway.app",
    "ANTHROPIC_API_KEY": "sk-..."
  }
}
```

### Run the proxy locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ar_proxy.py
```

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:7187
```

### Path note

Claude Code builds the full path itself:

```
/v1/messages
```

So `ANTHROPIC_BASE_URL` must be the bare domain, with no `/v1`.

## Option two: direct connection

Claude Code's User-Agent is on AgentRouter's allowlist today, so a direct connection works:

```bash
export ANTHROPIC_BASE_URL=https://agentrouter.org
export ANTHROPIC_API_KEY=sk-...
```

Limits of this mode:

- The allowlist may change.
- Extra stream events may disturb processing.
- Some body fields may trigger AgentRouter's content filter.

The proxy covers these and gives more stable behaviour.

## Model selection

By default Claude Code sends its own model name, which may not exist on AgentRouter, producing:

```
503 no available channel
```

Set the model explicitly:

```bash
claude --model claude-opus-4-6
```

Or in the settings file:

```json
{
  "env": {
    "ANTHROPIC_MODEL": "claude-opus-4-6"
  }
}
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `404` or an HTML response | Wrong base URL | In direct mode use the bare domain, not `/v1` |
| `unauthorized client detected` | Client header not allowlisted | Use the proxy |
| `503 no available channel` | Model missing or out of capacity | Set the model name explicitly |
| `400 content-blocked` | Persian input text | English prompt plus a Persian system instruction |
| `401` | Invalid key | Issue a new key in the AgentRouter panel |

## Quick test

```bash
claude -p "say hello" --model claude-opus-4-6
```

A text answer means the whole path works.

## Difference from OpenCode

- Claude Code uses `/v1/messages`; OpenCode uses `/messages`.
- Claude Code sends its own default model name; OpenCode reads the model from its config.
- That makes explicit model selection more important in Claude Code.

</div>
