"""Real-URL paywall bypass tests.

Each test archives a live site and validates the output against QA criteria.
Parametrised dynamically from sites.yaml via conftest.pytest_generate_tests.

Invoked via subprocess to mirror the exact end-user experience:
    archiveinator archive <url> --output-dir <tmp> --verbose

Usage:
    pytest tests/qa/test_real_urls.py -m real_url --qa-sample 10 -n auto -v
    pytest tests/qa/test_real_urls.py -m real_url --qa-difficulty easy -n 3 -v
    pytest tests/qa/test_real_urls.py -m real_url --qa-paywall-type piano -v
    pytest tests/qa/test_real_urls.py -m real_url --qa-category finance -v

Use ``-n auto`` (or ``-n N``) for parallel execution via pytest-xdist.
Results are persisted to disk so the summary table works across workers.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.qa.reporter import MIN_WORD_COUNT, QAResult, save_result, validate_archive
from tests.qa.rss_resolver import resolve_article_urls, resolve_site_url


def _run_archive(url: str, tmp_path: Path, site_name: str, tags: dict[str, str]) -> QAResult:
    """Run archiveinator on url and return validation result."""
    # Run archiveinator as a subprocess — mirrors end-user experience
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "archiveinator",
            "archive",
            url,
            "--output-dir",
            str(tmp_path),
            "--verbose",
        ],
        capture_output=True,
        text=True,
        timeout=_ARCHIVE_TIMEOUT,
    )

    # Validate the archive
    result = validate_archive(
        tmp_path,
        site_name=site_name,
        difficulty=tags.get("difficulty", ""),
    )
    result.category = tags.get("category", "")
    result.paywall_type = tags.get("paywall_type", "")

    # Extract bypass method from verbose output
    output = proc.stdout + proc.stderr
    for method in [
        "js_overlay_removal",
        "ua_cycling",
        "header_tricks",
        "google_news",
        "content_extraction",
    ]:
        if (method.replace("_", " ") in output.lower() or method in output.lower()) and (
            "bypassed" in output.lower() or "bypass" in output.lower()
        ):
            result.bypass_method = method
            break

    return result


# Timeout per site in seconds — generous to accommodate slow pages + monolith
_ARCHIVE_TIMEOUT = 180


@pytest.mark.real_url
def test_archive_site(qa_site: dict[str, Any], tmp_path: Path) -> None:
    """Archive a live site and validate the output."""
    site_name = qa_site["name"]
    tags = qa_site.get("tags", {})

    # Determine the initial URL (RSS feed article or fallback)
    primary_url = resolve_site_url(qa_site)
    result = _run_archive(primary_url, tmp_path, site_name, tags)

    # If primary article is too short and we have an RSS feed, try alternate articles
    if result.word_count < MIN_WORD_COUNT and qa_site.get("rss_feed"):
        for alt_url in resolve_article_urls(qa_site["rss_feed"], max_articles=5)[
            1:
        ]:  # skip first (already tried)
            if alt_url == primary_url:
                continue
            alt_result = _run_archive(alt_url, tmp_path, site_name, tags)
            if alt_result.word_count >= MIN_WORD_COUNT:
                result = alt_result
                break

    # Persist result for summary table (works across xdist workers)
    save_result(result)

    # For easy/no-paywall sites, expect a clean pass
    if tags.get("difficulty") == "easy":
        assert result.passed, (
            f"{site_name}: expected clean archive for easy site, "
            f"got: {'; '.join(result.failure_reasons)}"
        )
    else:
        # For medium/hard sites, record the result but only hard-fail on
        # catastrophic issues (no output at all)
        if not result.output_file:
            pytest.fail(f"{site_name}: no output file produced at all")
        if not result.passed:
            pytest.xfail(
                f"{site_name} ({tags.get('difficulty', '?')}): {'; '.join(result.failure_reasons)}"
            )
