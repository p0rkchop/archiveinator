from __future__ import annotations

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "google_news"

# Googlebot's documented IP range (used as X-Forwarded-For to reinforce the illusion)
_GOOGLEBOT_IP = "66.249.66.1"
_GOOGLE_NEWS_REFERER = "https://news.google.com/"


async def run(ctx: ArchiveContext) -> None:
    """Configure headers to simulate a visit referred from Google News.

    Many publishers allow Googlebot/Google-referred traffic through their
    paywalls so that articles remain indexed. This step sets the Referer and
    X-Forwarded-For headers accordingly and switches to the Googlebot UA if one
    is configured, then lets page_load re-run with those overrides in place.
    """
    # Prefer the configured Googlebot UA; fall back to whatever is active.
    googlebot_ua: str | None = None
    for agent in ctx.config.user_agents.agents:
        if agent.name == "googlebot":
            googlebot_ua = agent.ua
            break

    if googlebot_ua:
        ctx.ua_override = googlebot_ua
        console.step("Google News bypass: using Googlebot UA")
    else:
        console.step("Google News bypass: no Googlebot UA configured, using current UA")

    ctx.extra_headers["Referer"] = _GOOGLE_NEWS_REFERER
    ctx.extra_headers["X-Forwarded-For"] = _GOOGLEBOT_IP
