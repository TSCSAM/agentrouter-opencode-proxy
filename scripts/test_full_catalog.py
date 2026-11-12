"""Verify that every tool/skill schema survives both proxy translation paths.

Covers the full agent catalog: shell, files, search, web, todos, subagents,
skills, Windows app control, screenshots, clipboard and computer use.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import proxy  # noqa: E402


def tool(name, description, properties, required=None):
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            **({"required": required} if required else {}),
        },
    }


CATALOG = [
    tool("bash", "Run a shell command on the user's machine", {
        "command": {"type": "string", "description": "Command to run"},
        "timeout": {"type": "number", "description": "Timeout in milliseconds"},
        "description": {"type": "string"},
    }, ["command"]),
    tool("read", "Read a file from disk", {
        "filePath": {"type": "string"},
        "offset": {"type": "integer"},
        "limit": {"type": "integer"},
    }, ["filePath"]),
    tool("write", "Write content to a file", {
        "filePath": {"type": "string"},
        "content": {"type": "string"},
    }, ["filePath", "content"]),
    tool("edit", "Replace text inside a file", {
        "filePath": {"type": "string"},
        "oldString": {"type": "string"},
        "newString": {"type": "string"},
        "replaceAll": {"type": "boolean", "default": False},
    }, ["filePath", "oldString", "newString"]),
    tool("glob", "Find files by glob pattern", {
        "pattern": {"type": "string"},
        "path": {"type": "string"},
    }, ["pattern"]),
    tool("grep", "Search file contents with a regex", {
        "pattern": {"type": "string"},
        "path": {"type": "string"},
        "include": {"type": "string"},
    }, ["pattern"]),
    tool("webfetch", "Fetch a URL and return its contents", {
        "url": {"type": "string"},
        "format": {"type": "string", "enum": ["text", "markdown", "html"]},
        "timeout": {"type": "number"},
    }, ["url"]),
    tool("websearch", "Search the public web", {
        "query": {"type": "string"},
        "numResults": {"type": "integer"},
    }, ["query"]),
    tool("todowrite", "Update the session task list", {
        "todos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["content", "status", "priority"],
            },
        },
    }, ["todos"]),
    tool("task", "Delegate work to a subagent", {
        "description": {"type": "string"},
        "prompt": {"type": "string"},
        "subagent_type": {"type": "string"},
    }, ["description", "prompt", "subagent_type"]),
    tool("skill", "Load a skill's instructions by name", {
        "name": {"type": "string", "description": "Skill name, e.g. Windows-skill"},
        "args": {"type": "string"},
    }, ["name"]),
    tool("computer", "Control the desktop: screenshot, click, type, key, scroll", {
        "action": {"type": "string", "enum": ["screenshot", "click", "double_click", "right_click", "type", "key", "scroll", "move"]},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "text": {"type": "string"},
        "keys": {"type": "array", "items": {"type": "string"}},
        "amount": {"type": "integer"},
    }, ["action"]),
    tool("open_windows_app", "Open an installed Windows application", {
        "app": {"type": "string", "enum": ["notepad", "calculator", "paint", "explorer", "cmd", "powershell"]},
        "arguments": {"type": "string"},
    }, ["app"]),
    tool("run_powershell", "Run a PowerShell command on the Windows host", {
        "command": {"type": "string"},
        "timeout_ms": {"type": "integer"},
    }, ["command"]),
    tool("screenshot", "Capture the current screen", {
        "region": {"type": "string", "enum": ["full", "active_window"]},
        "format": {"type": "string", "enum": ["png", "jpeg"]},
    }),
    tool("clipboard", "Read or write the Windows clipboard", {
        "action": {"type": "string", "enum": ["read", "write"]},
        "text": {"type": "string"},
    }, ["action"]),
    tool("notebook_edit", "Edit a Jupyter notebook cell", {
        "notebook_path": {"type": "string"},
        "cell_id": {"type": "string"},
        "new_source": {"type": "string"},
        "cell_type": {"type": "string", "enum": ["code", "markdown"]},
    }, ["notebook_path", "new_source"]),
    tool("ask_user", "Ask the user a question", {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
    }, ["question"]),
]

# A realistic Skill tool schema: Hbox sends every registered skill as an enum.
SKILL_NAMES = [
    "adaptive", "agp-9-upgrade", "android-cli", "android-for-cars-parked-apps",
    "android-intent-security", "android-permissions-security", "android-profiler",
    "Android-Skill", "anr-audit-and-fix", "appfunctions", "camerax",
    "cloudflare-webmaster-github", "display-glasses-with-jetpack-compose-glimmer",
    "edge-to-edge", "engage-sdk-integration", "firebase-ai-logic-basics",
    "firebase-auth-basics", "firebase-basics", "firebase-crashlytics",
    "firebase-data-connect-basics", "firebase-firestore",
    "firebase-security-rules-auditor", "glance-appwidget-updates-and-memory",
    "glance-canonical-layouts", "ink-app-builder", "ink-custom-brush-builder",
    "jetpack-compose-performance", "leanback-to-compose-tv-migration",
    "litert-lm", "litert-runtime", "media3-cast-integration",
    "migrate-xml-views-to-jetpack-compose", "ml-kit-genai-prompt-api",
    "mlkit-agent-api", "navigation-3", "navigation-event",
    "play-billing-library-version-upgrade", "play-policy-insights",
    "projected-hardware", "r8-analyzer", "restore-credentials", "testing-setup",
    "verified-email", "wear-compose-m3", "wear-widgets", "winapp-find-api",
    "winapp-find-ui", "winapp-frameworks", "winapp-identity", "winapp-manifest",
    "winapp-maui", "winapp-package", "winapp-performance", "winapp-sandbox",
    "winapp-setup", "winapp-signing", "winapp-troubleshoot",
    "winapp-ui-automation", "Windows-skill", "winui-code-review", "winui-design",
    "winui-dev", "winui-dev-workflow", "winui-devtools", "winui-packaging",
    "winui-setup", "winui-ui-testing", "winui-wpf-migration",
    "browser-use:control-browser", "browser-use:web-gui-tester",
    "documents:docx", "documents:docx-viewer", "pdf:pdf", "pdf:pdf-viewer",
    "presentations:pptx", "presentations:pptx-viewer", "spreadsheets:xlsx",
    "spreadsheets:xlsx-viewer", "visualize:visualize", "skill-creator:skill-creator",
    "plugin-creator:plugin-creator", "hbox-guide:diagnosing-mcp",
    "hbox-guide:diagnosing-skills", "hbox-guide:hbox-configuration-guide",
]
CATALOG.append(
    tool("Skill", "Load a skill by name. Available skills are listed in the enum.", {
        "name": {"type": "string", "enum": SKILL_NAMES},
        "arguments": {"type": "string"},
    }, ["name"])
)


def openai_body():
    return {
        "model": "agentrouter/gpt-6.1-sol",
        "messages": [{"role": "user", "content": "go"}],
        "tools": [{"type": "function", "function": copy.deepcopy(t)} for t in CATALOG],
        "tool_choice": "auto",
    }


def check_openai_path() -> None:
    converted = proxy._openai_to_anthropic(openai_body())["tools"]
    assert len(converted) == len(CATALOG)
    for source, target in zip(CATALOG, converted):
        assert target["name"] == source["name"]
        assert target["description"] == source["description"]
        assert target["input_schema"] == source["parameters"], source["name"]
    print(f"  OpenAI -> Anthropic   {len(CATALOG)} tools, every schema byte-identical")

    payload = proxy._openai_to_responses(openai_body())
    assert len(payload["tools"]) == len(CATALOG)
    for source, target in zip(CATALOG, payload["tools"]):
        assert target["name"] == source["name"]
        assert target["description"] == source["description"]
        assert target["parameters"] == source["parameters"], source["name"]
    print(f"  OpenAI -> Responses   {len(CATALOG)} tools, every schema byte-identical")


def check_anthropic_path() -> None:
    anthropic_tools = [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in CATALOG
    ]
    body = {
        "model": "gpt-6.1-sol",
        "max_tokens": 1024,
        "system": [{"type": "text", "text": "You are a Windows agent."}],
        "messages": [
            {"role": "user", "content": "Open Notepad."},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Opening it."},
                {"type": "tool_use", "id": "toolu_1", "name": "open_windows_app", "input": {"app": "notepad"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "notepad started (pid 4242)"},
            ]},
        ],
        "tools": anthropic_tools,
        "tool_choice": {"type": "auto"},
    }
    payload = proxy._anthropic_to_responses(body)
    assert payload["instructions"] == "You are a Windows agent."
    assert len(payload["tools"]) == len(CATALOG)
    for source, target in zip(CATALOG, payload["tools"]):
        assert target["name"] == source["name"]
        assert target["parameters"] == source["parameters"], source["name"]
    assert any(item.get("type") == "function_call_output" and item.get("call_id") == "toolu_1" for item in payload["input"])
    assert any(item.get("type") == "function_call" and item.get("name") == "open_windows_app" for item in payload["input"])
    print(f"  Anthropic -> Responses {len(CATALOG)} tools, tool_use/tool_result converted")

    fake_response = {
        "id": "resp_1",
        "model": "gpt-6.1-sol",
        "status": "completed",
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": "Notepad is open."}]},
            {"type": "function_call", "call_id": "call_2", "name": "screenshot", "arguments": "{\"region\":\"full\"}"},
        ],
    }
    message = proxy._responses_to_anthropic(fake_response)
    assert message["stop_reason"] == "tool_use"
    assert message["content"][0] == {"type": "text", "text": "Notepad is open."}
    assert message["content"][1]["name"] == "screenshot"
    assert message["content"][1]["input"] == {"region": "full"}
    print("  Responses -> Anthropic text + tool_use converted back")


def check_image_and_tool_result() -> None:
    converted = proxy._openai_to_anthropic({
        "model": "m",
        "messages": [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "function": {"name": "screenshot", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": [
                {"type": "text", "text": "screen:"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}},
            ]},
        ],
    })
    block = converted["messages"][1]["content"][0]
    assert block["type"] == "tool_result"
    assert block["content"][1]["source"]["media_type"] == "image/jpeg"
    print("  tool result with image            converted")

    anthropic = proxy._anthropic_to_responses({
        "model": "gpt-6.1-sol",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "What is this?"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
        ]}],
    })
    parts = anthropic["input"][0]["content"]
    assert parts[1]["type"] == "input_image"
    assert parts[1]["image_url"].startswith("data:image/png;base64,")
    assert parts[1]["detail"] == "auto"
    print("  Anthropic image -> input_image    converted with detail")


def main() -> None:
    print(f"catalog: {len(CATALOG)} tools, {len(json.dumps(CATALOG))} bytes")
    check_openai_path()
    check_anthropic_path()
    check_image_and_tool_result()
    print("FULL TOOL/SKILL CATALOG OK")


if __name__ == "__main__":
    main()
