<p align="right">
  <a href="README.md">English</a>
</p>

<p align="center">
  <img src="assets/yuxiang-code-logo.svg" width="520" alt="YuXiang Code logo">
</p>

<h1 align="center">YuXiang Code</h1>

<p align="center">
  <strong>一个自主 Agent，本质上就是 LLM + 工具 + 循环。</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="DeepSeek" src="https://img.shields.io/badge/DeepSeek-API-0F172A">
  <img alt="OpenAI compatible" src="https://img.shields.io/badge/API-OpenAI--compatible-111827">
  <img alt="Streaming SSE" src="https://img.shields.io/badge/Streaming-SSE-2563EB">
  <img alt="Local CLI" src="https://img.shields.io/badge/Run-Local%20CLI-4B5563">
  <img alt="Tools" src="https://img.shields.io/badge/Tools-bash%20%7C%20read%20%7C%20write%20%7C%20edit-047857">
</p>

<p align="center">
  一个很小、可观察的本地 code agent：纯文件、可见工具调用，以及真的能工作的朴素循环。
</p>

---

## Philosophy

| 取舍 | 原因 |
|---|---|
| <img alt="No" src="https://img.shields.io/static/v1?label=No&message=&color=red"> Plan Mode | 用普通的 `PLAN.md` 文件替代。它可见、可版本控制，也能跨会话共享。 |
| <img alt="No" src="https://img.shields.io/static/v1?label=No&message=&color=red"> MCP integration | 工具描述会真实占用上下文窗口。CLI 工具和 README 通过 `bash` 按需加载即可。 |
| <img alt="No" src="https://img.shields.io/static/v1?label=No&message=&color=red"> Sub-agents | 在黑盒里再放一个黑盒，会降低可观察性。需要时用 `bash` 调另一个进程。 |
| <img alt="No" src="https://img.shields.io/static/v1?label=No&message=&color=red"> `maxSteps` ceremony | 循环应该在任务完成时自然结束。只有出现真实问题时，才添加步数限制。 |
| <img alt="No" src="https://img.shields.io/static/v1?label=No&message=&color=red"> permission theater | 一旦 agent 能写代码并运行代码，虚假的确认弹窗就不是安全模型。保持本地、可见、可检查更重要。 |

YuXiang Code 故意保持很小。它不想变成一个 Agent 操作系统，而是把核心循环留在你眼前：

```text
user -> LLM -> tool call -> tool result -> LLM -> done
```

重点不是把复杂度藏进另一个框架里，而是让 agent 足够可理解：它运行时，你能看见它在做什么，也能调试它。

## 它是什么

- 流式终端对话，工具调用全程可见。
- 本地工具：`bash`、`read`、`write`、`edit`。
- 手动上下文控制：你可以查看、裁剪、保存、重写模型真正收到的上下文。
- 本地优先的 CLI，而不是托管式 agent 平台。

这就是产品本身。其他东西都需要证明自己值得加入。

## 快速开始

```powershell
$env:DEEPSEEK_API_KEY="your-key"
python -m pip install -e .
python .\code_agent.py
```

## 命令

只有带 `/` 前缀的输入才会被解释为命令。`history` 是普通聊天内容；`/history` 才会打开当前上下文面板。

```text
/help              查看命令
/models            查看内置 DeepSeek 模型名
/history           查看完整 active model context
/context           /history 的别名
/clear             清空上下文和输入历史
/keep [n]          只保留最近 n 条上下文消息
/drop INDEX        删除一条上下文消息
/set INDEX text    替换一条上下文消息
/system text       替换 system prompt
/save              保存上下文到 .agent_context.json
/load              从 .agent_context.json 加载上下文
/model [name]      查看或切换模型
/exit              退出
```

## 项目结构

```text
.
|-- code_agent.py
|-- pyproject.toml
|-- assets/
`-- src/
    `-- mini_code_agent/
        |-- api.py
        |-- app.py
        |-- config.py
        |-- models.py
        |-- prompt.py
        |-- session.py
        |-- tools.py
        `-- ui.py
```

## License

MIT
