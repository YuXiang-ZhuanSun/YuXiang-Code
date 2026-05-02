<p align="center">
  <img src="assets/yuxiang-code-logo.svg" width="520" alt="YuXiang Code logo">
</p>

<h1 align="center">YuXiang Code</h1>

<p align="center">
  <strong>An autonomous agent is just an LLM + tools + a loop.</strong>
</p>

<p align="center">
  A tiny, inspectable code agent for people who prefer plain files, visible tool calls, and boring loops that actually work.
</p>

---

## Philosophy

YuXiang Code is intentionally small. It does not try to become an operating system for agents. It keeps the core loop visible:

```text
user -> LLM -> tool call -> tool result -> LLM -> done
```

The point is not to hide complexity behind another framework. The point is to make the agent understandable enough that you can debug it while it is running.

## What It Is

- Streaming terminal chat with visible tool calls.
- Local tools for `bash`, `read`, `write`, and `edit`.
- Manual context controls so you can inspect, trim, save, and rewrite the conversation.

That is the product. Everything else has to earn its place.

## Deliberately Missing

| 刻意不做 | 理由 |
|---|---|
| 无 Plan Mode | 用文件 `PLAN.md` 替代。有完整可观测性，可版本控制，可跨会话共享。 |
| 无 MCP 支持 | MCP 工具描述占 7-9% 上下文窗口。用 CLI + README 通过 `bash` 调用，按需加载。 |
| 无 Sub-Agent | "黑盒中的黑盒"，失去可观测性。通过 `bash` 自我调用，保留完整输出可见性。 |
| 无 maxSteps | 循环自然结束。"我从来没找到需要 maxSteps 的用例，所以为什么要加？" |
| 无权限检查 | "安全措施大多是安全剧场。一旦 Agent 能写代码和运行代码，就 game over。" |

## Quick Start

```powershell
$env:DEEPSEEK_API_KEY="your-key"
python -m pip install -e .
python .\code_agent.py
```

## Commands

```text
/help              show commands
/models            show built-in DeepSeek model names
/history           show the full active model context
/context           alias of /history
/clear             clear context and prompt history
/keep [n]          keep only last n context messages
/drop INDEX        remove one context message
/set INDEX text    replace one context message
/system text       replace the system prompt
/save              save context to .agent_context.json
/load              load context from .agent_context.json
/model [name]      show or change model
/exit              quit
```

## License

MIT
