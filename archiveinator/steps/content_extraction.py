from __future__ import annotations

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "content_extraction"

_FALLBACK_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
    article {{ line-height: 1.7; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <article>
    {body}
  </article>
  <footer style="margin-top:2rem;color:#888;font-size:.85em">
    Extracted from: <a href="{url}">{url}</a>
  </footer>
</body>
</html>"""


class ContentExtractionError(Exception):
    pass


async def run(ctx: ArchiveContext) -> None:
    """Extract article body from ctx.page_html using trafilatura.

    On success, replaces ctx.page_html with a clean self-contained HTML
    document containing only the article body and clears ctx.paywalled so
    downstream steps treat it as a full archive.

    Raises ContentExtractionError if trafilatura cannot extract any content.
    """
    try:
        import trafilatura
    except ImportError as exc:
        raise ContentExtractionError("trafilatura is not installed") from exc

    html = ctx.page_html or ""
    if not html:
        raise ContentExtractionError("No HTML to extract from")

    console.step("Content extraction: running trafilatura")

    extracted = trafilatura.extract(
        html,
        output_format="html",
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )

    if not extracted:
        raise ContentExtractionError("trafilatura could not extract article content")

    # Reject extractions that are too short to be real article content.
    # Cloudflare / bot-challenge pages produce a handful of words (e.g. "Just a
    # moment... Checking your browser...") that trafilatura happily returns.
    # A legitimate article should have at least 50 plain-text words.
    import re as _re

    plain_text = _re.sub(r"<[^>]+>", " ", extracted)
    word_count = len(plain_text.split())
    if word_count < 50:
        raise ContentExtractionError(
            f"extracted content too short ({word_count} words) — likely a challenge page"
        )

    title = ctx.page_title or ""
    url = ctx.final_url or ctx.url
    ctx.page_html = _FALLBACK_TEMPLATE.format(
        title=title,
        body=extracted,
        url=url,
    )
    ctx.paywalled = False
    ctx.bypass_method = "content_extraction"
    ctx.log(STEP, f"extracted article content via trafilatura ({len(extracted)} chars)")
    console.step("Content extraction: article body extracted")
