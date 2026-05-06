# Trace Analysis Example

This directory contains a complete offline trace-analysis example generated from a real two-turn YuXiang Code session.

Files:

- `deepseek-multiturn.agent_context.json`: the saved context produced by `/save examples/trace/deepseek-multiturn.agent_context.json`.
- `deepseek-multiturn.html`: the static report rendered from that saved context.

The session prompts were:

```text
Inspect README.md first. Summarize what this project says about harness design and observability. Use tools before answering.

Now inspect pyproject.toml and src/mini_code_agent/session.py. Explain why the saved context from /save is useful for offline trace analysis, and name two limitations. Use tools before answering.
```

Render the report again with:

```powershell
mini-code-agent-trace examples/trace/deepseek-multiturn.agent_context.json -o examples/trace/deepseek-multiturn.html
```
