from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOOL_CALL_RE = re.compile(
    r"<tool_call\s+name=[\"'](?P<name>[a-zA-Z_][\w-]*)[\"']\s*>(?P<body>.*?)</tool_call>",
    flags=re.DOTALL,
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    raw: str


@dataclass
class ToolResultBlock:
    name: str
    ok: bool | None
    text: str


@dataclass
class MessageInfo:
    index: int
    role: str
    content: str
    chars: int
    lines: int
    tool_calls: list[ToolCall]
    tool_results: list[ToolResultBlock]
    flags: list[str]


def load_context(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("context file must contain a JSON object")
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise ValueError("context file must contain a messages list")
    return payload


def parse_json_tool_call(text: str) -> ToolCall | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and isinstance(obj.get("tool"), str) and isinstance(obj.get("args"), dict):
        return ToolCall(obj["tool"], obj["args"], cleaned)
    return None


def normalize_tool_args(name: str, obj: dict[str, Any]) -> dict[str, Any]:
    if name == "bash" and isinstance(obj.get("command"), str):
        return {"command": obj["command"]}
    if isinstance(obj.get("args"), dict):
        return obj["args"]
    if name == "read" and isinstance(obj.get("path"), str):
        return {"path": obj["path"]}
    if name == "write" and isinstance(obj.get("path"), str):
        return {"path": obj["path"], "content": str(obj.get("content", ""))}
    if name == "edit" and isinstance(obj.get("path"), str):
        return {
            "path": obj["path"],
            "old": str(obj.get("old", "")),
            "new": str(obj.get("new", "")),
            "replace_all": bool(obj.get("replace_all", False)),
        }
    return obj


def parse_tool_calls(content: str) -> list[ToolCall]:
    direct = parse_json_tool_call(content)
    if direct:
        return [direct]

    calls: list[ToolCall] = []
    seen: set[tuple[str, str]] = set()
    for match in TOOL_CALL_RE.finditer(content):
        body = match.group("body").strip()
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        name = match.group("name")
        args = normalize_tool_args(name, obj)
        key = (name, json.dumps(args, ensure_ascii=False, sort_keys=True))
        if key not in seen:
            seen.add(key)
            calls.append(ToolCall(name, args, match.group(0)))

    decoder = json.JSONDecoder()
    index = 0
    while index < len(content):
        start = content.find("{", index)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str) and isinstance(obj.get("args"), dict):
            name = obj["tool"]
            args = obj["args"]
            key = (name, json.dumps(args, ensure_ascii=False, sort_keys=True))
            if key not in seen:
                seen.add(key)
                calls.append(ToolCall(name, args, json.dumps(obj, ensure_ascii=False)))
        index = start + max(end, 1)
    return calls


def parse_tool_results(content: str) -> list[ToolResultBlock]:
    if not content.startswith("Tool results:"):
        return []

    body = content.removeprefix("Tool results:").strip()
    if not body:
        return []

    blocks: list[ToolResultBlock] = []
    pattern = re.compile(r"^(.+?) \((ok|failed)\):\n", flags=re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        return [ToolResultBlock("unknown", None, body)]

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        blocks.append(
            ToolResultBlock(
                name=match.group(1).strip(),
                ok=match.group(2) == "ok",
                text=body[start:end].strip(),
            )
        )
    return blocks


def flags_for(content: str, calls: list[ToolCall], results: list[ToolResultBlock]) -> list[str]:
    flags: list[str] = []
    lower = content.lower()
    if len(content) > 8000:
        flags.append("long")
    if "...[truncated " in content:
        flags.append("truncated")
    if "timed out" in lower or "timeout" in lower:
        flags.append("timeout")
    if "tool crashed" in lower or "traceback" in lower or "exception" in lower:
        flags.append("error")
    if any(result.ok is False for result in results):
        flags.append("failed-tool")
    if len(calls) > 1:
        flags.append("multi-tool")
    return flags


def analyze_messages(payload: dict[str, Any]) -> list[MessageInfo]:
    infos: list[MessageInfo] = []
    for index, msg in enumerate(payload.get("messages", [])):
        if not isinstance(msg, dict):
            role = "unknown"
            content = str(msg)
        else:
            role = str(msg.get("role", "unknown"))
            content = str(msg.get("content", ""))
        calls = parse_tool_calls(content) if role == "assistant" else []
        results = parse_tool_results(content) if role == "user" else []
        infos.append(
            MessageInfo(
                index=index,
                role=role,
                content=content,
                chars=len(content),
                lines=content.count("\n") + 1 if content else 0,
                tool_calls=calls,
                tool_results=results,
                flags=flags_for(content, calls, results),
            )
        )
    return infos


def summarize(payload: dict[str, Any], messages: list[MessageInfo]) -> dict[str, Any]:
    roles = Counter(message.role for message in messages)
    tool_calls = [call for message in messages for call in message.tool_calls]
    tool_results = [result for message in messages for result in message.tool_results]
    total_chars = sum(message.chars for message in messages)
    longest = max(messages, key=lambda message: message.chars, default=None)
    command_counts = Counter(
        str(call.args.get("command", "")) for call in tool_calls if call.name == "bash" and call.args.get("command")
    )
    repeated_commands = [command for command, count in command_counts.items() if count > 1]
    risky = [message for message in messages if message.flags]
    return {
        "model": payload.get("model", "(unknown)"),
        "message_count": len(messages),
        "roles": roles,
        "history_count": len(payload.get("history") or []),
        "total_chars": total_chars,
        "tool_call_count": len(tool_calls),
        "tool_result_count": len(tool_results),
        "failed_tool_result_count": sum(1 for result in tool_results if result.ok is False),
        "truncated_count": sum(1 for message in messages if "truncated" in message.flags),
        "long_count": sum(1 for message in messages if "long" in message.flags),
        "risky_count": len(risky),
        "longest_index": longest.index if longest else None,
        "longest_chars": longest.chars if longest else 0,
        "repeated_command_count": len(repeated_commands),
    }


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def preview(content: str, limit: int = 180) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
    <div class="metric">
      <div class="metric-value">{esc(value)}</div>
      <div class="metric-label">{esc(label)}</div>
      {f'<div class="metric-hint">{esc(hint)}</div>' if hint else ''}
    </div>
    """


def render_tool_call(call: ToolCall) -> str:
    return f"""
    <div class="tool-card">
      <div class="tool-head"><span class="pill tool">{esc(call.name)}</span><span>tool call</span></div>
      <pre>{esc(pretty_json(call.args))}</pre>
    </div>
    """


def render_tool_result(result: ToolResultBlock) -> str:
    state = "unknown" if result.ok is None else ("ok" if result.ok else "failed")
    return f"""
    <div class="tool-card {state}">
      <div class="tool-head"><span class="pill {state}">{esc(state)}</span><span>{esc(result.name)} result</span></div>
      <pre>{esc(result.text)}</pre>
    </div>
    """


def render_message(message: MessageInfo) -> str:
    flags = "".join(f'<span class="pill warn">{esc(flag)}</span>' for flag in message.flags)
    tools = "".join(render_tool_call(call) for call in message.tool_calls)
    results = "".join(render_tool_result(result) for result in message.tool_results)
    open_attr = " open" if message.index < 3 or message.flags else ""
    return f"""
    <details class="message {esc(message.role)}"{open_attr}>
      <summary>
        <span class="index">[{message.index}]</span>
        <span class="role">{esc(message.role)}</span>
        <span class="summary-text">{esc(preview(message.content))}</span>
        <span class="meta">{message.chars} chars · {message.lines} lines</span>
        {flags}
      </summary>
      {tools}
      {results}
      <pre class="content">{esc(message.content)}</pre>
    </details>
    """


def diagnosis(summary: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if summary["tool_call_count"] == 0:
        notes.append("No tool calls were detected in assistant messages; this context is mostly conversational.")
    if summary["failed_tool_result_count"]:
        notes.append(f"{summary['failed_tool_result_count']} failed tool result(s) were preserved in context.")
    if summary["truncated_count"]:
        notes.append(f"{summary['truncated_count']} message(s) contain truncated tool output.")
    if summary["long_count"]:
        notes.append(f"{summary['long_count']} message(s) are longer than 8k characters and may dominate context budget.")
    if summary["repeated_command_count"]:
        notes.append(f"{summary['repeated_command_count']} repeated bash command pattern(s) were found.")
    if not notes:
        notes.append("No obvious fragility markers were detected from the saved context shape.")
    return notes


def render_html(payload: dict[str, Any], source: Path) -> str:
    messages = analyze_messages(payload)
    summary = summarize(payload, messages)
    roles = summary["roles"]
    role_text = ", ".join(f"{role}: {count}" for role, count in sorted(roles.items()))
    notes = "".join(f"<li>{esc(note)}</li>" for note in diagnosis(summary))
    rendered_messages = "\n".join(render_message(message) for message in messages)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YuXiang Code Trace</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f7f8fa;
  --panel: #ffffff;
  --text: #1d2433;
  --muted: #657083;
  --line: #d8dee8;
  --user: #0f766e;
  --assistant: #315f9d;
  --system: #6d5a12;
  --tool: #8b4c13;
  --bad: #b42318;
  --ok: #16794c;
  --warn: #9a5b00;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  padding: 28px 32px 18px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}}
h1 {{ margin: 0 0 6px; font-size: 26px; letter-spacing: 0; }}
.subtle {{ color: var(--muted); }}
main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}}
.metric {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}}
.metric-value {{ font-size: 24px; font-weight: 700; }}
.metric-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
.metric-hint {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
.diagnosis {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 18px;
}}
.diagnosis h2 {{ margin: 0 0 8px; font-size: 16px; }}
.diagnosis ul {{ margin: 0; padding-left: 20px; }}
.toolbar {{
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}}
input {{
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  font: inherit;
}}
.message {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-left-width: 5px;
  border-radius: 8px;
  margin: 10px 0;
  overflow: hidden;
}}
.message.system {{ border-left-color: var(--system); }}
.message.user {{ border-left-color: var(--user); }}
.message.assistant {{ border-left-color: var(--assistant); }}
summary {{
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
}}
.index, .meta, .summary-text {{ color: var(--muted); }}
.summary-text {{
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.role {{ font-weight: 700; }}
.pill {{
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
  background: #edf1f7;
  color: #334155;
}}
.pill.tool {{ background: #fff1dc; color: var(--tool); }}
.pill.ok {{ background: #dcfce7; color: var(--ok); }}
.pill.failed, .pill.unknown {{ background: #fee2e2; color: var(--bad); }}
.pill.warn {{ background: #fff7d6; color: var(--warn); }}
pre {{
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 13px/1.45 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}}
.content {{
  border-top: 1px solid var(--line);
  padding: 14px;
  background: #fbfcfe;
}}
.tool-card {{
  margin: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}}
.tool-card.failed {{ border-color: #f0b4af; }}
.tool-head {{
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: #f8fafc;
  color: var(--muted);
}}
.tool-card pre {{ padding: 10px; background: #ffffff; }}
.hidden {{ display: none; }}
@media (max-width: 720px) {{
  header {{ padding: 22px 18px 14px; }}
  main {{ padding: 16px; }}
  summary {{ grid-template-columns: auto auto 1fr; }}
  .meta {{ display: none; }}
}}
</style>
</head>
<body>
<header>
  <h1>YuXiang Code Trace</h1>
  <div class="subtle">Source: {esc(source)} · Model: {esc(summary["model"])} · Roles: {esc(role_text)}</div>
</header>
<main>
  <section class="metrics">
    {metric("messages", summary["message_count"])}
    {metric("history", summary["history_count"])}
    {metric("chars", summary["total_chars"])}
    {metric("tool calls", summary["tool_call_count"])}
    {metric("tool results", summary["tool_result_count"])}
    {metric("failed tools", summary["failed_tool_result_count"])}
    {metric("truncated", summary["truncated_count"])}
    {metric("longest", f'[{summary["longest_index"]}]', f'{summary["longest_chars"]} chars')}
  </section>
  <section class="diagnosis">
    <h2>Harness Signals</h2>
    <ul>{notes}</ul>
  </section>
  <div class="toolbar">
    <input id="filter" type="search" placeholder="Filter messages, tool names, commands, output...">
  </div>
  <section id="messages">
    {rendered_messages}
  </section>
</main>
<script>
const filter = document.getElementById('filter');
const messages = Array.from(document.querySelectorAll('.message'));
filter.addEventListener('input', () => {{
  const q = filter.value.trim().toLowerCase();
  for (const el of messages) {{
    el.classList.toggle('hidden', q && !el.innerText.toLowerCase().includes(q));
  }}
}});
</script>
</body>
</html>
"""


def render_file(input_path: Path, output_path: Path) -> None:
    payload = load_context(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(payload, input_path), encoding="utf-8", newline="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a YuXiang Code /save context as a static HTML trace report.")
    parser.add_argument("context", type=Path, help="path to .agent_context.json")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output HTML path")
    args = parser.parse_args()

    input_path = args.context
    output_path = args.output if args.output else input_path.with_suffix(".html")
    render_file(input_path, output_path)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
