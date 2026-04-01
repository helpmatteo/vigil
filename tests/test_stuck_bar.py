from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from vigil.discovery import InstanceInfo
from vigil.widgets.stuck_bar import StuckBar


def _make_instance(id: int, status: str = "loading", dph_total: float = 0.0, label: str | None = None) -> InstanceInfo:
    return InstanceInfo(
        id=id,
        ssh_host="",
        ssh_port=0,
        gpu_name="RTX 4090",
        num_gpus=4,
        status=status,
        machine_id=1000 + id,
        label=label,
        dph_total=dph_total,
    )


class _TestApp(App):
    """Minimal host app for testing StuckBar in isolation."""

    def compose(self) -> ComposeResult:
        yield StuckBar()


@pytest.mark.anyio
async def test_collapsed_summary_shows_count_and_cost():
    """Collapsed summary line shows correct instance count and total cost."""
    instances = [
        _make_instance(1234567, status="loading", dph_total=0.240),
        _make_instance(1234568, status="exited", dph_total=0.480),
    ]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)
        bar.update_instances(instances)
        await pilot.pause()

        from textual.widgets import Static
        summary = bar.query_one("#stuck-summary", Static)
        text = str(summary.content)
        assert "2 stuck instances" in text
        assert "$0.720/hr" in text
        assert "press 's' to expand" in text


@pytest.mark.anyio
async def test_toggle_expands_and_collapses_table():
    """toggle() shows the DataTable when expanding, hides it when collapsing."""
    instances = [_make_instance(9999, status="loading", dph_total=0.10)]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)
        bar.update_instances(instances)
        await pilot.pause()

        from textual.widgets import DataTable
        table = bar.query_one("#stuck-table", DataTable)

        # Initially collapsed
        assert table.display is False

        bar.toggle()
        await pilot.pause()
        assert table.display is True

        bar.toggle()
        await pilot.pause()
        assert table.display is False


@pytest.mark.anyio
async def test_expanded_summary_hint_changes():
    """Summary hint text reflects expanded vs collapsed state."""
    instances = [_make_instance(111, dph_total=0.100)]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)
        bar.update_instances(instances)
        await pilot.pause()

        from textual.widgets import Static
        summary = bar.query_one("#stuck-summary", Static)

        assert "press 's' to expand" in str(summary.content)

        bar.toggle()
        await pilot.pause()
        assert "press 's' to collapse" in str(summary.content)


@pytest.mark.anyio
async def test_selected_instance_id_returns_correct_id():
    """selected_instance_id returns the ID of the currently highlighted row."""
    instances = [
        _make_instance(1111, dph_total=0.10),
        _make_instance(2222, dph_total=0.20),
        _make_instance(3333, dph_total=0.30),
    ]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)
        bar.update_instances(instances)
        await pilot.pause()

        # Collapsed — always None
        assert bar.selected_instance_id is None

        bar.toggle()
        await pilot.pause()

        from textual.widgets import DataTable
        table = bar.query_one("#stuck-table", DataTable)

        # Default cursor is on row 0
        table.move_cursor(row=0)
        await pilot.pause()
        assert bar.selected_instance_id == 1111

        table.move_cursor(row=1)
        await pilot.pause()
        assert bar.selected_instance_id == 2222

        table.move_cursor(row=2)
        await pilot.pause()
        assert bar.selected_instance_id == 3333


@pytest.mark.anyio
async def test_update_instances_empty_adds_no_stuck_class():
    """update_instances([]) adds the no-stuck class to hide the bar."""
    instances = [_make_instance(42, dph_total=0.50)]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)

        # Start with some instances (visible)
        bar.update_instances(instances)
        await pilot.pause()
        assert not bar.has_class("no-stuck")

        # Clear instances — should hide
        bar.update_instances([])
        await pilot.pause()
        assert bar.has_class("no-stuck")


@pytest.mark.anyio
async def test_update_instances_non_empty_removes_no_stuck_class():
    """update_instances with data removes the no-stuck class to show the bar."""
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)

        # Start empty
        bar.update_instances([])
        await pilot.pause()
        assert bar.has_class("no-stuck")

        # Add instances — should show
        bar.update_instances([_make_instance(99, dph_total=0.10)])
        await pilot.pause()
        assert not bar.has_class("no-stuck")


@pytest.mark.anyio
async def test_selected_instance_id_none_when_collapsed():
    """selected_instance_id is always None when the bar is collapsed."""
    instances = [_make_instance(777, dph_total=0.10)]
    async with _TestApp().run_test(headless=True) as pilot:
        bar = pilot.app.query_one(StuckBar)
        bar.update_instances(instances)
        await pilot.pause()

        # Collapsed by default
        assert bar.selected_instance_id is None

        # Expand then collapse again
        bar.toggle()
        await pilot.pause()
        bar.toggle()
        await pilot.pause()

        assert bar.selected_instance_id is None
