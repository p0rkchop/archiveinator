from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

_theme = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "step": "bold blue",
        "muted": "dim",
    }
)

_console = Console(theme=_theme)
_verbose: bool = False
_debug: bool = False


def configure(verbose: bool = False, debug: bool = False, stderr: bool = False) -> None:
    global _console, _verbose, _debug
    _verbose = verbose
    _debug = debug
    if stderr:
        _console = Console(theme=_theme, stderr=True)


def info(msg: str) -> None:
    _console.print(f"[info]{msg}[/info]")


def success(msg: str) -> None:
    _console.print(f"[success]✓ {msg}[/success]")


def error(msg: str) -> None:
    _console.print(f"[error]✗ {msg}[/error]")


def warning(msg: str) -> None:
    _console.print(f"[warning]⚠ {msg}[/warning]")


def step(msg: str) -> None:
    """Print a pipeline step message — only shown in verbose mode."""
    if _verbose or _debug:
        _console.print(f"[step]→ {msg}[/step]")


def debug(msg: str) -> None:
    """Print a debug message — only shown in debug mode."""
    if _debug:
        _console.print(f"[muted][debug] {msg}[/muted]")


def is_verbose() -> bool:
    return _verbose


def is_debug() -> bool:
    return _debug
