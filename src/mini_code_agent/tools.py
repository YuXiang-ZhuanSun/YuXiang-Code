from __future__ import annotations

import shutil
import subprocess
import locale
from pathlib import Path
from typing import Any

from .config import Config
from .models import ToolResult


def compact(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def decode(raw: bytes) -> str:
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class LocalTools:
    def __init__(self, config: Config):
        self.config = config
        self.root = config.root

    def resolve(self, path: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.root / p
        return p.resolve()

    def bash(self, command: str) -> ToolResult:
        bash_path = shutil.which("bash")
        if self.config.shell == "powershell" or (self.config.shell == "auto" and not bash_path):
            wrapped = (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                "$OutputEncoding=[System.Text.Encoding]::UTF8; "
                f"{command}"
            )
            cmd = ["powershell", "-NoProfile", "-Command", wrapped]
            shell_name = "powershell"
        else:
            cmd = [bash_path or "bash", "-lc", command]
            shell_name = "bash"

        timeout = self.config.tool_timeout_seconds
        try:
            proc = subprocess.run(cmd, cwd=str(self.root), capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Command timed out after {timeout}s: {command}")
        except Exception as exc:
            return ToolResult(False, f"Command failed to start: {exc}")

        output = (
            f"$ [{shell_name}] {command}\n"
            f"exit_code={proc.returncode}\n\n"
            f"stdout:\n{decode(proc.stdout)}\n"
            f"stderr:\n{decode(proc.stderr)}"
        )
        return ToolResult(proc.returncode == 0, compact(output))

    def read(self, path: str) -> ToolResult:
        p = self.resolve(path)
        try:
            return ToolResult(True, compact(f"{p}\n\n{p.read_text(encoding='utf-8', errors='replace')}"))
        except Exception as exc:
            return ToolResult(False, f"Could not read {p}: {exc}")

    def write(self, path: str, content: str) -> ToolResult:
        p = self.resolve(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8", newline="")
            return ToolResult(True, f"Wrote {p} ({len(content)} chars)")
        except Exception as exc:
            return ToolResult(False, f"Could not write {p}: {exc}")

    def edit(self, path: str, old: str, new: str, replace_all: bool = False) -> ToolResult:
        p = self.resolve(path)
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
            count = data.count(old)
            if count == 0:
                return ToolResult(False, f"No match in {p}")
            if count > 1 and not replace_all:
                return ToolResult(False, f"Found {count} matches in {p}; set replace_all=true")
            updated = data.replace(old, new) if replace_all else data.replace(old, new, 1)
            p.write_text(updated, encoding="utf-8", newline="")
            return ToolResult(True, f"Edited {p}; replacements={count if replace_all else 1}")
        except Exception as exc:
            return ToolResult(False, f"Could not edit {p}: {exc}")

    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name == "bash":
            return self.bash(str(args.get("command", "")))
        if name == "read":
            return self.read(str(args.get("path", "")))
        if name == "write":
            return self.write(str(args.get("path", "")), str(args.get("content", "")))
        if name == "edit":
            return self.edit(
                str(args.get("path", "")),
                str(args.get("old", "")),
                str(args.get("new", "")),
                bool(args.get("replace_all", False)),
            )
        return ToolResult(False, f"Unknown tool: {name}")
