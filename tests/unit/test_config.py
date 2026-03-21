from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from archiveinator.config import (
    Config,
    PipelineStep,
    UserAgent,
    UserAgentConfig,
    create_default,
    load,
)


def test_default_config_values():
    config = Config()
    assert config.asset_size_limit_mb == 5
    assert config.timeout_seconds == 30
    assert config.blocklist_update_interval_days == 7


def test_active_user_agent_returns_first_enabled():
    config = Config()
    config.user_agents = UserAgentConfig(
        agents=[
            UserAgent(name="a", ua="ua-a", enabled=False),
            UserAgent(name="b", ua="ua-b", enabled=True),
            UserAgent(name="c", ua="ua-c", enabled=True),
        ]
    )
    assert config.active_user_agent() == "ua-b"


def test_active_user_agent_raises_when_none_enabled():
    config = Config()
    config.user_agents = UserAgentConfig(
        agents=[
            UserAgent(name="a", ua="ua-a", enabled=False),
        ]
    )
    with pytest.raises(ValueError, match="No enabled user agents"):
        config.active_user_agent()


def test_active_pipeline_steps_returns_enabled_only():
    config = Config()
    config.pipeline = [
        PipelineStep(step="network_ad_blocking", enabled=True),
        PipelineStep(step="page_load", enabled=True),
        PipelineStep(step="dom_ad_cleanup", enabled=False),
        PipelineStep(step="asset_inlining", enabled=True),
    ]
    assert config.active_pipeline_steps() == ["network_ad_blocking", "page_load", "asset_inlining"]


def test_load_creates_default_config_when_missing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    assert not config_file.exists()
    config = load(config_file)
    assert config_file.exists()
    assert config.asset_size_limit_mb == 5


def test_load_reads_values_from_yaml(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
output_dir: /tmp/archives
asset_size_limit_mb: 10
timeout_seconds: 60
blocklist_update_interval_days: 3
""")
    config = load(config_file)
    assert config.output_dir == Path("/tmp/archives")
    assert config.asset_size_limit_mb == 10
    assert config.timeout_seconds == 60
    assert config.blocklist_update_interval_days == 3


def test_load_uses_defaults_for_missing_keys(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("timeout_seconds: 45\n")
    config = load(config_file)
    assert config.timeout_seconds == 45
    assert config.asset_size_limit_mb == 5  # default unchanged


def test_load_empty_yaml_uses_all_defaults(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    config = load(config_file)
    assert config.timeout_seconds == 30
    assert config.asset_size_limit_mb == 5


def test_load_user_agents(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
user_agents:
  cycle: true
  agents:
    - name: bot
      enabled: true
      ua: "TestBot/1.0"
""")
    config = load(config_file)
    assert config.user_agents.cycle is True
    assert len(config.user_agents.agents) == 1
    assert config.active_user_agent() == "TestBot/1.0"


def test_load_pipeline(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: page_load
    enabled: true
  - step: asset_inlining
    enabled: true
""")
    config = load(config_file)
    assert config.active_pipeline_steps() == ["page_load", "asset_inlining"]


def test_pipeline_missing_page_load_raises(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: asset_inlining
    enabled: true
""")
    with pytest.raises(ValueError, match="page_load"):
        load(config_file)


def test_pipeline_asset_inlining_not_last_raises(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: asset_inlining
    enabled: true
  - step: page_load
    enabled: true
""")
    with pytest.raises(ValueError, match="last"):
        load(config_file)


def test_create_default_writes_valid_yaml(tmp_path: Path):
    config_file = tmp_path / "subdir" / "config.yaml"
    create_default(config_file)
    assert config_file.exists()
    data = yaml.safe_load(config_file.read_text())
    assert "pipeline" in data
    assert "user_agents" in data
    assert data["asset_size_limit_mb"] == 5


def test_output_dir_expands_home(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("output_dir: ~/my_archives\n")
    config = load(config_file)
    assert not str(config.output_dir).startswith("~")
