from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir, user_data_dir

CONFIG_DIR = Path(user_config_dir("archiveinator"))
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DATA_DIR = Path(user_data_dir("archiveinator"))


@dataclass
class UserAgent:
    name: str
    ua: str
    enabled: bool = True


@dataclass
class PipelineStep:
    step: str
    enabled: bool = True


@dataclass
class UserAgentConfig:
    cycle: bool = False
    agents: list[UserAgent] = field(
        default_factory=lambda: [
            UserAgent(
                name="chrome_desktop",
                ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            ),
            UserAgent(
                name="googlebot",
                ua="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                enabled=False,
            ),
            UserAgent(
                name="bingbot",
                ua="Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingcrawl.htm)",
                enabled=False,
            ),
        ]
    )


DEFAULT_PIPELINE: list[PipelineStep] = [
    PipelineStep(step="network_ad_blocking"),
    PipelineStep(step="page_load"),
    PipelineStep(step="paywall_detection"),
    PipelineStep(step="js_overlay_removal"),
    PipelineStep(step="ua_cycling"),
    PipelineStep(step="header_tricks"),
    PipelineStep(step="google_news"),
    PipelineStep(step="dom_ad_cleanup"),
    PipelineStep(step="image_dedup"),
    PipelineStep(step="content_extraction"),
    PipelineStep(step="asset_inlining"),
]


@dataclass
class Config:
    output_dir: Path = field(default_factory=lambda: Path.cwd())
    asset_size_limit_mb: int = 5
    timeout_seconds: int = 30
    blocklist_update_interval_days: int = 7
    user_agents: UserAgentConfig = field(default_factory=UserAgentConfig)
    pipeline: list[PipelineStep] = field(default_factory=lambda: list(DEFAULT_PIPELINE))

    def active_user_agent(self) -> str:
        """Return the first enabled user agent string."""
        for agent in self.user_agents.agents:
            if agent.enabled:
                return agent.ua
        raise ValueError("No enabled user agents found in config")

    def active_pipeline_steps(self) -> list[str]:
        """Return ordered list of enabled step names."""
        return [s.step for s in self.pipeline if s.enabled]


def _parse_user_agents(data: dict[str, Any]) -> UserAgentConfig:
    agents = [
        UserAgent(
            name=a["name"],
            ua=a["ua"],
            enabled=a.get("enabled", True),
        )
        for a in data.get("agents", [])
    ]
    return UserAgentConfig(
        cycle=data.get("cycle", False),
        agents=agents or UserAgentConfig().agents,
    )


def _parse_pipeline(data: list[dict[str, Any]]) -> list[PipelineStep]:
    steps = [PipelineStep(step=s["step"], enabled=s.get("enabled", True)) for s in data]
    # Hard constraints: page_load must be present
    step_names = [s.step for s in steps]
    if "page_load" not in step_names:
        raise ValueError("Pipeline must include 'page_load' step")
    # asset_inlining must be last if present
    if "asset_inlining" in step_names and step_names[-1] != "asset_inlining":
        raise ValueError("'asset_inlining' must be the last pipeline step")
    return steps


def load(path: Path = CONFIG_PATH) -> Config:
    """Load config from YAML file. Creates default config if not present."""
    if not path.exists():
        create_default(path)

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    config = Config()

    if "output_dir" in data:
        config.output_dir = Path(data["output_dir"]).expanduser()
    if "asset_size_limit_mb" in data:
        config.asset_size_limit_mb = int(data["asset_size_limit_mb"])
    if "timeout_seconds" in data:
        config.timeout_seconds = int(data["timeout_seconds"])
    if "blocklist_update_interval_days" in data:
        config.blocklist_update_interval_days = int(data["blocklist_update_interval_days"])
    if "user_agents" in data:
        config.user_agents = _parse_user_agents(data["user_agents"])
    if "pipeline" in data:
        config.pipeline = _parse_pipeline(data["pipeline"])

    return config


def create_default(path: Path = CONFIG_PATH) -> None:
    """Write the default config file to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    default_content = """\
# archiveinator configuration
# https://github.com/p0rkchop/archiveinator

# Directory where archived files are saved (default: current working directory)
output_dir: .

# Maximum asset size to inline in MB (images, CSS, fonts — videos are always skipped)
asset_size_limit_mb: 5

# Page load timeout in seconds
timeout_seconds: 30

# How often to auto-update adblock blocklists (in days)
blocklist_update_interval_days: 7

user_agents:
  cycle: false
  agents:
    - name: chrome_desktop
      enabled: true
      ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    - name: googlebot
      enabled: false
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    - name: bingbot
      enabled: false
      ua: "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingcrawl.htm)"

pipeline:
  - step: network_ad_blocking
    enabled: true
  - step: page_load
    enabled: true
  # Paywall detection runs inside page_load while the browser is still open
  - step: paywall_detection
    enabled: true
  # JS overlay removal: clears paywall modals in-page before serializing HTML
  - step: js_overlay_removal
    enabled: true
  # Bypass strategies — tried in order when paywall_detection fires
  # ua_cycling requires user_agents.cycle: true to take effect
  - step: ua_cycling
    enabled: true
  - step: header_tricks
    enabled: true
  - step: google_news
    enabled: true
  - step: dom_ad_cleanup
    enabled: true
  - step: image_dedup
    enabled: true
  # Last-resort content extraction via trafilatura (strips to article body)
  - step: content_extraction
    enabled: true
  - step: asset_inlining
    enabled: true
"""
    path.write_text(default_content)


def config_path() -> Path:
    return CONFIG_PATH


def data_dir() -> Path:
    return DATA_DIR


def monolith_bin() -> Path:
    return DATA_DIR / "bin" / "monolith"


def ua_cache_path() -> Path:
    return CONFIG_DIR / "ua_cache.yaml"
