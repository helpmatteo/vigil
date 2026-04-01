from __future__ import annotations

import asyncio
import re
from collections import deque
from collections.abc import Callable

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widgets import RichLog, Static

from ..discovery import InstanceInfo
from ..notifications import send_desktop_notification
from ..parser import MetricState

# Metrics where "down" is good (losses) — module-level defaults
DECREASE_GOOD = {"loss", "rssm", "vc", "tom"}
# Metrics where "up" is good (rewards/accuracy) — module-level defaults
INCREASE_GOOD = {"reward", "accuracy"}
# Metrics that are just counters (no sparkline) — module-level defaults
COUNTERS = {"step", "epoch"}


class InstancePanel(Vertical):
    """A panel displaying one Vast.ai instance's status, metrics, and logs."""

    DEFAULT_CSS = """
    InstancePanel {
        border: solid $surface-lighten-2;
        height: 1fr;
        min-height: 12;
    }

    InstancePanel:focus-within {
        border: heavy $accent;
    }

    InstancePanel.alert {
        border: heavy $error;
    }

    InstancePanel.stopping {
        opacity: 0.5;
    }

    InstancePanel .panel-status {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }

    InstancePanel .panel-status.connected {
        color: $success;
    }

    InstancePanel .panel-status.disconnected {
        color: $error;
    }

    InstancePanel .panel-metrics {
        height: auto;
        max-height: 3;
        padding: 0 1;
        color: $text;
    }

    InstancePanel RichLog {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    def __init__(
        self,
        instance_info: InstanceInfo,
        *,
        sparkline_history: int = 60,
        plateau_window: int = 8,
        plateau_threshold: float = 1e-4,
        plateau_metrics: list[str] | None = None,
        desktop_notifications: bool = True,
        notify_nan: bool = True,
        notify_plateau: bool = True,
        highlight_logs: bool = False,
        panel_index: int = 0,
        decrease_good: set[str] | None = None,
        increase_good: set[str] | None = None,
        counters: set[str] | None = None,
        log_buffer_lines: int = 5000,
        log_display_lines: int = 2000,
        on_alert: Callable[[str, str, dict[str, str] | None], None] | None = None,
    ) -> None:
        title = ""
        if panel_index > 0:
            title += f"[{panel_index}] "
        title += f"#{instance_info.id}  {instance_info.gpu_name} x{instance_info.num_gpus}"
        if instance_info.label:
            title += f"  [{instance_info.label}]"
        if instance_info.dph_total > 0:
            title += f"  ${instance_info.dph_total:.3f}/hr"
        super().__init__(id=f"panel-{instance_info.id}")
        self.border_title = title
        self.instance_info = instance_info
        self.metric_state = MetricState(max_history=sparkline_history)
        self._plateau_window = plateau_window
        self._plateau_threshold = plateau_threshold
        self._desktop_notifications = desktop_notifications
        self._notify_nan = notify_nan
        self._notify_plateau = notify_plateau
        self._highlight_logs = highlight_logs
        self._decrease_good = decrease_good if decrease_good is not None else DECREASE_GOOD
        self._increase_good = increase_good if increase_good is not None else INCREASE_GOOD
        self._counters = counters if counters is not None else COUNTERS
        self._plateau_metrics = plateau_metrics if plateau_metrics is not None else ["loss"]
        self._removed = False
        self._line_buffer: deque[str] = deque(maxlen=log_buffer_lines)
        self._log_display_lines = log_display_lines
        self._search_term: str = ""
        self._search_timer: Timer | None = None
        self._plateau_alerted: bool = False
        self._nan_alerted: bool = False
        self._paused: bool = False
        self._follow: bool = True
        self._on_alert = on_alert
        self._background_tasks: set[asyncio.Task[None]] = set()

    def compose(self) -> ComposeResult:
        yield Static("waiting", classes="panel-status")
        yield Static("", classes="panel-metrics")
        yield RichLog(
            highlight=self._highlight_logs, markup=False, wrap=True,
            auto_scroll=True, max_lines=self._log_display_lines,
        )

    def on_unmount(self) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()

    def mark_removed(self) -> None:
        self._removed = True

    def set_status(self, status: str) -> None:
        if self._removed:
            return
        widget = self.query_one(".panel-status", Static)
        widget.update(status)

        widget.remove_class("connected", "disconnected")
        if "connected" in status and "disconnect" not in status:
            widget.add_class("connected")
        elif "disconnect" in status or "error" in status or "retry" in status:
            widget.add_class("disconnected")

    def add_log_line(self, line: str, metrics: dict[str, str]) -> None:
        if self._removed:
            return

        self._line_buffer.append(line)

        if metrics:
            self.metric_state.update(metrics)
            nan_key = self.metric_state.has_nan()
            if nan_key:
                if not self._nan_alerted:
                    self._nan_alerted = True
                    if self._notify_nan:
                        self._trigger_alert(f"NaN detected in {nan_key}!", alert_type="nan")
            elif self._nan_alerted:
                self._nan_alerted = False
                if self.has_class("alert") and not self._plateau_alerted:
                    self.clear_alert()
            self._refresh_metrics()

            if any(m in metrics for m in self._plateau_metrics):
                self._check_plateau()

        if not self._paused:
            self._write_filtered_line(line)

    def _check_plateau(self) -> None:
        for metric_key in self._plateau_metrics:
            if self.metric_state.has_plateau(
                metric_key, window=self._plateau_window, threshold=self._plateau_threshold
            ):
                if not self._plateau_alerted and self._notify_plateau:
                    self._plateau_alerted = True
                    self._trigger_alert(f"{metric_key} plateau detected — training may be stuck", alert_type="plateau")
                return
        # No plateau in any watched metric
        if self._plateau_alerted:
            self._plateau_alerted = False
            if not self._nan_alerted:
                self.clear_alert()

    def _write_filtered_line(self, line: str) -> None:
        if self._search_term:
            matcher = self._build_matcher()
            if not matcher(line):
                return
        self.query_one(RichLog).write(line)

    def set_search(self, term: str) -> None:
        if self._removed:
            return
        self._search_term = term
        # Cancel any pending debounce
        if self._search_timer is not None:
            self._search_timer.cancel()
        # Debounce: apply after 200ms using Textual's timer (safe from any context)
        self._search_timer = self.set_timer(0.2, self._apply_search)

    def _apply_search(self) -> None:
        if self._removed:
            return
        log = self.query_one(RichLog)
        log.clear()
        matcher = self._build_matcher()
        for line in self._line_buffer:
            if matcher(line):
                log.write(line)

    def _build_matcher(self) -> Callable[[str], bool]:
        """Return a predicate that tests whether a line matches the current search."""
        if not self._search_term:
            return lambda _line: True
        try:
            pattern = re.compile(self._search_term, re.IGNORECASE)
            return lambda line: pattern.search(line) is not None
        except re.error:
            needle = self._search_term.lower()
            return lambda line: needle in line.lower()

    def toggle_pause(self) -> bool:
        """Toggle pause state. Returns the new paused state."""
        self._paused = not self._paused
        return self._paused

    def toggle_follow(self) -> bool:
        """Toggle follow/auto-scroll mode. Returns the new follow state."""
        self._follow = not self._follow
        self.query_one(RichLog).auto_scroll = self._follow
        return self._follow

    def _refresh_metrics(self) -> None:
        if self._removed:
            return
        widget = self.query_one(".panel-metrics", Static)

        counter_parts: list[str] = []
        metric_parts: list[str] = []

        for key, value in self.metric_state.current.items():
            safe_key = escape(key)
            safe_value = escape(value)

            if key in self._counters:
                counter_parts.append(f"{safe_key}: {safe_value}")
                continue

            direction = self.metric_state.direction(key)
            spark = self.metric_state.sparkline(key)
            color = self._metric_color(key, direction)

            if color:
                metric_parts.append(f"[{color}]{safe_key}:{safe_value}[/]{spark}")
            else:
                metric_parts.append(f"{safe_key}:{safe_value}{spark}")

        lines: list[str] = []
        if counter_parts:
            lines.append(" | ".join(counter_parts))
        if metric_parts:
            lines.append("  ".join(metric_parts))

        widget.update("\n".join(lines))

    def _metric_color(self, key: str, direction: str) -> str:
        if key in self._decrease_good:
            if direction == "down":
                return "green"
            if direction == "up":
                return "red"
        elif key in self._increase_good:
            if direction == "up":
                return "green"
            if direction == "down":
                return "red"
        return ""

    def _trigger_alert(self, message: str, alert_type: str = "unknown") -> None:
        self.add_class("alert")
        self.app.notify(
            f"#{self.instance_info.id}: {message}",
            severity="error",
            timeout=10,
        )
        if self._desktop_notifications:
            self.app.run_worker(
                send_desktop_notification(
                    f"Vast.ai #{self.instance_info.id}",
                    message,
                ),
                exit_on_error=False,
            )
        if self._on_alert:
            self._on_alert(alert_type, message, dict(self.metric_state.current))

    def get_log_lines(self) -> list[str]:
        """Return a copy of the in-memory log buffer."""
        return list(self._line_buffer)

    def clear_alert(self) -> None:
        self.remove_class("alert")

    def clear_log(self) -> None:
        self.query_one(RichLog).clear()
        self._line_buffer.clear()
        self.metric_state.reset()
        self._nan_alerted = False
        self._plateau_alerted = False
