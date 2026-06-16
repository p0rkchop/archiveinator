"""FlareSolverr integration for Cloudflare IUAM/Turnstile challenge bypass.

FlareSolverr is a self-hosted Docker sidecar that solves Cloudflare challenges
using a real browser session and returns the resulting cf_clearance cookie.
Injecting this cookie into a subsequent page load bypasses Cloudflare for the
session.

This step is a no-op when:
- ctx.config.flaresolverr_url is None (default — feature is opt-in)
- The FlareSolverr service is not reachable at the configured URL

Enable by setting flaresolverr_url in config.yaml or the FLARESOLVERR_URL
environment variable:

    flaresolverr_url: "http://localhost:8191/v1"

Docker Compose example:

    services:
      archiveinator:
        image: ghcr.io/p0rkchop/archiveinator:latest
        environment:
          - FLARESOLVERR_URL=http://flaresolverr:8191/v1
      flaresolverr:
        image: ghcr.io/flaresolverr/flaresolverr:latest
"""

from __future__ import annotations

import os

import httpx

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "flaresolverr"
_DEFAULT_URL = "http://localhost:8191/v1"
_AVAILABILITY_TIMEOUT = 2.0


def _get_flaresolverr_url(ctx: ArchiveContext) -> str | None:
    """Return the FlareSolverr URL from config or FLARESOLVERR_URL env var."""
    url = getattr(ctx.config, "flaresolverr_url", None)
    if not url:
        url = os.environ.get("FLARESOLVERR_URL")
    return url or None


async def _is_available(url: str) -> bool:
    """Return True if FlareSolverr is reachable."""
    health_url = url.replace("/v1", "") + "/health"
    try:
        async with httpx.AsyncClient(timeout=_AVAILABILITY_TIMEOUT) as client:
            resp = await client.get(health_url)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def run(ctx: ArchiveContext) -> None:
    """Obtain cf_clearance cookie from FlareSolverr and inject into ctx.cookies.

    On success, ctx.cookies is updated with the Cloudflare session cookies and
    ctx.ua_override is set to FlareSolverr's solved user agent. The caller
    (bypass loop) then reloads the page with the injected cookies.

    On any failure (service unavailable, solve timeout, bad response), the step
    exits silently so the bypass loop can try the next strategy.
    """
    fs_url = _get_flaresolverr_url(ctx)
    if not fs_url:
        console.debug("FlareSolverr: no URL configured (set flaresolverr_url or FLARESOLVERR_URL)")
        return

    if not await _is_available(fs_url):
        console.debug(f"FlareSolverr: service not available at {fs_url}")
        return

    console.step(f"Requesting Cloudflare solution from FlareSolverr at {fs_url}")

    timeout = ctx.config.timeout_seconds + 15
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                fs_url,
                json={
                    "cmd": "request.get",
                    "url": ctx.url,
                    "maxTimeout": ctx.config.timeout_seconds * 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        console.debug(f"FlareSolverr: request failed: {exc}")
        return

    if data.get("status") != "ok":
        console.debug(f"FlareSolverr: non-ok status: {data.get('status')!r}")
        return

    solution = data.get("solution", {})
    new_cookies = solution.get("cookies", [])
    solved_ua = solution.get("userAgent")

    if new_cookies:
        ctx.cookies = list(ctx.cookies or []) + new_cookies
        console.debug(f"FlareSolverr: injected {len(new_cookies)} cookie(s)")

    if solved_ua:
        ctx.ua_override = solved_ua
        console.debug(f"FlareSolverr: using solved UA: {solved_ua[:60]}...")
