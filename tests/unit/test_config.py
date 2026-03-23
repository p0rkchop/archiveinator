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


def test_load_pipeline_migrates_missing_steps(tmp_path: Path):
    """A config with only page_load + asset_inlining gets the missing defaults added."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: page_load
    enabled: true
  - step: asset_inlining
    enabled: true
""")
    config = load(config_file)
    steps = config.active_pipeline_steps()
    # Migration should have inserted the missing default steps
    assert "paywall_detection" in steps
    assert "js_overlay_removal" in steps
    assert "content_extraction" in steps
    # Original steps still present
    assert "page_load" in steps
    assert "asset_inlining" in steps
    # asset_inlining still last
    assert steps[-1] == "asset_inlining"


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


def test_migration_preserves_disabled_steps(tmp_path: Path):
    """Steps the user explicitly has (even disabled) are not re-added."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: network_ad_blocking
    enabled: true
  - step: page_load
    enabled: true
  - step: paywall_detection
    enabled: false
  - step: dom_ad_cleanup
    enabled: true
  - step: asset_inlining
    enabled: true
""")
    config = load(config_file)
    # paywall_detection was present but disabled — should stay disabled
    pd = next(s for s in config.pipeline if s.step == "paywall_detection")
    assert pd.enabled is False
    # Missing steps like js_overlay_removal should have been added
    step_names = [s.step for s in config.pipeline]
    assert "js_overlay_removal" in step_names
    assert "content_extraction" in step_names


def test_migration_rewrites_config_file(tmp_path: Path):
    """After migration, the config file on disk should contain the new steps."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""\
pipeline:
  - step: page_load
    enabled: true
  - step: asset_inlining
    enabled: true
""")
    load(config_file)
    # Re-read the file — it should now have the migrated steps
    updated = yaml.safe_load(config_file.read_text())
    step_names = [s["step"] for s in updated["pipeline"]]
    assert "paywall_detection" in step_names
    assert "content_extraction" in step_names
    assert step_names[-1] == "asset_inlining"


def test_no_migration_when_pipeline_is_complete(tmp_path: Path):
    """A config with all default steps should not trigger migration."""
    config_file = tmp_path / "config.yaml"
    create_default(config_file)
    original = config_file.read_text()
    load(config_file)
    # File should be unchanged
    assert config_file.read_text() == original


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
