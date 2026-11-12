<div dir="rtl">

# پروکسی AgentRouter

یک واسط سبک با **FastAPI** میان کلاینت‌های هوش مصنوعی و **AgentRouter**. هم پروتکل **Anthropic Messages** را می‌فهمد و هم **OpenAI Chat Completions**، روی **Railway** اجرا می‌شود و می‌تواند کلید AgentRouter را از خود درخواست عبور دهد؛ بنابراین لازم نیست کلید روی سرور ذخیره شود.

```
Client  →  this proxy  →  agentrouter.org
```

ترجمه کامل فراخوانی ابزار و پشتیبانی از تصویر در هر دو مسیر انجام می‌شود.

## راهنماها

هر راهنما دو زبانه است؛ بخش فارسی و بخش انگلیسی.

- [راهنمای OpenCode](docs/opencode.md)
- [راهنمای Claude Code](docs/claude-code.md)
- [راهنمای AgentRouter](docs/agentrouter.md)
- [ابزارها و مهارت‌ها](docs/tools-and-skills.md)

## شروع سریع روی Railway

1. مخزن را در حساب گیت‌هاب خود داشته باشید.
2. در Railway یک **New Project** بسازید و **Deploy from GitHub repo** را بزنید.
3. مخزن را انتخاب کنید. ساخت به‌صورت خودکار انجام می‌شود.
4. در تب **Networking** یک دامنه بسازید.
5. آدرس زیر را باز کنید و پاسخ سلامت را ببینید:

```
https://<your-app>.up.railway.app/health
```

هیچ متغیر محیطی برای حالت پیش‌فرض لازم نیست؛ کلید از سمت کلاینت می‌آید.

## اتصال ۹روتر

در پنل ۹روتر یک provider از نوع **OpenAI Compatible** بسازید:

```
Base URL   https://<your-app>.up.railway.app/v1
API Key    sk-...            (AgentRouter key)
Model      claude-opus-4-6
```

جزئیات کامل در [راهنمای AgentRouter](docs/agentrouter.md) آمده است.

## نقاط انتهایی

| مسیر | پروتکل |
|---|---|
| `GET /health` | بررسی سلامت |
| `GET /v1/models` | فهرست مدل‌ها |
| `POST /v1/messages` | Anthropic |
| `POST /v1/chat/completions` | OpenAI |

</div>

---

<div dir="ltr">

# AgentRouter Proxy

A small **FastAPI** bridge between AI clients and **AgentRouter**. It speaks both **Anthropic Messages** and **OpenAI Chat Completions**, runs on **Railway**, and can relay the AgentRouter key from the incoming request, so nothing has to be stored on the server.

```
Client  →  this proxy  →  agentrouter.org
```

Full tool-calling translation and image support on both routes.

## Guides

Every guide is bilingual: Persian and English sections.

- [OpenCode guide](docs/opencode.md)
- [Claude Code guide](docs/claude-code.md)
- [AgentRouter guide](docs/agentrouter.md)
- [Tools and skills](docs/tools-and-skills.md)

## Quick start on Railway

1. Keep the repository on your GitHub account.
2. In Railway, create a **New Project** and choose **Deploy from GitHub repo**.
3. Select the repository. The build is automatic.
4. Open **Networking** and generate a domain.
5. Check the health endpoint:

```
https://<your-app>.up.railway.app/health
```

No environment variable is needed in the default mode; the key arrives with each request.

## Connect 9Router

Add an **OpenAI Compatible** provider in the 9Router panel:

```
Base URL   https://<your-app>.up.railway.app/v1
API Key    sk-...            (AgentRouter key)
Model      claude-opus-4-6
```

Full details are in the [AgentRouter guide](docs/agentrouter.md).

## Endpoints

| Path | Protocol |
|---|---|
| `GET /health` | health probe |
| `GET /v1/models` | model list |
| `POST /v1/messages` | Anthropic |
| `POST /v1/chat/completions` | OpenAI |

</div>
