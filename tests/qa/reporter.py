"""QA reporter — archive validation and rich table summary.

Provides:
    validate_archive()  — checks an archived HTML file against QA criteria
    QAResult            — dataclass holding per-site test results
    print_summary()     — renders a rich table of all results
    pytest hooks        — wires the summary into pytest_terminal_summary
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Bot challenge / paywall selectors to scan for in the saved HTML.
# Mirrors the lists in archiveinator/steps/paywall.py — kept flat here
# so the QA suite has no import dependency on the application code.
_BLOCK_PATTERNS: list[str] = [
    # PerimeterX
    'id="px-captcha"',
    'id="px-loader"',
    # Cloudflare
    'id="challenge-form"',
    "cf-browser-verification",
    # Akamai
    'id="ak_bmsc"',
    # DataDome
    'id="datadome-captcha"',
    # Piano / TinyPass
    "tp-modal",
    "tp-container",
    "tp-backdrop",
    "piano-offer",
    # Generic paywall
    "paywall",
    "content-gate",
    "subscription-wall",
    "regwall",
]

# Title patterns that indicate a bot page rather than a real article.
_BOT_TITLE_PATTERNS: list[str] = [
    "are you a robot",
    "just a moment",
    "attention required",
    "access denied",
    "ddos protection",
    "security check",
    "robot check",
]

MIN_WORD_COUNT = 300


@dataclass
class QAResult:
    """Outcome of a single QA site test."""

    site_name: str
    category: str = ""
    difficulty: str = ""
    paywall_type: str = ""
    passed: bool = False
    word_count: int = 0
    bypass_method: str = ""
    failure_reasons: list[str] = field(default_factory=list)
    output_file: str = ""


# Module-level list that tests append results to; printed at end of session.
results: list[QAResult] = []


def _extract_text(html: str) -> str:
    """Rough text extraction — strip tags, collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_title(html: str) -> str:
    """Pull the <title> content from raw HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return m.group(1).strip() if m else ""


def validate_archive(
    output_dir: Path,
    *,
    site_name: str = "",
    difficulty: str = "",
) -> QAResult:
    """Validate an archived HTML file against QA criteria.

    Looks for the newest .html file in *output_dir* and checks:
      1. No ``_partial`` in filename
      2. Word count >= MIN_WORD_COUNT
      3. No bot/paywall selectors in the saved HTML
      4. No bot-challenge title pattern
    """
    result = QAResult(site_name=site_name, difficulty=difficulty)

    # Find the newest HTML file in the output directory
    html_files = sorted(output_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not html_files:
        result.failure_reasons.append("no output file produced")
        return result

    archive = html_files[0]
    result.output_file = archive.name

    # 1. No _partial suffix
    if "_partial" in archive.name:
        result.failure_reasons.append("partial archive (_partial in filename)")

    html = archive.read_text(encoding="utf-8", errors="replace")

    # 2. Word count
    text = _extract_text(html)
    result.word_count = len(text.split())
    if result.word_count < MIN_WORD_COUNT:
        result.failure_reasons.append(f"word count too low ({result.word_count} < {MIN_WORD_COUNT})")

    # 3. Bot/paywall selectors in HTML
    html_lower = html.lower()
    for pattern in _BLOCK_PATTERNS:
        if pattern.lower() in html_lower:
            result.failure_reasons.append(f"block pattern found: {pattern}")
            break

    # 4. Bot-challenge title
    title = _extract_title(html).lower()
    for pat in _BOT_TITLE_PATTERNS:
        if pat in title:
            result.failure_reasons.append(f"bot challenge title: {title!r}")
            break

    result.passed = len(result.failure_reasons) == 0
    return result


def print_summary(console: Console | None = None) -> None:
    """Render a rich table summarising all QA results collected so far."""
    if not results:
        return

    con = console or Console()
    table = Table(title="QA — Paywall Bypass Results", show_lines=True)
    table.add_column("Site", style="bold", min_width=20)
    table.add_column("Category")
    table.add_column("Difficulty")
    table.add_column("Type")
    table.add_column("Words", justify="right")
    table.add_column("Result")
    table.add_column("Details", max_width=50)

    passed = 0
    failed = 0
    for r in results:
        if r.passed:
            passed += 1
            result_str = "[green]PASS[/green]"
            detail = ""
        else:
            failed += 1
            result_str = "[red]FAIL[/red]"
            detail = "; ".join(r.failure_reasons)

        table.add_row(
            r.site_name,
            r.category,
            r.difficulty,
            r.paywall_type,
            str(r.word_count),
            result_str,
            detail,
        )

    con.print()
    con.print(table)
    con.print(f"\n[bold]{passed} passed[/bold], [bold]{failed} failed[/bold]")
