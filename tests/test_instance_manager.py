from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from textual.app import App
from textual.widgets import DataTable

from vigil.discovery import InstanceInfo
from vigil.widgets.instance_manager import InstanceManagerScreen


def _make_instance(
    id: int, status: str = "running", gpu: str = "RTX 4090",
    ssh_host: str = "ssh.vast.ai", ssh_port: int = 22,
    dph: float = 0.24, label: str | None = None,
) -> InstanceInfo:
    return InstanceInfo(
        id=id,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
        gpu_name=gpu,
        num_gpus=1,
        status=status,
        machine_id=0,
        label=label,
        dph_total=dph,
    )


class ManagerApp(App):
    def __init__(self, panels, stuck, api_key="test", http_client=None):
        super().__init__()
        self._panels = panels
        self._stuck = stuck
        self._api_key = api_key
        self._http_client = http_client or AsyncMock(spec=httpx.AsyncClient)

    def on_mount(self) -> None:
        self.push_screen(InstanceManagerScreen(
            self._panels,
            self._stuck,
            self._api_key,
            self._http_client,
        ))


@pytest.mark.anyio
async def test_instance_manager_shows_stuck_table():
    stuck = [_make_instance(42, status="exited", ssh_host="")]
    async with ManagerApp({}, stuck).run_test() as pilot:
        await pilot.pause()
        stuck_table = pilot.app.screen.query_one("#stuck-instance-table", DataTable)
        # Should have a row for the stuck instance (not the placeholder message)
        assert stuck_table.row_count == 1
        row = stuck_table.get_row_at(0)
        assert row[0] == "42"


@pytest.mark.anyio
async def test_instance_manager_stuck_table_has_rows():
    stuck = [
        _make_instance(42, status="exited", ssh_host=""),
        _make_instance(99, status="loading", ssh_host=""),
    ]
    async with ManagerApp({}, stuck).run_test() as pilot:
        await pilot.pause()
        stuck_table = pilot.app.screen.query_one("#stuck-instance-table", DataTable)
        assert stuck_table.row_count == 2


@pytest.mark.anyio
async def test_instance_manager_no_stuck_shows_message():
    async with ManagerApp({}, []).run_test() as pilot:
        await pilot.pause()
        stuck_table = pilot.app.screen.query_one("#stuck-instance-table", DataTable)
        assert stuck_table.row_count == 1  # "No stuck instances" row
