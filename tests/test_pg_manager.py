from unittest.mock import patch

from src.pg_manager import apply_config, backup_config, restore_config

SAMPLE_CONF = """\
# PostgreSQL performance config
shared_buffers = 512MB
work_mem = 4096kB
max_connections = 100
jit = off
"""


# ── apply_config: editing existing keys ───────────────────────────────────────


def test_updates_existing_key(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        apply_config({"shared_buffers": "1024MB"})
    text = conf.read_text()
    assert "shared_buffers = 1024MB" in text
    assert "512MB" not in text


def test_appends_missing_key(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        apply_config({"wal_buffers": "32MB"})
    assert "wal_buffers = 32MB" in conf.read_text()


def test_preserves_comments(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        apply_config({"work_mem": "8192kB"})
    assert "# PostgreSQL performance config" in conf.read_text()


def test_multiple_params_applied(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        apply_config({"shared_buffers": "2048MB", "work_mem": "8192kB"})
    text = conf.read_text()
    assert "shared_buffers = 2048MB" in text
    assert "work_mem = 8192kB" in text


# ── apply_config: restart detection ──────────────────────────────────────────


def test_returns_true_when_restart_required_param_changes(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        assert apply_config({"shared_buffers": "1024MB"}) is True


def test_returns_false_when_restart_required_param_unchanged(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        assert apply_config({"shared_buffers": "512MB"}) is False


def test_returns_false_for_non_restart_param_change(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        assert apply_config({"work_mem": "8192kB"}) is False


def test_returns_true_when_restart_param_newly_appended(tmp_path):
    conf = tmp_path / "performance.conf"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf):
        # max_worker_processes not in file — appending a new restart-required param
        assert apply_config({"max_worker_processes": "8"}) is True


# ── backup_config / restore_config ────────────────────────────────────────────


def test_backup_creates_bak_file(tmp_path):
    conf = tmp_path / "performance.conf"
    bak = tmp_path / "performance.conf.bak"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf), patch("src.pg_manager.BACKUP_PATH", bak):
        backup_config()
    assert bak.read_text() == SAMPLE_CONF


def test_restore_overwrites_conf_with_bak(tmp_path):
    conf = tmp_path / "performance.conf"
    bak = tmp_path / "performance.conf.bak"
    conf.write_text(SAMPLE_CONF)
    bak.write_text("# backup content\n")
    with patch("src.pg_manager.CONFIG_PATH", conf), patch("src.pg_manager.BACKUP_PATH", bak):
        restore_config()
    assert conf.read_text() == "# backup content\n"


def test_restore_noop_when_no_bak(tmp_path):
    conf = tmp_path / "performance.conf"
    bak = tmp_path / "performance.conf.bak"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf), patch("src.pg_manager.BACKUP_PATH", bak):
        restore_config()  # bak does not exist — should not raise
    assert conf.read_text() == SAMPLE_CONF


def test_backup_restore_roundtrip(tmp_path):
    conf = tmp_path / "performance.conf"
    bak = tmp_path / "performance.conf.bak"
    conf.write_text(SAMPLE_CONF)
    with patch("src.pg_manager.CONFIG_PATH", conf), patch("src.pg_manager.BACKUP_PATH", bak):
        backup_config()
        conf.write_text("# modified\n")
        restore_config()
    assert conf.read_text() == SAMPLE_CONF
