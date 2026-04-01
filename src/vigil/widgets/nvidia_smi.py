from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import RichLog, Static

from ..config import Config
from ..discovery import InstanceInfo
from ..ssh import ssh_connect


class NvidiaSmiScreen(ModalScreen[None]):
    """Run nvidia-smi on a remote instance and display the output."""

    DEFAULT_CSS = """
    NvidiaSmiScreen {
        align: center middle;
    }

    NvidiaSmiScreen #smi-dialog {
        width: 90;
        max-width: 95%;
        height: 30;
        border: solid $surface-lighten-3;
        background: $surface;
        padding: 1 2;
    }

    NvidiaSmiScreen #smi-dialog RichLog {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, instance: InstanceInfo, config: Config) -> None:
        super().__init__()
        self.instance = instance
        self.config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="smi-dialog"):
            yield Static(
                f"[bold]nvidia-smi[/bold] — #{self.instance.id} "
                f"({self.instance.gpu_name} x{self.instance.num_gpus})",
                markup=True,
            )
            yield RichLog(id="smi-output", highlight=False, markup=False, wrap=True)

    def on_mount(self) -> None:
        self.run_worker(self._fetch_smi(), exclusive=True, group="smi")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_refresh(self) -> None:
        log = self.query_one("#smi-output", RichLog)
        log.clear()
        log.write("Refreshing...")
        self.run_worker(self._fetch_smi(), exclusive=True, group="smi")

    async def _fetch_smi(self) -> None:
        log = self.query_one("#smi-output", RichLog)
        log.clear()
        log.write("Connecting...")
        try:
            conn = await ssh_connect(self.instance, self.config, keepalive=False)
            async with conn:
                result = await asyncio.wait_for(
                    conn.run("nvidia-smi", check=True),
                    timeout=15.0,
                )
                if not self.is_attached:
                    return
                log.clear()
                if result.stdout:
                    for line in result.stdout.splitlines():
                        log.write(line)
                if result.stderr:
                    log.write(f"\n[stderr]\n{result.stderr}")
        except Exception as exc:
            if not self.is_attached:
                return
            log.clear()
            log.write(f"Error: {type(exc).__name__}: {exc}")
