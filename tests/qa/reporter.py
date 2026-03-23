"""QA reporter — archive validation and rich table summary.

Provides:
    validate_archive()  — checks an archived HTML file against QA criteria
    QAResult            — dataclass holding per-site test results
    print_summary()     — renders a rich table of all results
    pytest hooks        — wires the summary into pytest_terminal_summary
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Bot challenge / paywall selectors to scan for in the saved HTML.
# Mirrors the lists in archiveinator/steps/paywall.py — kept flat here
# so the QA suite has no import dependency on the application code.

# Patterns that already include attribute context — safe for substring match.
_EXACT_BLOCK_PATTERNS: list[str] = [
    'id="px-captcha"',
    'id="px-loader"',
    'id="challenge-form"',
    'id="ak_bmsc"',
    'id="datadome-captcha"',
]

# Patterns checked only inside class/id attributes to avoid false positives
# on articles that merely *discuss* paywalls or bot detection.
_ATTRIBUTE_BLOCK_PATTERNS: list[str] = [
    "cf-browser-verification",
    "tp-modal",
    "tp-container",
    "tp-backdrop",
    "piano-offer",
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

# Directory for persisting results across xdist workers (set by conftest).
_results_dir: Path | None = None


def set_results_dir(path: Path) -> None:
    """Set the shared directory for persisting QA results across workers."""
    global _results_dir
    _results_dir = path
    path.mkdir(parents=True, exist_ok=True)


def save_result(result: QAResult) -> None:
    """Append result to in-memory list and persist to disk for xdist collection."""
    results.append(result)
    if _results_dir is not None:
        dest = _results_dir / f"{result.site_name.replace(' ', '_').replace('/', '_')}.json"
        dest.write_text(json.dumps(asdict(result)), encoding="utf-8")


def collect_results() -> list[QAResult]:
    """Collect all persisted results from disk (for xdist controller)."""
    if _results_dir is None or not _results_dir.exists():
        return results
    all_results: list[QAResult] = []
    for f in sorted(_results_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        all_results.append(QAResult(**data))
    return all_results or results


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
    found_block = False
    # 3a. Exact attribute patterns — specific enough for substring match
    for pattern in _EXACT_BLOCK_PATTERNS:
        if pattern.lower() in html_lower:
            result.failure_reasons.append(f"block pattern found: {pattern}")
            found_block = True
            break
    # 3b. Generic terms — only flag if they appear in a class="" or id="" attribute,
    #     not in article body text (avoids false positives on articles about paywalls)
    if not found_block:
        for pattern in _ATTRIBUTE_BLOCK_PATTERNS:
            attr_re = re.compile(
                rf'(?:class|id)\s*=\s*["\'][^"\']*{re.escape(pattern)}[^"\']*["\']',
                re.IGNORECASE,
            )
            if attr_re.search(html):
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
    all_results = collect_results()
    if not all_results:
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
    for r in all_results:
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
