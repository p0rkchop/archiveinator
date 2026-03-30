from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from archiveinator import console
from archiveinator.config import monolith_bin
from archiveinator.pipeline import ArchiveContext

STEP = "asset_inlining"


class AssetInliningError(Exception):
    pass


def check_monolith() -> Path:
    """Return monolith binary path, raising a helpful error if not installed."""
    bin_path = monolith_bin()
    if not bin_path.exists():
        raise AssetInliningError(
            f"monolith binary not found at {bin_path}. Run 'archiveinator setup' to install it."
        )
    return bin_path


async def run(ctx: ArchiveContext) -> None:
    """Inline all assets into a single self-contained HTML file using monolith."""
    if ctx.page_html is None:
        raise AssetInliningError("No page HTML — page_load must run before asset_inlining")

    bin_path = check_monolith()
    base_url = ctx.final_url or ctx.url
    inlining_timeout = max(60, ctx.config.timeout_seconds * 1.5)  # Minimum 60s, max 1.5x page timeout

    console.step("Inlining assets with monolith")
    console.debug(f"base_url={base_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        input_file = tmp / "input.html"
        output_file = tmp / "output.html"

        input_file.write_text(ctx.page_html, encoding="utf-8")

        # Sites requiring a bypass often sit behind Cloudflare or similar CDN
        # protection that also blocks non-browser asset fetches.  Monolith
        # (no JS engine) hits the same wall, times out, and turns a successful
        # bypass into a _partial save.  When any bypass was used, suppress ALL
        # external asset fetching so monolith completes quickly with inline text.
        # Also suppress when paywall was detected but not cleared (e.g., NYT 403),
        # because external assets are likely blocked as well.
        extra_flags: list[str] = []
        if ctx.bypass_method is not None or ctx.paywalled:
            extra_flags.extend(["--no-images", "--no-css", "--no-fonts", "--no-frames", "--no-js"])
            reason = ctx.bypass_method or "paywall detected"
            console.debug(
                f"{reason}: suppressing external asset fetching in monolith"
            )

        try:
            result = subprocess.run(
                [
                    str(bin_path),
                    str(input_file),
                    "--base-url",
                    base_url,
                    "--no-audio",
                    "--no-video",
                    "--isolate",
                    "--insecure",
                    "--quiet",
                    *extra_flags,
                    "-o",
                    str(output_file),
                ],
                capture_output=True,
                timeout=inlining_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssetInliningError(f"monolith timed out after {inlining_timeout}s") from exc

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise AssetInliningError(f"monolith exited {result.returncode}: {stderr}")

        if not output_file.exists():
            raise AssetInliningError("monolith produced no output file")

        ctx.page_html = output_file.read_text(encoding="utf-8")
        ctx.log(STEP, f"inlined {len(ctx.page_html):,} bytes")
        console.step(f"Assets inlined ({len(ctx.page_html):,} bytes)")
