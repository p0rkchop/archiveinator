from __future__ import annotations

import sys
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
    PipelineStep(step="stealth_browser"),
    PipelineStep(step="ua_cycling"),
    PipelineStep(step="header_tricks"),
    PipelineStep(step="google_news"),
    PipelineStep(step="dom_ad_cleanup"),
    PipelineStep(step="image_dedup"),
    PipelineStep(step="content_extraction"),
    PipelineStep(step="archive_fallback"),
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


def _migrate_pipeline(steps: list[PipelineStep], path: Path) -> list[PipelineStep]:
    """Insert any default pipeline steps missing from the user's config.

    When new steps are added to DEFAULT_PIPELINE, existing config files lack
    them.  This inserts each missing step at the correct position relative to
    the steps that *are* present, then rewrites the config file so the change
    is visible and persistent.
    """
    user_step_names = {s.step for s in steps}
    default_names = [s.step for s in DEFAULT_PIPELINE]
    missing = [s for s in DEFAULT_PIPELINE if s.step not in user_step_names]

    if not missing:
        return steps

    merged = list(steps)
    for new_step in missing:
        # Find the correct insertion point: right after the last existing step
        # that precedes this one in the default order.
        default_idx = default_names.index(new_step.step)
        preceding = default_names[:default_idx]
        insert_at = 0
        for i, s in enumerate(merged):
            if s.step in preceding:
                insert_at = i + 1
        merged.insert(insert_at, PipelineStep(step=new_step.step, enabled=True))

    added = [s.step for s in missing]
    print(
        f"Config migration: added pipeline steps {added} — edit {path} to customise.",
        file=sys.stderr,
    )

    # Rewrite the pipeline section of the config file on disk.
    _rewrite_pipeline_in_config(merged, path)

    return merged


def _rewrite_pipeline_in_config(steps: list[PipelineStep], path: Path) -> None:
    """Rewrite only the pipeline section of the YAML config on disk."""
    if not path.exists():
        return

    lines = path.read_text().splitlines(keepends=True)
    # Find the pipeline section and replace it
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.rstrip() == "pipeline:":
            start = i
        elif start is not None and line and not line[0].isspace() and line[0] != "#":
            end = i
            break

    if start is None:
        # No pipeline section — append one
        new_lines = lines + ["\npipeline:\n"] + _pipeline_yaml_lines(steps)
    else:
        new_lines = lines[:start] + ["pipeline:\n"] + _pipeline_yaml_lines(steps) + lines[end:]

    path.write_text("".join(new_lines))


def _pipeline_yaml_lines(steps: list[PipelineStep]) -> list[str]:
    """Generate YAML lines for the pipeline section."""
    lines: list[str] = []
    for s in steps:
        lines.append(f"  - step: {s.step}\n")
        lines.append(f"    enabled: {'true' if s.enabled else 'false'}\n")
    return lines


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
        config.pipeline = _migrate_pipeline(_parse_pipeline(data["pipeline"]), path)

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
  # Stealth browser: retries page load with anti-fingerprinting patches
  # Effective against Cloudflare "Just a moment" and DataDome challenges
  - step: stealth_browser
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
  # Archive service fallback: try Wayback Machine when all else fails
  - step: archive_fallback
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
