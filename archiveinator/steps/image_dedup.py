from __future__ import annotations

import contextlib

from bs4 import BeautifulSoup, Tag

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "image_dedup"

# Select the largest srcset variant up to this width.
# If all variants exceed this, use the smallest available.
MAX_WIDTH = 1200


def _parse_srcset(srcset: str) -> list[tuple[str, int]]:
    """Parse a srcset string into (url, width) pairs.

    Width is 0 for density descriptors (1x, 2x) or entries with no descriptor.
    """
    entries: list[tuple[str, int]] = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        url = tokens[0]
        width = 0
        if len(tokens) > 1:
            descriptor = tokens[1]
            if descriptor.endswith("w"):
                with contextlib.suppress(ValueError):
                    width = int(descriptor[:-1])
        entries.append((url, width))
    return entries


def _best_url(srcset: str) -> str | None:
    """Return the single best image URL from a srcset string."""
    entries = _parse_srcset(srcset)
    if not entries:
        return None

    widths = [(url, w) for url, w in entries if w > 0]
    if widths:
        under = [(url, w) for url, w in widths if w <= MAX_WIDTH]
        if under:
            return max(under, key=lambda x: x[1])[0]
        return min(widths, key=lambda x: x[1])[0]

    # No width descriptors — take the last entry (conventionally highest quality)
    return entries[-1][0]


def _collapse_picture(tag: Tag) -> None:
    """Replace a <picture> element with a single <img>, choosing the best source."""
    img_el = tag.find("img")
    if not isinstance(img_el, Tag):
        return

    # Try to find a better URL from <source> elements
    best: str | None = None
    for source in tag.find_all("source"):
        if not isinstance(source, Tag):
            continue
        srcset_val = source.get("srcset")
        if isinstance(srcset_val, str) and srcset_val:
            candidate = _best_url(srcset_val)
            if candidate:
                best = candidate  # last valid source wins

    if best:
        img_el["src"] = best

    # Remove srcset from the img — we've chosen a single source
    if img_el.get("srcset"):
        del img_el["srcset"]

    tag.replace_with(img_el)


def _resolve_srcset(tag: Tag) -> None:
    """Collapse srcset on a standalone <img> to a single src."""
    srcset_val = tag.get("srcset")
    if not isinstance(srcset_val, str) or not srcset_val:
        return

    best = _best_url(srcset_val)
    if best:
        tag["src"] = best
    del tag["srcset"]


async def run(ctx: ArchiveContext) -> None:
    """Collapse responsive image markup to a single URL per image."""
    if ctx.page_html is None:
        return

    soup = BeautifulSoup(ctx.page_html, "html.parser")

    pictures_collapsed = 0
    srcsets_resolved = 0

    for picture in soup.find_all("picture"):
        if isinstance(picture, Tag):
            _collapse_picture(picture)
            pictures_collapsed += 1

    for img in soup.find_all("img", srcset=True):
        if isinstance(img, Tag):
            _resolve_srcset(img)
            srcsets_resolved += 1

    ctx.page_html = str(soup)
    ctx.log(STEP, f"collapsed {pictures_collapsed} picture, resolved {srcsets_resolved} srcset")
    console.step(
        f"Image dedup: {pictures_collapsed} picture elements, {srcsets_resolved} srcset attributes"
    )
