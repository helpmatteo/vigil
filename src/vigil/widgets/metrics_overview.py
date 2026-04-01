from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Header

if TYPE_CHECKING:
    from .instance_panel import InstancePanel

from .instance_panel import DECREASE_GOOD, INCREASE_GOOD


class MetricsOverviewScreen(Screen):
    """Compare training metrics across all running instances."""

    DEFAULT_CSS = """
    MetricsOverviewScreen DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh_table", "Refresh"),
    ]

    def __init__(
        self, panels: dict[int, InstancePanel], *,
        decrease_good: set[str] | None = None, increase_good: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.panels = panels
        self._decrease_good = decrease_good if decrease_good is not None else DECREASE_GOOD
        self._increase_good = increase_good if increase_good is not None else INCREASE_GOOD
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="metrics-table")
        yield Footer()

    def on_mount(self) -> None:
        self._build_table()
        self._refresh_timer = self.set_interval(2.0, self._build_table)

    def on_unmount(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

    def action_refresh_table(self) -> None:
        self._build_table()

    def _build_table(self) -> None:
        table = self.query_one("#metrics-table", DataTable)
        saved_row = table.cursor_row
        table.clear(columns=True)

        # Collect all metric keys across all instances, preserving first-seen order
        all_keys: list[str] = []
        seen: set[str] = set()
        panels_snapshot = list(self.panels.values())
        for panel in panels_snapshot:
            for key in panel.metric_state.current:
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)

        if not all_keys:
            table.add_column("Status")
            table.add_row("No metrics collected yet")
            return

        table.add_column("Instance", key="instance")
        for key in all_keys:
            table.add_column(key, key=key)

        for iid, panel in sorted(list(self.panels.items())):
            label = f"#{iid}"
            if panel.instance_info.label:
                label += f" {panel.instance_info.label}"

            row: list[str | Text] = [label]
            for key in all_keys:
                value = panel.metric_state.current.get(key, "—")
                spark = panel.metric_state.sparkline(key)
                direction = panel.metric_state.direction(key)

                color = self._metric_color(key, direction)

                cell = f"{value} {spark}" if spark else value
                if color:
                    row.append(Text.from_markup(f"[{color}]{cell}[/{color}]"))
                else:
                    row.append(cell)
            table.add_row(*row)

        if saved_row is not None and table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

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
