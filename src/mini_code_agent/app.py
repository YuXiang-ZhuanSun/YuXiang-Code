from __future__ import annotations

import argparse
import sys

from .config import APP_NAME, Config
from .session import Session
from . import ui


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_stdio()
    ui.enable_ansi()

    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--model", default=None, help="model name")
    args = parser.parse_args()

    config = Config.from_env(args.root, args.model)
    session = Session(config)
    ui.header(APP_NAME, str(config.root), config.model)

    while True:
        try:
            line = ui.input_box()
            if not line:
                continue
            if session.handle_command(line):
                continue
            usage = session.run_turn(line)
            ui.usage_line(usage)
        except KeyboardInterrupt:
            print("\ninterrupted")
        except SystemExit:
            print("bye")
            return 0
        except Exception as exc:
            print(f"\nerror: {exc}", file=sys.stderr)
