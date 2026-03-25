"""Archive service fallback: fetch from Wayback Machine or archive.today when bypass fails.

Last-resort strategy — when all other bypass methods are exhausted, check
if the Wayback Machine or archive.today has an archived copy of the page
and use that instead.
"""

from __future__ import annotations

import httpx

from archiveinator import console

STEP = "archive_fallback"

_WAYBACK_API = "https://archive.org/wayback/available"
_TIMEOUT = 15


async def check_wayback(url: str) -> str | None:
    """Check the Wayback Machine for an archived snapshot of the URL.

    Returns the snapshot URL if available, or None.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_WAYBACK_API, params={"url": url})
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as e:
        console.debug(f"Wayback API request failed: {e}")
        return None

    snapshot = data.get("archived_snapshots", {}).get("closest")
    if snapshot and snapshot.get("available"):
        snapshot_url: str = snapshot.get("url", "")
        if snapshot_url:
            console.debug(f"Wayback snapshot found: {snapshot_url}")
            return snapshot_url

    console.debug("No Wayback snapshot available")
    return None


async def check_archive_today(url: str) -> str | None:
    """Check archive.today for an archived snapshot of the URL.

    Requests ``https://archive.ph/newest/{url}`` with redirects enabled.
    If the service redirects to an actual archived page (i.e. the final URL
    differs from the request URL), the archived page URL is returned.
    Returns None on 404 or any error.
    """
    request_url = f"https://archive.ph/newest/{url}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
            resp = await client.get(request_url)
    except httpx.HTTPError as e:
        console.debug(f"archive.today request failed: {e}")
        return None

    if resp.status_code != 200:
        console.debug(f"archive.today returned status {resp.status_code}")
        return None

    final_url = str(resp.url)
    if final_url == request_url:
        console.debug("archive.today did not redirect — no archived copy found")
        return None

    console.debug(f"archive.today snapshot found: {final_url}")
    return final_url
