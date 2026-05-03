from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "YuXiang Code"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
CONTEXT_FILE = ".agent_context.json"
DEFAULT_TOOL_TIMEOUT_SECONDS = 90


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


@dataclass(frozen=True)
class Config:
    root: Path
    model: str
    base_url: str
    api_key: str
    shell: str
    max_tool_rounds: int = 12
    tool_timeout_seconds: int = DEFAULT_TOOL_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls, root: str, model: str | None) -> "Config":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        return cls(
            root=Path(root).resolve(),
            model=model or os.getenv("CODE_AGENT_MODEL", DEFAULT_MODEL),
            base_url=os.getenv("CODE_AGENT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            api_key=api_key,
            shell=os.getenv("CODE_AGENT_SHELL", "auto").lower(),
            tool_timeout_seconds=env_int("CODE_AGENT_TOOL_TIMEOUT", DEFAULT_TOOL_TIMEOUT_SECONDS),
        )

    @property
    def context_path(self) -> Path:
        return self.root / CONTEXT_FILE
