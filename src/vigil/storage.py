from __future__ import annotations

import collections
import io
import json
import shutil
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path


class LogStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._lock = threading.Lock()
        self._files: dict[int, io.TextIOWrapper] = {}
        self._metric_files: dict[int, io.TextIOWrapper] = {}

    def _open_log(self, instance_id: int) -> io.TextIOWrapper:
        instance_dir = self.base_dir / str(instance_id)
        instance_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = instance_dir / f"raw_{timestamp_str}.log"

        fh = open(log_path, "a", buffering=8192)

        # Maintain a latest.log symlink (atomic replacement)
        latest = instance_dir / "latest.log"
        tmp = instance_dir / f".tmp_latest_{uuid.uuid4().hex}"
        tmp.symlink_to(log_path.name)
        tmp.rename(latest)  # atomic on POSIX

        # Open the companion metrics sidecar
        self._open_metrics(instance_id, timestamp_str)

        return fh

    def _open_metrics(self, instance_id: int, timestamp_str: str) -> None:
        instance_dir = self.base_dir / str(instance_id)
        instance_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = instance_dir / f"metrics_{timestamp_str}.jsonl"
        existing = self._metric_files.get(instance_id)
        if existing is not None:
            existing.close()
        self._metric_files[instance_id] = open(metrics_path, "a", buffering=8192)

    def write_line(self, instance_id: int, line: str) -> None:
        with self._lock:
            if instance_id not in self._files:
                self._files[instance_id] = self._open_log(instance_id)
            fh = self._files[instance_id]
            fh.write(line + "\n")

    def write_metrics(
        self, instance_id: int, metrics: dict[str, str], timestamp: float
    ) -> None:
        with self._lock:
            fh = self._metric_files.get(instance_id)
            if fh is None:
                # Auto-open metrics file paired with the existing log file's timestamp
                if instance_id in self._files:
                    log_name = Path(self._files[instance_id].name).stem  # "raw_YYYYMMDD_HHMMSS"
                    ts = log_name[4:]  # strip "raw_" prefix
                    self._open_metrics(instance_id, ts)
                    fh = self._metric_files.get(instance_id)
                if fh is None:
                    return
            record = {"t": timestamp, **metrics}
            fh.write(json.dumps(record) + "\n")

    def flush(self, instance_id: int | None = None) -> None:
        with self._lock:
            if instance_id is not None:
                fh = self._files.get(instance_id)
                if fh:
                    fh.flush()
                mfh = self._metric_files.get(instance_id)
                if mfh:
                    mfh.flush()
            else:
                self._flush_all_unlocked()

    def flush_all(self) -> None:
        with self._lock:
            self._flush_all_unlocked()

    def _flush_all_unlocked(self) -> None:
        for fh in self._files.values():
            fh.flush()
        for mfh in self._metric_files.values():
            mfh.flush()

    def close(self, instance_id: int | None = None) -> None:
        with self._lock:
            if instance_id is not None:
                fh = self._files.pop(instance_id, None)
                if fh:
                    fh.close()
                mfh = self._metric_files.pop(instance_id, None)
                if mfh:
                    mfh.close()
            else:
                for fh in self._files.values():
                    fh.close()
                self._files.clear()
                for mfh in self._metric_files.values():
                    mfh.close()
                self._metric_files.clear()

    def log_dir_for(self, instance_id: int) -> Path:
        return self.base_dir / str(instance_id)

    # ------------------------------------------------------------------
    # Historical log browsing
    # ------------------------------------------------------------------

    def list_instances(self) -> list[int]:
        if not self.base_dir.exists():
            return []
        return sorted(
            int(d.name)
            for d in self.base_dir.iterdir()
            if d.is_dir() and d.name.isdigit()
        )

    def list_sessions(self, instance_id: int) -> list[Path]:
        instance_dir = self.base_dir / str(instance_id)
        if not instance_dir.exists():
            return []
        return sorted(instance_dir.glob("raw_*.log"), reverse=True)

    def list_metric_sessions(self, instance_id: int) -> list[Path]:
        instance_dir = self.base_dir / str(instance_id)
        if not instance_dir.exists():
            return []
        return sorted(instance_dir.glob("metrics_*.jsonl"), reverse=True)

    def read_lines(self, path: Path, max_lines: int = 5000) -> list[str]:
        try:
            with open(path) as f:
                tail = collections.deque((line.rstrip("\n\r") for line in f), maxlen=max_lines)
            return list(tail)
        except FileNotFoundError:
            return []

    def read_metrics(self, path: Path, max_lines: int = 50000) -> list[dict]:
        try:
            results: list[dict] = []
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if len(results) >= max_lines:
                        break
            return results
        except FileNotFoundError:
            return []

    def _active_paths(self) -> tuple[set[Path], set[Path]]:
        """Return resolved paths of currently-open log and metric files.

        Must be called under self._lock.
        """
        log_paths = {Path(fh.name).resolve() for fh in self._files.values()}
        metric_paths = {Path(fh.name).resolve() for fh in self._metric_files.values()}
        return log_paths, metric_paths

    def cleanup(self, retention_days: int = 0, max_size_mb: int = 0) -> dict[str, int]:
        """Remove old log files based on retention policy.

        Returns dict with cleanup stats: {files_removed, bytes_freed}.
        """
        if not self.base_dir.exists():
            return {"files_removed": 0, "bytes_freed": 0}

        # Snapshot active file paths and instance IDs under the lock to avoid races with writes
        with self._lock:
            active_log_paths, active_metric_paths = self._active_paths()
            active_ids = set(self._files.keys()) | set(self._metric_files.keys())

        files_removed = 0
        bytes_freed = 0
        now = datetime.now()

        def _is_active(path: Path) -> bool:
            resolved = path.resolve()
            return resolved in active_log_paths or resolved in active_metric_paths

        # Phase 1: Delete files older than retention_days
        if retention_days > 0:
            cutoff = now - timedelta(days=retention_days)
            for instance_dir in self.base_dir.iterdir():
                if not instance_dir.is_dir() or not instance_dir.name.isdigit():
                    continue
                for path in list(instance_dir.glob("raw_*.log")) + list(
                    instance_dir.glob("metrics_*.jsonl")
                ):
                    if _is_active(path):
                        continue

                    try:
                        stat = path.stat()
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        if mtime < cutoff:
                            path.unlink()
                            files_removed += 1
                            bytes_freed += stat.st_size
                    except OSError:
                        continue

                # Clean up empty instance directories (skip if instance is still active)
                try:
                    instance_id_int = int(instance_dir.name)
                    if instance_id_int in active_ids:
                        continue
                    remaining = list(instance_dir.iterdir())
                    non_symlinks = [p for p in remaining if not p.is_symlink()]
                    if not non_symlinks:
                        shutil.rmtree(instance_dir, ignore_errors=True)
                except (OSError, ValueError):
                    pass

        # Phase 2: If total size exceeds max_size_mb, delete oldest files first
        if max_size_mb > 0:
            max_bytes = max_size_mb * 1024 * 1024
            all_files: list[tuple[float, int, Path]] = []

            for instance_dir in self.base_dir.iterdir():
                if not instance_dir.is_dir() or not instance_dir.name.isdigit():
                    continue
                for path in list(instance_dir.glob("raw_*.log")) + list(
                    instance_dir.glob("metrics_*.jsonl")
                ):
                    if _is_active(path):
                        continue
                    try:
                        stat = path.stat()
                        all_files.append((stat.st_mtime, stat.st_size, path))
                    except OSError:
                        continue

            total_size = sum(size for _, size, _ in all_files)
            if total_size > max_bytes:
                # Sort by mtime ascending (oldest first)
                all_files.sort(key=lambda x: x[0])
                for _mtime, size, path in all_files:
                    if total_size <= max_bytes:
                        break
                    try:
                        path.unlink()
                        total_size -= size
                        files_removed += 1
                        bytes_freed += size
                    except OSError:
                        continue

        return {"files_removed": files_removed, "bytes_freed": bytes_freed}
