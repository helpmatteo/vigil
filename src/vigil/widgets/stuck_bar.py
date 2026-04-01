from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from ..discovery import InstanceInfo


class StuckBar(Vertical):
    """Collapsible bar docked at the bottom showing stuck (non-running) instances."""

    can_focus = True

    DEFAULT_CSS = """
    StuckBar {
        dock: bottom;
        height: auto;
        max-height: 12;
        background: $warning 10%;
        border-top: solid $warning;
        padding: 0 1;
    }

    StuckBar.no-stuck {
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="stuck-bar")
        self._instances: list[InstanceInfo] = []
        self._expanded = False

    def compose(self) -> ComposeResult:
        yield Static("", id="stuck-summary")
        yield DataTable(id="stuck-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#stuck-table", DataTable)
        table.add_columns("ID", "GPU", "Status", "Label", "$/hr")
        table.display = False
        self.add_class("no-stuck")

    def update_instances(self, instances: list[InstanceInfo]) -> None:
        """Rebuild display with the given list of stuck instances."""
        self._instances = instances

        if not instances:
            self.add_class("no-stuck")
            return

        self.remove_class("no-stuck")
        self._update_summary()
        self._rebuild_table()

    def toggle(self) -> None:
        """Flip expanded/collapsed state."""
        self._expanded = not self._expanded
        table = self.query_one("#stuck-table", DataTable)
        table.display = self._expanded
        self._update_summary()

    @property
    def selected_instance_id(self) -> int | str | None:
        """Return the instance ID of the currently highlighted row, or None."""
        if not self._expanded or not self._instances:
            return None
        table = self.query_one("#stuck-table", DataTable)
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            return row_key.value
        except Exception:
            return None

    def _update_summary(self) -> None:
        count = len(self._instances)
        total_cost = sum(i.dph_total for i in self._instances)
        hint = "press 's' to collapse" if self._expanded else "press 's' to expand"
        summary = self.query_one("#stuck-summary", Static)
        summary.update(
            f"[!] {count} stuck {'instance' if count == 1 else 'instances'}"
            f" — ${total_cost:.3f}/hr burning  [{hint}]"
        )

    def _rebuild_table(self) -> None:
        table = self.query_one("#stuck-table", DataTable)
        table.clear()
        for inst in self._instances:
            gpu_label = f"{inst.gpu_name} x{inst.num_gpus}"
            label = inst.label or ""
            cost = f"${inst.dph_total:.3f}"
            table.add_row(str(inst.id), gpu_label, inst.status, label, cost, key=str(inst.id))
