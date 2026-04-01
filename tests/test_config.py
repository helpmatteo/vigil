from pathlib import Path

import pytest
import yaml

from vigil.config import (
    Config,
    DEFAULT_LOG_COMMAND,
    DEFAULT_LOG_DIR,
    DEFAULT_METRIC_PATTERNS,
    InstanceConfig,
    load_config,
)


def test_default_config():
    config = Config()
    assert config.api_key == ""
    assert config.poll_interval == 30
    assert config.log_dir == DEFAULT_LOG_DIR
    assert config.default_log_command == DEFAULT_LOG_COMMAND
    assert config.ssh_key_path == Path.home() / ".ssh" / "id_vastai"
    assert config.instances == {}
    assert config.metric_patterns == DEFAULT_METRIC_PATTERNS
    assert config.stall_threshold_minutes == 5
    assert config.plateau_window == 8
    assert config.plateau_threshold == 1e-4
    assert config.sparkline_history == 60
    assert config.desktop_notifications is True
    assert config.alert_webhook_url is None
    assert config.highlight_logs is False


def test_stall_threshold_for_default():
    config = Config()
    assert config.stall_threshold_for(12345) == 5


def test_stall_threshold_for_override():
    config = Config()
    config.instances["42"] = InstanceConfig(stall_threshold_minutes=15)
    assert config.stall_threshold_for(42) == 15
    assert config.stall_threshold_for(99) == 5


def test_load_config_missing_file():
    config = load_config(config_path=Path("/tmp/nonexistent_vast_config.yaml"))
    assert isinstance(config, Config)
    assert config.poll_interval == 30
    assert config.stall_threshold_minutes == 5
    assert config.metric_patterns == DEFAULT_METRIC_PATTERNS


def test_load_config_yaml_scalars(tmp_path: Path, monkeypatch):
    """load_config correctly reads scalar fields from YAML."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "vast_api_key": "test-key-123",
        "poll_interval": 15,
        "stall_threshold_minutes": 10,
        "plateau_window": 12,
        "plateau_threshold": 0.001,
        "sparkline_history": 100,
        "highlight_logs": True,
        "ssh_username": "myuser",
        "max_grid_columns": 4,
        "log_buffer_lines": 3000,
        "log_display_lines": 1000,
        "ssh_login_timeout": 20,
        "ssh_keepalive_interval": 30,
        "reconnect_backoff_max": 120,
        "log_retention_days": 7,
        "log_max_size_mb": 500,
        "alert_webhook_url": "https://hooks.example.com/test",
        "alert_webhook_format": "slack",
    }))

    config = load_config(config_path=cfg_path)

    assert config.api_key == "test-key-123"
    assert config.poll_interval == 15
    assert config.stall_threshold_minutes == 10
    assert config.plateau_window == 12
    assert abs(config.plateau_threshold - 0.001) < 1e-9
    assert config.sparkline_history == 100
    assert config.highlight_logs is True
    assert config.ssh_username == "myuser"
    assert config.max_grid_columns == 4
    assert config.log_buffer_lines == 3000
    assert config.log_display_lines == 1000
    assert config.ssh_login_timeout == 20
    assert config.ssh_keepalive_interval == 30
    assert config.reconnect_backoff_max == 120
    assert config.log_retention_days == 7
    assert config.log_max_size_mb == 500
    assert config.alert_webhook_url == "https://hooks.example.com/test"
    assert config.alert_webhook_format == "slack"


def test_load_config_extra_metric_patterns(tmp_path: Path, monkeypatch):
    """extra_metric_patterns are appended to default metric_patterns."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    extras = [r"custom_loss[:\s=]+(?P<custom_loss>[\d.]+)"]
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"extra_metric_patterns": extras}))

    config = load_config(config_path=cfg_path)

    assert config.extra_metric_patterns == extras
    assert config.metric_patterns == DEFAULT_METRIC_PATTERNS + extras


def test_load_config_explicit_metric_patterns(tmp_path: Path, monkeypatch):
    """Explicit metric_patterns replaces defaults entirely."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    patterns = [r"my_metric=(?P<my_metric>[\d.]+)"]
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"metric_patterns": patterns}))

    config = load_config(config_path=cfg_path)

    assert config.metric_patterns == patterns


def test_load_config_notifications_block(tmp_path: Path, monkeypatch):
    """notifications block correctly overrides NotificationConfig fields."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "notifications": {"nan": False, "desktop": False, "webhook": False},
    }))

    config = load_config(config_path=cfg_path)

    assert config.notifications.nan is False
    assert config.notifications.desktop is False
    assert config.notifications.webhook is False
    assert config.notifications.plateau is True  # default preserved
    assert config.notifications.stall is True    # default preserved


