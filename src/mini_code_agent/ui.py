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
from prompt_toolkit.layout import HSplit, Layout
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


def help_text() -> str:
    return """Commands:
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

Tools: bash, read, write, edit."""


def print_help() -> None:
    console.print(Panel(Markdown(f"```text\n{help_text()}\n```"), title="help", border_style="magenta"))


def status(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def warn(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")
