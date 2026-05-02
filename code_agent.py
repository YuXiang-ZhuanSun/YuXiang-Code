#!/usr/bin/env python3
"""Convenience launcher for local development."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mini_code_agent.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
