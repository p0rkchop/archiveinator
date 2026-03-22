from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from archiveinator import ua_manager
from archiveinator.config import Config, UserAgent, UserAgentConfig


def _config_with_cycle(agents: list[UserAgent], cycle: bool = True) -> Config:
    cfg = Config()
    cfg.user_agents = UserAgentConfig(cycle=cycle, agents=agents)
    return cfg


_UA_CHROME = UserAgent(name="chrome", ua="Mozilla/5.0 Chrome", enabled=True)
_UA_GOOGLEBOT = UserAgent(name="googlebot", ua="Googlebot/2.1", enabled=True)
_UA_BING = UserAgent(name="bingbot", ua="Bingbot/2.0", enabled=True)


# --- get_next_ua ---


def test_get_next_ua_returns_none_when_cycling_disabled() -> None:
    cfg = _config_with_cycle([_UA_CHROME, _UA_GOOGLEBOT], cycle=False)
    assert ua_manager.get_next_ua("https://example.com", cfg) is None


def test_get_next_ua_returns_none_with_single_agent() -> None:
    cfg = _config_with_cycle([_UA_CHROME])
    assert ua_manager.get_next_ua("https://example.com", cfg) is None


def test_get_next_ua_cycles_to_next() -> None:
    cfg = _config_with_cycle([_UA_CHROME, _UA_GOOGLEBOT])
    nxt = ua_manager.get_next_ua("https://example.com", cfg, current_ua=_UA_CHROME.ua)
    assert nxt == _UA_GOOGLEBOT.ua


def test_get_next_ua_wraps_around() -> None:
    cfg = _config_with_cycle([_UA_CHROME, _UA_GOOGLEBOT])
    nxt = ua_manager.get_next_ua("https://example.com", cfg, current_ua=_UA_GOOGLEBOT.ua)
    assert nxt == _UA_CHROME.ua


def test_get_next_ua_skips_disabled_agents() -> None:
    disabled = UserAgent(name="disabled", ua="Disabled/1.0", enabled=False)
    cfg = _config_with_cycle([_UA_CHROME, disabled, _UA_GOOGLEBOT])
    nxt = ua_manager.get_next_ua("https://example.com", cfg, current_ua=_UA_CHROME.ua)
    assert nxt == _UA_GOOGLEBOT.ua


# --- record_success / get_cached_ua ---


def test_record_and_retrieve_cached_ua(tmp_path: Path) -> None:
    cache_file = tmp_path / "ua_cache.yaml"
    cfg = _config_with_cycle([_UA_CHROME, _UA_GOOGLEBOT])

    with patch("archiveinator.ua_manager.ua_cache_path", return_value=cache_file):
        ua_manager.record_success("https://nytimes.com/article", "googlebot")
        cached = ua_manager.get_cached_ua("https://nytimes.com/other", cfg)

    assert cached == _UA_GOOGLEBOT.ua


def test_cached_ua_returns_none_when_no_cache(tmp_path: Path) -> None:
    cache_file = tmp_path / "ua_cache.yaml"
    cfg = _config_with_cycle([_UA_CHROME])

    with patch("archiveinator.ua_manager.ua_cache_path", return_value=cache_file):
        result = ua_manager.get_cached_ua("https://example.com", cfg)

    assert result is None


def test_cached_ua_returns_none_for_unknown_agent_name(tmp_path: Path) -> None:
    cache_file = tmp_path / "ua_cache.yaml"
    cfg = _config_with_cycle([_UA_CHROME])

    with patch("archiveinator.ua_manager.ua_cache_path", return_value=cache_file):
        ua_manager.record_success("https://example.com", "nonexistent_agent")
        result = ua_manager.get_cached_ua("https://example.com", cfg)

    assert result is None
