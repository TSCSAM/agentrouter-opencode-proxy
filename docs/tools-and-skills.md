<div dir="rtl">

# ابزارها و مهارت‌ها

این سند توضیح می‌دهد مدل چگونه از ابزارها و مهارت‌ها استفاده می‌کند، پروکسی در این مسیر چه کاری انجام می‌دهد و چه کاری انجام نمی‌دهد.

## قاعده اصلی

پروکسی فقط **حمل و ترجمه** می‌کند. اجرای ابزار روی **کلاینت** انجام می‌شود.

```
کلاینت (Hbox / Claude Code / OpenCode)
   │  پیام‌ها + تعریف ابزارها
   ▼
پروکسی روی Railway
   │  ترجمه به /v1/responses
   ▼
مدل AgentRouter  →  درخواست فراخوانی ابزار
   ▲
   └── پروکسی پاسخ را برمی‌گرداند
         ▼
کلاینت ابزار را روی ویندوز اجرا می‌کند
```

مدل هیچ‌وقت خودش فایل را باز نمی‌کند، برنامه اجرا نمی‌کند یا کلیک نمی‌کند. مدل فقط می‌گوید «این ابزار را با این آرگومان‌ها صدا بزن». کلاینت آن را اجرا می‌کند و نتیجه را برمی‌گرداند.

## چرا اجرا روی سرور نیست؟

پروکسی روی Railway در یک کانتینر لینوکسی اجرا می‌شود، نه روی کامپیوتر شما. اگر پروکسی خودش ابزار را اجرا می‌کرد:

- برنامه‌ای روی ویندوز شما باز نمی‌شد؛ روی سرور باز می‌شد.
- فایل‌های شما در دسترس نبودند.
- هر درخواست به یک پوسته اجرای کد از راه دور تبدیل می‌شد؛ یک حفره امنیتی جدی.

به همین دلیل اجرای ابزار در سمت کلاینت است. Hbox روی ویندوز شما اجرا می‌شود و همان ابزارهایی را دارد که خودش می‌تواند اجرا کند.

## چه چیزهایی پشتیبانی می‌شود؟

- تعریف ابزار با هر دو قالب OpenAI (`function.parameters`) و Anthropic (`input_schema`)
- نتیجه ابزار، شامل متن و تصویر
- فراخوانی ابزار در حالت استریم
- تصویر در پیام کاربر و در نتیجه ابزار
- ابزار مهارت (Skill) با فهرست کامل نام‌ها و توضیحات
- ابزارهای ویندوز: پوسته و PowerShell، خواندن و نوشتن فایل، جست‌وجوی فایل، باز کردن برنامه، اسکرین‌شات، کلیپ‌بورد، کنترل ماوس و کیبورد
- ابزارهای سند: Word، Excel، PowerPoint و PDF
- ابزارهای مرورگر، جست‌وجوی وب، فهرست کارها و زیرعامل‌ها

هیچ فهرست ثابتی در پروکسی نیست. هر ابزاری که کلاینت بفرستد، همان‌طور به مدل می‌رسد و پاسخش برمی‌گردد. به همین دلیل افزودن یک مهارت جدید در Hbox نیازی به تغییر پروکسی ندارد.

## مسیر درخواست‌ها

| ورودی کلاینت | شرط | مسیر داخلی |
|---|---|---|
| `POST /v1/chat/completions` | متن ساده | `/v1/messages` در AgentRouter |
| `POST /v1/chat/completions` | ابزار یا تصویر | `/v1/responses` در AgentRouter |
| `POST /v1/messages` | متن ساده | `/v1/messages` در AgentRouter |
| `POST /v1/messages` | ابزار یا تصویر | `/v1/responses` در AgentRouter |

در مسیر Anthropic، پاسخ‌های Responses به رویدادهای SSE استاندارد Anthropic ترجمه می‌شوند تا Claude Code و OpenCode بدون تغییر کار کنند.

## تنظیمات

```
PROXY_RESPONSES_MODE=auto
```

- `auto` فقط درخواست‌های دارای ابزار یا تصویر را به Responses می‌فرستد.
- `always` همه درخواست‌ها را از Responses می‌فرستد.
- `off` مسیر Responses را غیرفعال می‌کند.

مقدار پیش‌فرض `auto` است.

## تست‌ها

سه اسکریپت در مخزن هست:

```
python scripts/test_tool_catalog.py       # سازگاری تعریف ابزارها در مسیر Anthropic
python scripts/test_full_catalog.py       # ۱۹ ابزار و مهارت در هر دو مسیر
python scripts/test_bridge.py             # ترجمه پاسخ و استریم با سرور ساختگی
```

