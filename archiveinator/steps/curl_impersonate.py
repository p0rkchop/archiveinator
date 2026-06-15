"""curl-impersonate fast-path for server-side TLS/IP fingerprint blocks.

Some sites block requests at the TCP/TLS layer based on the JA3/JA4 fingerprint
of the TLS ClientHello and HTTP/2 SETTINGS frame — signatures that are
characteristic of datacenter/automated traffic regardless of JS patches applied
downstream.

curl-impersonate is a patched curl build that mimics the exact TLS handshake of
real Chrome and Firefox browsers (cipher suite ordering, extensions, GREASE
values, HTTP/2 SETTINGS frames), making requests indistinguishable from a real
browser at the network layer.

This step is a fast path: if it retrieves content successfully (HTTP 200, word
count > 150), the expensive Playwright browser launch is skipped entirely for
this bypass attempt. The fetched HTML then flows through the rest of the pipeline
normally (paywall detection, DOM cleanup, asset inlining).

Binary not found → step skips silently (no exception, no side effects).

Installation:
  - Docker: bundled in image at /usr/local/bin/curl_chrome124
  - Linux:  archiveinator setup downloads the binary
  - macOS:  not supported (no pre-built upstream binary); compile from source
            https://github.com/lwthiker/curl-impersonate
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "curl_impersonate"

# Binary names to probe in PATH order (newest Chrome impersonation first)
_BINARY_NAMES = (
    "curl_chrome124",
    "curl_chrome116",
    "curl_chrome110",
    "curl-impersonate-chrome",
)


def find_binary() -> Path | None:
    """Return the first curl-impersonate binary found in PATH, or None."""
    for name in _BINARY_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


async def run(ctx: ArchiveContext) -> None:
    """Attempt page fetch via curl-impersonate to bypass TLS fingerprint blocks.

    On success (HTTP 200 + sufficient content), sets ctx.page_html and
    ctx.final_url. Paywall detection runs after to determine if further bypass
    is needed.

    On any failure or insufficient content, exits cleanly — the bypass loop
    continues to the next strategy.
    """
    binary = find_binary()
    if binary is None:
        console.debug("curl-impersonate: binary not found in PATH, skipping")
        return

    console.step(f"Fast-path: trying curl-impersonate ({binary.name})")

    ua = ctx.ua_override or ctx.config.active_user_agent()

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = Path(f.name)

    try:
        cmd = [
            str(binary),
            "--silent",
            "--location",
            "--max-time",
            str(ctx.config.timeout_seconds),
            "--output",
            str(tmp),
            "--write-out",
            "%{http_code}",
            "--user-agent",
            ua,
        ]

        for key, value in (ctx.extra_headers or {}).items():
            if key.lower() == "referer":
                cmd += ["--referer", value]
            else:
                cmd += ["--header", f"{key}: {value}"]

        cmd.append(ctx.url)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=ctx.config.timeout_seconds + 5,
        )

        status_code_str = stdout.decode().strip()
        status_code = int(status_code_str) if status_code_str.isdigit() else 0
        ctx.response_status = status_code

        if status_code != 200:
            console.debug(f"curl-impersonate: HTTP {status_code}")
            return

        if not tmp.exists() or tmp.stat().st_size == 0:
            console.debug("curl-impersonate: empty response body")
            return

        html = tmp.read_text(encoding="utf-8", errors="replace")
        word_count = len(html.split())

        if word_count < 150:
            console.debug(f"curl-impersonate: response too short ({word_count} words), ignoring")
            return

        ctx.page_html = html
        ctx.final_url = ctx.url
        console.debug(f"curl-impersonate: fetched {word_count} words via HTTP {status_code}")

        # Run paywall detection on the fetched HTML (no live browser available here,
        # so we use a lightweight HTML-only check via BeautifulSoup)
        _detect_paywall_from_html(ctx, html)

    except TimeoutError:
        console.debug(f"curl-impersonate: timed out after {ctx.config.timeout_seconds}s")
    except Exception as exc:
        console.debug(f"curl-impersonate: unexpected error: {exc}")
    finally:
        tmp.unlink(missing_ok=True)


def _detect_paywall_from_html(ctx: ArchiveContext, html: str) -> None:
    """Lightweight HTML-only paywall detection (no live browser)."""
    from bs4 import BeautifulSoup

    from archiveinator.steps.paywall import (
        _BOT_CHALLENGE_SELECTORS,
        _BOT_CHALLENGE_TITLE_PATTERNS,
        _PAYWALL_SELECTORS,
    )
    from archiveinator.utils import word_count

    soup = BeautifulSoup(html, "html.parser")

    # Check page title for bot challenge patterns
    title_tag = soup.find("title")
    title = title_tag.get_text() if title_tag else ""
    title_lower = title.lower()
    for pattern in _BOT_CHALLENGE_TITLE_PATTERNS:
        if pattern in title_lower:
            ctx.paywalled = True
            ctx.paywall_reason = f"bot challenge title: {pattern!r}"
            return

    # Check for known bot challenge DOM selectors
    for selector in _BOT_CHALLENGE_SELECTORS:
        if soup.select(selector):
            ctx.paywalled = True
            ctx.paywall_reason = "bot challenge DOM selector"
            return

    # Check for paywall DOM selectors
    for selector in _PAYWALL_SELECTORS:
        if soup.select(selector):
            ctx.paywalled = True
            ctx.paywall_reason = "paywall DOM selector"
            return

    # Word count check
    wc = word_count(html)
    if wc < 150:
        ctx.paywalled = True
        ctx.paywall_reason = f"low word count ({wc})"
        return

    ctx.paywalled = False
