from __future__ import annotations

from urllib.parse import urlparse

import yaml

from archiveinator.config import Config, ua_cache_path


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def get_cached_ua(url: str, config: Config) -> str | None:
    """Return a previously-successful UA string for this domain, if any."""
    domain = _domain(url)
    cache = _load_cache()
    ua_name = cache.get(domain, {}).get("best_ua")
    if ua_name is None:
        return None
    for agent in config.user_agents.agents:
        if agent.name == ua_name and agent.enabled:
            return agent.ua
    return None


def get_next_ua(url: str, config: Config, current_ua: str | None = None) -> str | None:
    """Return the next enabled UA to try for this domain.

    Cycles through the enabled user agents list. Returns None if cycling is
    disabled or there is only one enabled agent.
    """
    if not config.user_agents.cycle:
        return None
    enabled = [a for a in config.user_agents.agents if a.enabled]
    if len(enabled) <= 1:
        return None
    if current_ua is None:
        current_ua = config.active_user_agent()
    current_idx = next((i for i, a in enumerate(enabled) if a.ua == current_ua), -1)
    next_idx = (current_idx + 1) % len(enabled)
    return enabled[next_idx].ua


def record_success(url: str, ua_name: str) -> None:
    """Record that *ua_name* successfully bypassed the paywall for this domain."""
    domain = _domain(url)
    cache = _load_cache()
    cache.setdefault(domain, {})["best_ua"] = ua_name
    _save_cache(cache)


def _load_cache() -> dict[str, dict[str, str]]:
    path = ua_cache_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_cache(cache: dict[str, dict[str, str]]) -> None:
    path = ua_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(cache, f, default_flow_style=False)