`test_full_catalog.py` بررسی می‌کند که نام، توضیح و کل طرح‌واره هر ابزار بایت‌به‌بایت سالم عبور کند. کاتالوگ شامل پوسته، فایل، جست‌وجو، وب، فهرست کار، زیرعامل، مهارت، کنترل برنامه ویندوز، اسکرین‌شات، کلیپ‌بورد و کنترل دسکتاپ است.

## محدودیت‌ها

- پارامتر `stop` برای مدل `gpt-6.1-sol` در AgentRouter پشتیبانی نمی‌شود.
- فقط مدل‌هایی که کلید شما در AgentRouter به آن‌ها دسترسی دارد کار می‌کنند.
- اگر کلاینت ابزاری را در فهرست خود نداشته باشد، مدل هم نمی‌تواند آن را صدا بزند. پروکسی ابزار جدید نمی‌سازد؛ فقط ابزارهای کلاینت را منتقل می‌کند.

## امنیت

- کلید AgentRouter را در مخزن یا متغیرهای پروکسی ذخیره نکنید. پروکسی کلید را از هدر درخواست عبور می‌دهد.
- ابزارهایی مثل اجرای دستور و باز کردن برنامه فقط در کلاینت اجرا می‌شوند. دسترسی آن‌ها را در Hbox محدود کنید.
- لاگ پروکسی فقط نام مدل، تعداد ابزارها و متن خطای upstream را ثبت می‌کند؛ کلید و محتوای مکالمه ثبت نمی‌شود.

</div>

---

<div dir="ltr">

# Tools and skills

This document explains how the model uses tools and skills, and what the proxy does and does not do.

## Core rule

The proxy only **transports and translates**. Tools execute on the **client**.

```
Client (Hbox / Claude Code / OpenCode)
   │  messages + tool schemas
   ▼
Proxy on Railway
   │  translated to /v1/responses
   ▼
AgentRouter model  →  returns a tool call
   ▲
   └── proxy translates the call back
         ▼
Client executes the tool on Windows
```

The model never opens a file, launches an app, or clicks anything itself. It only says "call this tool with these arguments". The client executes it and returns the result.

## Why tools do not run on the server

The proxy runs in a Linux container on Railway, not on your PC. If the proxy executed tools itself:

- Apps would open on the server, not on your Windows desktop.
- Your files would not be reachable.
- Every request would become remote code execution on a public service.

That is why execution stays client-side. Hbox runs on your Windows machine and exposes the tools it can actually execute.

## What is supported

- Tool schemas in both OpenAI (`function.parameters`) and Anthropic (`input_schema`) shapes
- Tool results, including text and images
- Tool calls in streaming mode
- Images in user messages and tool results
- Skill tools with the full name list and descriptions
- Windows tools: shell and PowerShell, file read/write/edit, file search, app launch, screenshots, clipboard, mouse and keyboard control
- Document tools: Word, Excel, PowerPoint and PDF
- Browser, web search, todo and subagent tools

There is no fixed catalog in the proxy. Whatever the client sends reaches the model unchanged, and the model's call is translated back. Adding a new skill in Hbox needs no proxy change.

## Request routing

| Client endpoint | Condition | Internal route |
|---|---|---|
| `POST /v1/chat/completions` | plain text | AgentRouter `/v1/messages` |
| `POST /v1/chat/completions` | tools or images | AgentRouter `/v1/responses` |
| `POST /v1/messages` | plain text | AgentRouter `/v1/messages` |
| `POST /v1/messages` | tools or images | AgentRouter `/v1/responses` |

On the Anthropic route, Responses events are translated into standard Anthropic SSE so Claude Code and OpenCode work without changes.

## Configuration

```
PROXY_RESPONSES_MODE=auto
```

- `auto` sends only tool/image requests to Responses.
- `always` sends every request to Responses.
- `off` disables the Responses route.

The default is `auto`.

## Tests

Three scripts ship with the repository:

```
python scripts/test_tool_catalog.py       # Anthropic-path schema integrity
python scripts/test_full_catalog.py       # 19 tools and skills across both routes
python scripts/test_bridge.py             # response and stream translation against a mock upstream
```

`test_full_catalog.py` checks that each tool's name, description and JSON schema survive byte-identically. The catalog covers shell, files, search, web, todos, subagents, skills, Windows app launch, screenshots, clipboard and desktop control.

## Limits

- The `stop` parameter is not supported by `gpt-6.1-sol` on AgentRouter.
- Only models your AgentRouter key is authorized for will work.
- If the client does not expose a tool, the model cannot call it. The proxy does not invent tools; it only carries the client's own tools.

## Security

- Never store the AgentRouter key in the repository or in proxy variables. The proxy relays the key from the request header.
- Tools such as command execution and app launch run only on the client. Restrict their permissions in Hbox.
- Proxy logs record the model name, tool count and upstream error text only; keys and conversation content are not logged.

</div>
