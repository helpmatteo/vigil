from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDestroyScreen(ModalScreen[bool]):
    """Confirmation dialog before destroying a Vast.ai instance."""

    DEFAULT_CSS = """
    ConfirmDestroyScreen {
        align: center middle;
    }

    ConfirmDestroyScreen #destroy-dialog {
        width: 60;
        max-width: 90%;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }

    ConfirmDestroyScreen #destroy-dialog Label {
        margin-bottom: 1;
    }

    ConfirmDestroyScreen .buttons {
        height: 3;
        align: right middle;
    }

    ConfirmDestroyScreen .buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("y", "confirm", "Confirm"),
        ("n", "cancel", "Cancel"),
    ]

    def __init__(self, instance_id: int | str, gpu_name: str, dph: float) -> None:
        super().__init__()
        self.instance_id = instance_id
        self.gpu_name = gpu_name
        self.dph = dph

    def compose(self) -> ComposeResult:
        with Vertical(id="destroy-dialog"):
            yield Label(
                f"[bold red]Stop Instance #{self.instance_id}?[/bold red]\n\n"
                f"GPU: {self.gpu_name}\n"
                f"Cost: ${self.dph:.3f}/hr\n\n"
                f"This will stop the instance. You will stop being charged.",
                markup=True,
            )
            with Horizontal(classes="buttons"):
                yield Button("Stop Instance", variant="error", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
