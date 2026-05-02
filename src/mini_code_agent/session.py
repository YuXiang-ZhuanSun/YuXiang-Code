from __future__ import annotations

import json
import re
import sys
from typing import Any

from .api import DeepSeekClient
from .config import Config
from .models import Message, Usage
from .prompt import SYSTEM_PROMPT
from .tools import LocalTools, compact
from . import ui


class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = DeepSeekClient(config)
        self.tools = LocalTools(config)
        self.messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.history: list[str] = []

    def save(self) -> str:
        payload = {"model": self.config.model, "messages": self.messages, "history": self.history}
        self.config.context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"saved {self.config.context_path}"

    def load(self) -> str:
        if not self.config.context_path.exists():
            return f"missing {self.config.context_path}"
        payload = json.loads(self.config.context_path.read_text(encoding="utf-8"))
        self.messages = payload.get("messages", self.messages)
        self.history = payload.get("history", self.history)
        return f"loaded {self.config.context_path}"

    def context_lines(self) -> list[str]:
        lines = []
        for i, msg in enumerate(self.messages):
            content = msg["content"].replace("\r\n", "\n").strip()
            lines.append(f"[{i}] {msg['role']}\n{content}")
        return lines

    def drop_message(self, index: int) -> str:
        if index == 0:
            return "refusing to drop system message; use /system to edit it"
        if index < 0 or index >= len(self.messages):
            return f"message index out of range: {index}"
        removed = self.messages.pop(index)
        return f"dropped [{index}] {removed['role']}"

    def set_message(self, index: int, content: str) -> str:
        if index < 0 or index >= len(self.messages):
            return f"message index out of range: {index}"
        if not content:
            return "empty content ignored"
        self.messages[index]["content"] = content
        return f"updated [{index}] {self.messages[index]['role']}"

    def set_system(self, content: str) -> str:
        if not content:
            return "empty system prompt ignored"
        self.messages[0] = {"role": "system", "content": content}
        return "system prompt updated"

    def parse_tool_call(self, text: str) -> tuple[str, dict[str, Any]] | None:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str) and isinstance(obj.get("args"), dict):
            return obj["tool"], obj["args"]
        return None

    def parse_tool_calls(self, text: str) -> list[tuple[str, dict[str, Any]]]:
        direct = self.parse_tool_call(text)
        if direct:
            return [direct]

        calls: list[tuple[str, dict[str, Any]]] = []
        for match in re.finditer(
            r"<tool_call\s+name=[\"'](?P<name>[a-zA-Z_][\w-]*)[\"']\s*>(?P<body>.*?)</tool_call>",
            text,
            flags=re.DOTALL,
        ):
            try:
                obj = json.loads(match.group("body").strip())
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                calls.append((match.group("name"), self.normalize_tool_args(match.group("name"), obj)))

        decoder = json.JSONDecoder()
        index = 0
        while index < len(text):
            start = text.find("{", index)
            if start == -1:
                break
            try:
                obj, end = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                index = start + 1
                continue
            if isinstance(obj, dict) and isinstance(obj.get("tool"), str) and isinstance(obj.get("args"), dict):
                calls.append((obj["tool"], obj["args"]))
            index = start + max(end, 1)
        return calls

    def normalize_tool_args(self, name: str, obj: dict[str, Any]) -> dict[str, Any]:
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

    def stream_once(self, usage_total: Usage) -> str:
        chunks: list[str] = []
        mode: str | None = None
        pending = ""
        spin = ui.Spinner()
        spin.start()
        try:
            for text, usage in self.client.stream_chat(self.messages):
                if usage:
                    usage_total.add(usage)
                if not text:
                    continue
                chunks.append(text)
                if mode == "silent":
                    continue
                if mode == "print":
                    print(text, end="", flush=True)
                    continue

                pending += text
                stripped = pending.lstrip()
                if not stripped:
                    continue
                spin.stop()
                if stripped[0] == "{":
                    mode = "silent"
                    continue
                mode = "print"
                ui.assistant_start()
                print(pending, end="", flush=True)
        finally:
            spin.stop()
        if mode == "print":
            print(flush=True)
        return "".join(chunks)

    def run_turn(self, user_text: str) -> Usage:
        self.history.append(user_text)
        self.messages.append({"role": "user", "content": user_text})
        usage_total = Usage()

        for _ in range(self.config.max_tool_rounds):
            answer = self.stream_once(usage_total)
            tool_calls = self.parse_tool_calls(answer)
            if not tool_calls:
                self.messages.append({"role": "assistant", "content": answer})
                return usage_total

            self.messages.append({"role": "assistant", "content": answer})
            results: list[str] = []
            for name, args in tool_calls:
                ui.tool_box(name, json.dumps(args, ensure_ascii=False))
                result = self.tools.run(name, args)
                ui.tool_box(f"{name}:result", compact(result.text, 2400))
                results.append(f"{name} ({'ok' if result.ok else 'failed'}):\n{result.text}")
            self.messages.append({"role": "user", "content": "Tool results:\n\n" + "\n\n".join(results)})

        print("tool loop stopped: too many tool calls", file=sys.stderr)
        return usage_total

    def handle_command(self, line: str) -> bool:
        raw = line.strip()
        if not raw.startswith("/"):
            return False

        cmd = raw[1:]
        parts = cmd.split()
        if not parts:
            return True

        name = parts[0].lower()
        if name in {"exit", "quit", "q"}:
            raise SystemExit(0)
        if name == "help":
            ui.print_help()
            return True
        if name == "models":
            ui.popup(
                "models",
                [
                    "deepseek-v4-pro",
                    "deepseek-v4-flash",
                    "deepseek-chat (deprecated on 2026-07-24)",
                    "deepseek-reasoner (deprecated on 2026-07-24)",
                ],
            )
            return True
        if name == "history":
            ui.popup("history / active context", self.context_lines())
            return True
        if name == "context":
            ui.popup("context", self.context_lines())
            return True
        if name == "clear":
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            self.history = []
            ui.status("session cleared")
            return True
        if name == "keep":
            n = int(parts[1]) if len(parts) > 1 else 8
            self.messages = [self.messages[0]] + self.messages[-n:]
            ui.status(f"kept last {n} messages")
            return True
        if name == "drop":
            if len(parts) < 2:
                ui.warn("usage: /drop INDEX")
                return True
            ui.status(self.drop_message(int(parts[1])))
            return True
        if name == "set":
            if len(parts) < 3:
                ui.warn("usage: /set INDEX new content")
                return True
            ui.status(self.set_message(int(parts[1]), cmd.split(maxsplit=2)[2]))
            return True
        if name == "system":
            content = cmd.split(maxsplit=1)[1] if len(parts) > 1 else ""
            ui.status(self.set_system(content))
            return True
        if name == "save":
            ui.status(self.save())
            return True
        if name == "load":
            ui.status(self.load())
            return True
        if name == "model":
            if len(parts) > 1:
                object.__setattr__(self.config, "model", parts[1])
            ui.status(f"model {self.config.model}")
            return True
        ui.warn(f"unknown command: /{name}")
        return True
