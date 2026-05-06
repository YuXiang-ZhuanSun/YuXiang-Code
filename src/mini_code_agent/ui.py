from __future__ import annotations

import itertools
import os
import shutil
import sys
import threading
import time
import textwrap

if os.name == "nt":
    import ctypes

from rich.console import Console
from rich.align import Align
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from .models import Usage


console = Console()


def width() -> int:
    return max(60, min(shutil.get_terminal_size((100, 28)).columns, 140))


def rule(label: str = "") -> str:
    w = width()
    if not label:
        return "-" * w
    label = f" {label} "
    left = max(1, (w - len(label)) // 2)
    return "-" * left + label + "-" * max(1, w - left - len(label))


def say(text: str = "") -> None:
    print(text, flush=True)


def enable_ansi() -> None:
    if os.name != "nt":
        return
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


def header(app_name: str, root: str, model: str) -> None:
    from . import __version__

    logo = Text(
        "\n".join(
            [
                "   .----.",
                "  /  y  /\\",
                " /__x_/  )",
                " \\  <_  /",
                "  `----'",
            ]
        ),
        style="cyan",
    )
    title = Text()
    title.append("YuXiang", style="bold cyan")
    title.append(" Code", style="bold white")

    details = Text()
    details.append_text(title)
    details.append(f"  v{__version__}\n", style="dim")
    details.append("root   ", style="dim")
    details.append(f"{root}\n")
    details.append("model  ", style="dim")
    details.append(f"{model}\n")
    details.append("type   ", style="dim")
    details.append("/help", style="bold")
    details.append(" for commands")

    layout = Table.grid(padding=(0, 2))
    layout.add_column(justify="left", no_wrap=True)
    layout.add_column(justify="left")
    layout.add_row(logo, details)

    console.print(
        Panel(
            Align.left(layout),
            title=f"[bold]{app_name}[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def input_box() -> str:
    if os.getenv("CODE_AGENT_SIMPLE_INPUT") == "1":
        return simple_input_box()

    try:
        return prompt_toolkit_input()
    except Exception as exc:
        say(f"[ui fallback] prompt_toolkit unavailable: {exc}")
        return simple_input_box()


def simple_input_box() -> str:
    if not sys.stdin.isatty():
        say(rule("input"))
        try:
            line = input("| > ")
        except EOFError:
            line = "/exit"
        say(rule())
        return line.strip()

    line = input("> ")
    return line.strip()


def prompt_toolkit_input() -> str:
    text_area = TextArea(
        height=1,
        prompt="> ",
        multiline=False,
        wrap_lines=False,
        focusable=True,
    )
    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event) -> None:
        event.app.exit(result=text_area.text)

    @bindings.add("c-c")
    def _(event) -> None:
        event.app.exit(exception=KeyboardInterrupt())

    root = HSplit(
        [
            Frame(
                text_area,
                title=" input ",
                style="class:input-frame",
            )
        ],
        padding=0,
    )
    app = Application(
        layout=Layout(root, focused_element=text_area),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=False,
        style=Style.from_dict(
            {
                "input-frame": "ansibrightcyan",
                "text-area": "",
                "text-area.prompt": "ansibrightgreen",
            }
        ),
    )
    result = app.run()
    return (result or "").strip()


def assistant_start() -> None:
    console.print()
    console.print(Rule("assistant", style="cyan"))


def tool_box(name: str, body: str) -> None:
    console.print(
        Panel(
            Text(body),
            title=f"tool:{name}",
            border_style="yellow",
            padding=(0, 1),
        )
    )


def usage_line(usage: Usage) -> None:
    console.print(
        Panel(
            f"prompt={usage.prompt_tokens}  completion={usage.completion_tokens}  total={usage.total_tokens}",
            title="tokens",
            border_style="green",
            padding=(0, 1),
        )
    )


class Spinner:
    def __init__(self, text: str = "thinking"):
        self.text = text
        self.done = threading.Event()
        self.frames = itertools.cycle("|/-\\")
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.done.is_set():
            sys.stdout.write(f"\r{self.text} {next(self.frames)}")
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write("\r" + " " * (len(self.text) + 4) + "\r")
        sys.stdout.flush()

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.done.set()
        self.thread.join(timeout=0.3)


def popup(title: str, lines: list[str]) -> None:
    if not lines:
        lines = ["(empty)"]
    console.print(
        Panel(
            "\n".join(lines),
            title=title,
            border_style="magenta",
            padding=(0, 1),
        )
    )


def interactive_history(title: str, lines: list[str], locked_indices: set[int] | None = None) -> list[int]:
    if os.getenv("CODE_AGENT_SIMPLE_INPUT") == "1" or not sys.stdin.isatty():
        popup(title, lines)
        return []

    locked_indices = locked_indices or set()
    items = list(enumerate(lines))
    deleted: list[int] = []
    selected = 0
    top = 0
    visible_count = max(6, min(shutil.get_terminal_size((100, 28)).lines - 8, 18))
    notice = "↑↓ 选择 · Delete/Backspace 删除 · Esc/q/Enter 退出"

    def clamp_view() -> None:
        nonlocal selected, top
        if not items:
            selected = 0
            top = 0
            return
        selected = max(0, min(selected, len(items) - 1))
        if selected < top:
            top = selected
        if selected >= top + visible_count:
            top = selected - visible_count + 1

    def make_text() -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        if not items:
            return [("class:empty", "(empty)")]

        bottom = min(len(items), top + visible_count)
        for row, (original_index, body) in enumerate(items[top:bottom], start=top):
            is_selected = row == selected
            is_locked = original_index in locked_indices
            prefix = ">" if is_selected else " "
            lock = " locked" if is_locked else ""
            style = "class:selected" if is_selected else "class:locked" if is_locked else ""
            lines_for_item = body.splitlines() or [""]
            first = lines_for_item[0]
            fragments.append((style, f"{prefix} {first}{lock}\n"))
            for continuation in lines_for_item[1:]:
                fragments.append((style, f"  {continuation}\n"))
        if top > 0:
            fragments.insert(0, ("class:help", f"... {top} above ...\n"))
        if bottom < len(items):
            fragments.append(("class:help", f"... {len(items) - bottom} below ...\n"))
        return fragments

    control = FormattedTextControl(make_text, focusable=True)
    window = Window(content=control, wrap_lines=True, always_hide_cursor=True)
    toolbar = Window(
        content=FormattedTextControl([("class:help", notice)]),
        height=1,
        always_hide_cursor=True,
    )
    bindings = KeyBindings()

    @bindings.add("up")
    def _(event) -> None:
        nonlocal selected
        selected -= 1
        clamp_view()
        event.app.invalidate()

    @bindings.add("down")
    def _(event) -> None:
        nonlocal selected
        selected += 1
        clamp_view()
        event.app.invalidate()

    @bindings.add("pageup")
    def _(event) -> None:
        nonlocal selected
        selected -= visible_count
        clamp_view()
        event.app.invalidate()

    @bindings.add("pagedown")
    def _(event) -> None:
        nonlocal selected
        selected += visible_count
        clamp_view()
        event.app.invalidate()

    @bindings.add("delete")
    @bindings.add("backspace")
    def _(event) -> None:
        nonlocal selected
        if not items:
            event.app.invalidate()
            return
        original_index, _ = items[selected]
        if original_index in locked_indices:
            event.app.invalidate()
            return
        deleted.append(original_index)
        items.pop(selected)
        clamp_view()
        event.app.invalidate()

    @bindings.add("enter")
    @bindings.add("escape")
    @bindings.add("q")
    def _(event) -> None:
        event.app.exit(result=None)

    root = HSplit(
        [
            Frame(
                HSplit([window, toolbar], padding=0),
                title=f" {title} ",
                style="class:history-frame",
            )
        ],
        padding=0,
    )
    app = Application(
        layout=Layout(root, focused_element=window),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=False,
        style=Style.from_dict(
            {
                "history-frame": "ansimagenta",
                "selected": "reverse",
                "locked": "ansibrightblack",
                "empty": "ansibrightblack",
                "help": "ansibrightblack",
            }
        ),
    )
    app.run()
    return deleted


def help_text() -> str:
    return """Commands:
  /help              show commands
  /models            show built-in DeepSeek model names
  /history           browse context; use arrows + Delete/Backspace to drop messages
  /context           alias of /history
  /clear             clear context and prompt history
  /keep [n]          keep only last n context messages
  /drop INDEX        remove one context message
  /set INDEX text    replace one context message
  /system text       replace the system prompt
  /save [path]       save context to .agent_context.json or a custom path
  /load              load context from .agent_context.json
  /model [name]      show or change model
  /exit              quit

Tools: bash, read, write, edit."""


def print_help() -> None:
    console.print(Panel(Markdown(f"```text\n{help_text()}\n```"), title="help", border_style="magenta"))


def status(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def warn(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")