def test_load_config_desktop_notifications_compat(tmp_path: Path, monkeypatch):
    """Legacy desktop_notifications field overrides notifications.desktop."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"desktop_notifications": False}))

    config = load_config(config_path=cfg_path)

    assert config.notifications.desktop is False


def test_load_config_per_instance(tmp_path: Path, monkeypatch):
    """Per-instance config is correctly parsed."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "instances": {
            42: {"log_command": "tail -f /tmp/train.log", "stall_threshold_minutes": 15, "ssh_username": "worker"},
            99: {"log_command": "journalctl -f"},
        },
    }))

    config = load_config(config_path=cfg_path)

    assert "42" in config.instances
    assert config.instances["42"].log_command == "tail -f /tmp/train.log"
    assert config.instances["42"].stall_threshold_minutes == 15
    assert config.instances["42"].ssh_username == "worker"
    assert config.log_command_for(42) == "tail -f /tmp/train.log"
    assert config.ssh_username_for(42) == "worker"
    assert config.stall_threshold_for(42) == 15
    # Fallback for unknown instance
    assert config.log_command_for(1) == DEFAULT_LOG_COMMAND
    assert config.ssh_username_for(1) == "root"


def test_load_config_path_expansion(tmp_path: Path, monkeypatch):
    """Path fields expand ~ correctly."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "log_dir": "~/my-logs",
        "ssh_key_path": "~/keys/my_key",
    }))

    config = load_config(config_path=cfg_path)

    assert config.log_dir == Path.home() / "my-logs"
    assert config.ssh_key_path == Path.home() / "keys" / "my_key"


def test_load_config_set_fields(tmp_path: Path, monkeypatch):
    """decrease_good, increase_good, counters are loaded as sets."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "decrease_good": ["loss", "val_loss"],
        "increase_good": ["reward", "accuracy"],
        "counters": ["step"],
        "plateau_metrics": ["loss", "val_loss"],
    }))

    config = load_config(config_path=cfg_path)

    assert config.decrease_good == {"loss", "val_loss"}
    assert config.increase_good == {"reward", "accuracy"}
    assert config.counters == {"step"}
    assert config.plateau_metrics == ["loss", "val_loss"]


def test_save_load_round_trip(tmp_path: Path, monkeypatch):
    """save_config → load_config preserves non-default fields."""
    monkeypatch.delenv("VAST_API_KEY", raising=False)
    cfg_path = tmp_path / "config.yaml"

    original = Config()
    original.api_key = "round-trip-key"
    original.poll_interval = 20
    original.stall_threshold_minutes = 8
    original.highlight_logs = True
    original.alert_webhook_url = "https://example.com/hook"
    original.extra_metric_patterns = [r"custom=(?P<custom>[\d.]+)"]
    original.instances["42"] = InstanceConfig(log_command="tail -f /tmp/x.log", stall_threshold_minutes=3)
    original.notifications.nan = False
    original.decrease_good = {"loss", "custom_loss"}
    original.log_retention_days = 14
    original._config_path = cfg_path

    original.save_config()
    loaded = load_config(config_path=cfg_path)

    assert loaded.api_key == "round-trip-key"
    assert loaded.poll_interval == 20
    assert loaded.stall_threshold_minutes == 8
    assert loaded.highlight_logs is True
    assert loaded.alert_webhook_url == "https://example.com/hook"
    assert loaded.extra_metric_patterns == [r"custom=(?P<custom>[\d.]+)"]
    assert "42" in loaded.instances
    assert loaded.instances["42"].log_command == "tail -f /tmp/x.log"
    assert loaded.instances["42"].stall_threshold_minutes == 3
    assert loaded.notifications.nan is False
    assert loaded.notifications.plateau is True  # default preserved
    assert loaded.decrease_good == {"loss", "custom_loss"}
    assert loaded.log_retention_days == 14


def test_resolve_api_key_env_override(tmp_path: Path, monkeypatch):
    """VAST_API_KEY env var takes precedence over YAML."""
    from vigil.providers.vast import VastProvider

    monkeypatch.setenv("VAST_API_KEY", "env-key")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"vast_api_key": "yaml-key"}))

    config = load_config(config_path=cfg_path, provider=VastProvider())

    assert config.api_key == "env-key"


# ------------------------------------------------------------------
# save_config branch coverage
# ------------------------------------------------------------------


