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

import pytest

from tests.qa.reporter import save_result, validate_archive

# Timeout per site in seconds — generous to accommodate slow pages + monolith
_ARCHIVE_TIMEOUT = 180


@pytest.mark.real_url
def test_archive_site(qa_site: dict, tmp_path: pytest.TempPathFactory) -> None:
    """Archive a live site and validate the output."""
    site_name = qa_site["name"]
    url = qa_site["url"]
    tags = qa_site.get("tags", {})

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
                f"{site_name} ({tags.get('difficulty', '?')}): "
                f"{'; '.join(result.failure_reasons)}"
            )
