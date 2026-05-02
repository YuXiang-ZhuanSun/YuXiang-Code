from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

from .config import Config
from .models import Message, Usage


class DeepSeekClient:
    def __init__(self, config: Config):
        self.config = config

    def stream_chat(self, messages: list[Message]) -> Iterator[tuple[str, Usage | None]]:
        if not self.config.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")

        body = json.dumps(
            {
                "model": self.config.model,
                "messages": messages,
                "temperature": 0.2,
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            ensure_ascii=False,
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

        attempts = 3
        for attempt in range(1, attempts + 1):
            yielded_content = False
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        raw = line.decode("utf-8", errors="replace").strip()
                        if not raw or not raw.startswith("data:"):
                            continue
                        data = raw[5:].strip()
                        if data == "[DONE]":
                            break

                        chunk = json.loads(data)
                        usage = Usage.from_dict(chunk.get("usage")) if chunk.get("usage") else None
                        choices = chunk.get("choices") or []
                        if not choices:
                            yield "", usage
                            continue

                        delta = choices[0].get("delta") or {}
                        text = delta.get("content") or ""
                        if text:
                            yielded_content = True
                        yield text, usage
                return
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"DeepSeek request failed: HTTP {exc.code}\n{detail}") from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
                if yielded_content:
                    raise RuntimeError(f"DeepSeek stream interrupted after partial response: {exc}") from exc
                if attempt == attempts:
                    raise RuntimeError(f"DeepSeek request failed after {attempts} attempts: {exc}") from exc
                time.sleep(0.6 * attempt)