def test_save_config_all_fields(tmp_path: Path):
    """Set EVERY field to a non-default value, save, read YAML, verify all fields present."""
    cfg_path = tmp_path / "config.yaml"
    config = Config()
    config._config_path = cfg_path

    config.api_key = "all-fields-key"
    config.poll_interval = 99
    config.log_dir = Path("/tmp/custom-logs")
    config.ssh_key_path = Path("/tmp/custom-key")
    config.default_log_command = "tail -f /custom.log"
    config.stall_threshold_minutes = 77
    config.plateau_window = 16
    config.plateau_threshold = 0.999
    config.sparkline_history = 200
    config.alert_webhook_url = "https://hooks.example.com/all"
    config.alert_webhook_format = "slack"
    config.highlight_logs = True
    config.metric_patterns = ["custom_pattern"]
    config.decrease_good = {"custom_loss"}
    config.increase_good = {"custom_reward"}
    config.counters = {"custom_step"}
    config.plateau_metrics = ["custom_loss"]
    config.extra_metric_patterns = [r"extra=(?P<extra>[\d.]+)"]
    config.ssh_username = "worker"
    config.max_grid_columns = 6
    config.log_buffer_lines = 9999
    config.log_display_lines = 4444
    config.ssh_login_timeout = 30
    config.ssh_keepalive_interval = 60
    config.reconnect_backoff_max = 300
    config.log_retention_days = 14
    config.log_max_size_mb = 2048
    config.notifications.nan = False
    config.notifications.plateau = False
    config.notifications.stall = False
    config.notifications.desktop = False
    config.notifications.webhook = False

    config.save_config()

    with open(cfg_path) as f:
        data = yaml.safe_load(f)

    assert data["api_key"] == "all-fields-key"
    assert data["poll_interval"] == 99
    assert data["log_dir"] == "/tmp/custom-logs"
    assert data["ssh_key_path"] == "/tmp/custom-key"
    assert data["default_log_command"] == "tail -f /custom.log"
    assert data["stall_threshold_minutes"] == 77
    assert data["plateau_window"] == 16
    assert data["plateau_threshold"] == 0.999
    assert data["sparkline_history"] == 200
    assert data["alert_webhook_url"] == "https://hooks.example.com/all"
    assert data["alert_webhook_format"] == "slack"
    assert data["highlight_logs"] is True
    assert data["metric_patterns"] == ["custom_pattern"]
    assert data["decrease_good"] == ["custom_loss"]
    assert data["increase_good"] == ["custom_reward"]
    assert data["counters"] == ["custom_step"]
    assert data["plateau_metrics"] == ["custom_loss"]
    assert data["extra_metric_patterns"] == [r"extra=(?P<extra>[\d.]+)"]
    assert data["ssh_username"] == "worker"
    assert data["max_grid_columns"] == 6
    assert data["log_buffer_lines"] == 9999
    assert data["log_display_lines"] == 4444
    assert data["ssh_login_timeout"] == 30
    assert data["ssh_keepalive_interval"] == 60
    assert data["reconnect_backoff_max"] == 300
    assert data["log_retention_days"] == 14
    assert data["log_max_size_mb"] == 2048
    assert data["notifications"]["nan"] is False
    assert data["notifications"]["plateau"] is False
    assert data["notifications"]["stall"] is False
    assert data["notifications"]["desktop"] is False
    assert data["notifications"]["webhook"] is False


def test_save_config_default_only(tmp_path: Path):
    """Save a default config — YAML should have no non-default fields."""
    cfg_path = tmp_path / "config.yaml"
    config = Config()
    config._config_path = cfg_path

    config.save_config()

    with open(cfg_path) as f:
        data = yaml.safe_load(f)

    # Default config has no non-default fields, YAML should be empty dict or None
    assert data is None or data == {}


def test_save_config_instances_with_all_fields(tmp_path: Path):
    """Per-instance config with log_command, stall_threshold_minutes, ssh_username."""
    cfg_path = tmp_path / "config.yaml"
    config = Config()
    config._config_path = cfg_path
    config.instances["42"] = InstanceConfig(
        log_command="tail -f /tmp/train.log",
        stall_threshold_minutes=15,
        ssh_username="worker",
    )
    config.instances["99"] = InstanceConfig(log_command="journalctl -f")

    config.save_config()

    with open(cfg_path) as f:
        data = yaml.safe_load(f)

    assert "42" in data["instances"]
    assert data["instances"]["42"]["log_command"] == "tail -f /tmp/train.log"
    assert data["instances"]["42"]["stall_threshold_minutes"] == 15
    assert data["instances"]["42"]["ssh_username"] == "worker"
    assert "99" in data["instances"]
    assert data["instances"]["99"]["log_command"] == "journalctl -f"


def test_save_config_atomic_write_failure(tmp_path: Path):
    """Patch os.replace to raise — verify tmp file is cleaned up."""
    import os  # noqa: F401
    from unittest.mock import patch

    cfg_path = tmp_path / "config.yaml"
    config = Config()
    config._config_path = cfg_path
    config.api_key = "should-not-persist"

    with patch("vigil.config.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            config.save_config()

    # The target config file should NOT exist
    assert not cfg_path.exists()

    # No leftover .tmp files
    tmp_files = list(tmp_path.glob(".config_*.tmp"))
    assert tmp_files == []
