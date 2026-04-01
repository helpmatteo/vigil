from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from vigil.storage import LogStorage


def test_write_line_creates_file(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(1, "hello world")
    storage.flush(1)

    instance_dir = tmp_path / "1"
    log_files = list(instance_dir.glob("raw_*.log"))
    assert len(log_files) == 1
    assert "hello world\n" in log_files[0].read_text()


def test_write_line_multiple(tmp_path: Path):
    storage = LogStorage(tmp_path)
    lines = ["line one", "line two", "line three"]
    for line in lines:
        storage.write_line(1, line)
    storage.flush(1)

    log_files = list((tmp_path / "1").glob("raw_*.log"))
    content = log_files[0].read_text()
    for line in lines:
        assert line in content


def test_latest_symlink(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(1, "test")
    storage.flush(1)

    latest = tmp_path / "1" / "latest.log"
    assert latest.is_symlink()

    log_files = list((tmp_path / "1").glob("raw_*.log"))
    assert latest.resolve() == log_files[0].resolve()


def test_close_instance(tmp_path: Path):
    storage = LogStorage(tmp_path)

    fake_time = [datetime(2025, 1, 1, 12, 0, 0)]

    def mock_now():
        return fake_time[0]

    with patch("vigil.storage.datetime") as mock_dt:
        mock_dt.now = mock_now
        mock_dt.fromtimestamp = datetime.fromtimestamp

        storage.write_line(1, "first session")
        storage.flush(1)
        storage.close(1)

        # Advance the fake clock by 1 second for a distinct timestamp
        fake_time[0] = datetime(2025, 1, 1, 12, 0, 1)

        storage.write_line(1, "second session")
        storage.flush(1)

    log_files = sorted((tmp_path / "1").glob("raw_*.log"))
    assert len(log_files) == 2


def test_write_metrics(tmp_path: Path):
    storage = LogStorage(tmp_path)
    # write_line first to open the metrics sidecar
    storage.write_line(1, "init")
    storage.write_metrics(1, {"loss": "0.5", "step": "100"}, timestamp=1000.0)
    storage.flush(1)

    metric_files = list((tmp_path / "1").glob("metrics_*.jsonl"))
    assert len(metric_files) == 1

    content = metric_files[0].read_text().strip()
    record = json.loads(content)
    assert record["t"] == 1000.0
    assert record["loss"] == "0.5"
    assert record["step"] == "100"


def test_read_lines(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(1, "alpha")
    storage.write_line(1, "beta")
    storage.flush(1)

    log_files = list((tmp_path / "1").glob("raw_*.log"))
    result = storage.read_lines(log_files[0])
    assert result == ["alpha", "beta"]


def test_read_lines_missing_file(tmp_path: Path):
    storage = LogStorage(tmp_path)
    result = storage.read_lines(tmp_path / "nonexistent" / "missing.log")
    assert result == []


def test_read_metrics(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(1, "init")
    storage.write_metrics(1, {"loss": "0.1"}, timestamp=1.0)
    storage.write_metrics(1, {"loss": "0.05"}, timestamp=2.0)
    storage.flush(1)

    metric_files = list((tmp_path / "1").glob("metrics_*.jsonl"))
    results = storage.read_metrics(metric_files[0])
    assert len(results) == 2
    assert results[0]["t"] == 1.0
    assert results[0]["loss"] == "0.1"
    assert results[1]["t"] == 2.0
    assert results[1]["loss"] == "0.05"


def test_list_instances(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(10, "a")
    storage.write_line(20, "b")
    storage.write_line(5, "c")
    storage.flush()

    instances = storage.list_instances()
    assert instances == [5, 10, 20]


def test_flush(tmp_path: Path):
    storage = LogStorage(tmp_path)
    storage.write_line(1, "data")
    # Should not raise
    storage.flush(1)
    storage.flush()


def test_thread_safety(tmp_path: Path):
    storage = LogStorage(tmp_path)
    errors: list[Exception] = []

    def writer(instance_id: int, count: int):
        try:
            for i in range(count):
                storage.write_line(instance_id, f"line {i}")
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(inst_id, 50))
        for inst_id in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    storage.flush()

    # Verify all instances were written
    instances = storage.list_instances()
    assert len(instances) == 5

    storage.close()


def test_write_metrics_without_write_line(tmp_path: Path):
    """write_metrics without a prior write_line silently discards metrics."""
    storage = LogStorage(tmp_path)
    storage.write_metrics(1, {"loss": "0.5"}, timestamp=1000.0)

    # No files should be created — the metrics are silently dropped
    instance_dir = tmp_path / "1"
    assert not instance_dir.exists() or list(instance_dir.glob("metrics_*.jsonl")) == []


def _create_old_files(tmp_path: Path, instance_id: int, age_days: int, count: int = 1) -> list[Path]:
    """Helper: create log+metric files with mtime set to `age_days` ago."""
    instance_dir = tmp_path / str(instance_id)
    instance_dir.mkdir(parents=True, exist_ok=True)
    old_time = (datetime.now() - timedelta(days=age_days)).timestamp()
    paths = []
    for i in range(count):
        ts = f"20250101_00000{i}"
        log = instance_dir / f"raw_{ts}.log"
        log.write_text(f"old line {i}\n" * 100)
        import os
        os.utime(log, (old_time, old_time))
        paths.append(log)

        metric = instance_dir / f"metrics_{ts}.jsonl"
        metric.write_text('{"t":1.0,"loss":"0.5"}\n' * 10)
        os.utime(metric, (old_time, old_time))
        paths.append(metric)
    return paths


def test_cleanup_retention_days(tmp_path: Path):
    """cleanup removes files older than retention_days."""
    storage = LogStorage(tmp_path)

    old_files = _create_old_files(tmp_path, instance_id=1, age_days=10, count=2)
    assert all(f.exists() for f in old_files)

    # Write a fresh file that should NOT be deleted
    storage.write_line(2, "fresh data")
    storage.flush(2)

    result = storage.cleanup(retention_days=7)

    assert result["files_removed"] == 4  # 2 logs + 2 metrics
    assert result["bytes_freed"] > 0
    assert not any(f.exists() for f in old_files)

    # Fresh file still exists
    fresh_logs = list((tmp_path / "2").glob("raw_*.log"))
    assert len(fresh_logs) == 1


def test_cleanup_max_size(tmp_path: Path):
    """cleanup removes oldest files when total size exceeds max_size_mb."""
    storage = LogStorage(tmp_path)

    # Create enough data to exceed 1MB
    instance_dir = tmp_path / "1"
    instance_dir.mkdir(parents=True, exist_ok=True)
    old_time = (datetime.now() - timedelta(days=1)).timestamp()
    chunk = "x" * 1024 + "\n"  # ~1KB per line
    for i in range(3):
        log = instance_dir / f"raw_20250101_00000{i}.log"
        log.write_text(chunk * 400)  # ~400KB each, 1.2MB total
        import os
        os.utime(log, (old_time - i, old_time - i))  # stagger mtimes

    result = storage.cleanup(max_size_mb=1)

    assert result["files_removed"] >= 1
    assert result["bytes_freed"] > 0


def test_cleanup_preserves_active_files(tmp_path: Path):
    """cleanup does not delete currently-open log/metric files."""
    storage = LogStorage(tmp_path)

    # Write a line to open a file handle (makes it "active")
    storage.write_line(1, "active data")
    storage.flush(1)

    # Set the active file's mtime to 30 days ago
    import os
    old_time = (datetime.now() - timedelta(days=30)).timestamp()
    for f in (tmp_path / "1").glob("raw_*.log"):
        os.utime(f, (old_time, old_time))
    for f in (tmp_path / "1").glob("metrics_*.jsonl"):
        os.utime(f, (old_time, old_time))

    result = storage.cleanup(retention_days=7)

    # Active files should NOT be removed despite being "old"
    assert result["files_removed"] == 0
    log_files = list((tmp_path / "1").glob("raw_*.log"))
    assert len(log_files) == 1

    storage.close()


def test_cleanup_empty_dir_removal(tmp_path: Path):
    """cleanup removes empty instance directories after all files deleted."""
    _create_old_files(tmp_path, instance_id=99, age_days=30, count=1)

    storage = LogStorage(tmp_path)
    result = storage.cleanup(retention_days=7)

    assert result["files_removed"] == 2
    # The instance directory should be cleaned up
    assert not (tmp_path / "99").exists()


def test_cleanup_no_op_when_disabled(tmp_path: Path):
    """cleanup with retention_days=0 and max_size_mb=0 does nothing."""
    _create_old_files(tmp_path, instance_id=1, age_days=100, count=2)

    storage = LogStorage(tmp_path)
    result = storage.cleanup(retention_days=0, max_size_mb=0)

    assert result["files_removed"] == 0
    assert result["bytes_freed"] == 0


# ------------------------------------------------------------------
# Additional coverage tests
# ------------------------------------------------------------------


def test_write_metrics_auto_reopens_after_close(tmp_path: Path):
    """write_metrics auto-opens metrics file paired with existing log (lines 63-67)."""
    storage = LogStorage(tmp_path)
    storage.write_line(1, "init line")
    storage.flush(1)

    # Close the metrics handle directly, simulating it being None
    with storage._lock:
        mfh = storage._metric_files.pop(1, None)
        if mfh:
            mfh.close()

    # Now write_metrics should auto-reopen using the log file's timestamp
    storage.write_metrics(1, {"loss": "0.42"}, timestamp=999.0)
    storage.flush(1)

    metric_files = list((tmp_path / "1").glob("metrics_*.jsonl"))
    assert len(metric_files) >= 1
    content = metric_files[0].read_text().strip()
    lines = content.split("\n")
    found = any('"loss": "0.42"' in line or '"loss":"0.42"' in line for line in lines)
    assert found, f"Expected loss metric in {lines}"


def test_flush_all_method(tmp_path: Path):
    """flush_all() flushes all instances (lines 85-87)."""
    storage = LogStorage(tmp_path)
    storage.write_line(1, "data-a")
    storage.write_line(2, "data-b")
    storage.write_metrics(1, {"m": "1"}, timestamp=1.0)

    # Call flush_all directly
    storage.flush_all()

    # Verify data was flushed by reading files
    for iid in (1, 2):
        log_files = list((tmp_path / str(iid)).glob("raw_*.log"))
        assert len(log_files) == 1
        assert log_files[0].read_text().strip() != ""

    storage.close()


def test_flush_no_args_flushes_all(tmp_path: Path):
    """flush() with no args delegates to _flush_all_unlocked (line 83)."""
    storage = LogStorage(tmp_path)
    storage.write_line(10, "hello")
    storage.write_line(20, "world")

    # flush with no args
    storage.flush()

    log_10 = list((tmp_path / "10").glob("raw_*.log"))
    log_20 = list((tmp_path / "20").glob("raw_*.log"))
    assert len(log_10) == 1
    assert "hello" in log_10[0].read_text()
    assert len(log_20) == 1
    assert "world" in log_20[0].read_text()

    storage.close()


def test_list_sessions(tmp_path: Path):
    """list_sessions returns sorted log files for an instance (lines 128-132)."""
    storage = LogStorage(tmp_path)

    fake_time = [datetime(2025, 1, 1, 12, 0, 0)]

    def mock_now():
        return fake_time[0]

    with patch("vigil.storage.datetime") as mock_dt:
        mock_dt.now = mock_now
        mock_dt.fromtimestamp = datetime.fromtimestamp

        storage.write_line(5, "session data")
        storage.flush(5)
        storage.close(5)

        fake_time[0] = datetime(2025, 1, 1, 12, 0, 1)

        storage.write_line(5, "session two")
        storage.flush(5)

    sessions = storage.list_sessions(5)
    assert len(sessions) == 2
    assert all(p.name.startswith("raw_") for p in sessions)
    assert sessions == sorted(sessions, reverse=True)

    storage.close()


def test_list_sessions_nonexistent_instance(tmp_path: Path):
    """list_sessions returns empty list for nonexistent instance."""
    storage = LogStorage(tmp_path)
    assert storage.list_sessions(999) == []


def test_list_metric_sessions(tmp_path: Path):
    """list_metric_sessions returns sorted metric files for an instance (lines 134-138)."""
    storage = LogStorage(tmp_path)

    fake_time = [datetime(2025, 1, 1, 12, 0, 0)]

    def mock_now():
        return fake_time[0]

    with patch("vigil.storage.datetime") as mock_dt:
        mock_dt.now = mock_now
        mock_dt.fromtimestamp = datetime.fromtimestamp

        storage.write_line(7, "init")
        storage.write_metrics(7, {"loss": "0.1"}, timestamp=1.0)
        storage.flush(7)
        storage.close(7)

        fake_time[0] = datetime(2025, 1, 1, 12, 0, 1)

        storage.write_line(7, "init2")
        storage.write_metrics(7, {"loss": "0.05"}, timestamp=2.0)
        storage.flush(7)

    sessions = storage.list_metric_sessions(7)
    assert len(sessions) == 2
    assert all(p.name.startswith("metrics_") for p in sessions)
    assert sessions == sorted(sessions, reverse=True)

    storage.close()


def test_list_metric_sessions_nonexistent(tmp_path: Path):
    """list_metric_sessions returns empty list for nonexistent instance."""
    storage = LogStorage(tmp_path)
    assert storage.list_metric_sessions(999) == []


def test_read_metrics_empty_lines(tmp_path: Path):
    """read_metrics skips empty lines (line 154-155)."""
    storage = LogStorage(tmp_path)
    instance_dir = tmp_path / "1"
    instance_dir.mkdir(parents=True)
    metrics_path = instance_dir / "metrics_20250101_000000.jsonl"
    metrics_path.write_text('\n\n{"t":1.0,"loss":"0.5"}\n\n{"t":2.0,"loss":"0.3"}\n\n')

    results = storage.read_metrics(metrics_path)
    assert len(results) == 2
    assert results[0]["t"] == 1.0
    assert results[1]["t"] == 2.0


def test_read_metrics_malformed_json(tmp_path: Path):
    """read_metrics skips malformed JSON lines (lines 158-159)."""
    storage = LogStorage(tmp_path)
    instance_dir = tmp_path / "1"
    instance_dir.mkdir(parents=True)
    metrics_path = instance_dir / "metrics_20250101_000000.jsonl"
    metrics_path.write_text('{"t":1.0,"loss":"0.5"}\nNOT_JSON\n{broken\n{"t":3.0,"ok":"yes"}\n')

    results = storage.read_metrics(metrics_path)
    assert len(results) == 2
    assert results[0]["t"] == 1.0
    assert results[1]["ok"] == "yes"


def test_read_metrics_max_lines(tmp_path: Path):
    """read_metrics respects max_lines limit (lines 160-161)."""
    storage = LogStorage(tmp_path)
    instance_dir = tmp_path / "1"
    instance_dir.mkdir(parents=True)
    metrics_path = instance_dir / "metrics_20250101_000000.jsonl"
    lines = [json.dumps({"t": float(i), "v": str(i)}) for i in range(100)]
    metrics_path.write_text("\n".join(lines) + "\n")

    results = storage.read_metrics(metrics_path, max_lines=10)
    assert len(results) == 10
    assert results[0]["t"] == 0.0
    assert results[9]["t"] == 9.0


def test_read_metrics_file_not_found(tmp_path: Path):
    """read_metrics returns empty list for missing file (line 163-164)."""
    storage = LogStorage(tmp_path)
    results = storage.read_metrics(tmp_path / "nonexistent" / "metrics.jsonl")
    assert results == []


def test_log_dir_for(tmp_path: Path):
    """log_dir_for returns correct path (line 112-113)."""
    storage = LogStorage(tmp_path)
    assert storage.log_dir_for(42) == tmp_path / "42"
    assert storage.log_dir_for(1) == tmp_path / "1"
