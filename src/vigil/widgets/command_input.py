from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class CommandInputScreen(ModalScreen[str | None]):
    """Modal dialog to change the log command for an instance."""

    DEFAULT_CSS = """
    CommandInputScreen {
        align: center middle;
    }

    CommandInputScreen #command-dialog {
        width: 80;
        max-width: 90%;
        height: auto;
        border: solid $surface-lighten-3;
        background: $surface;
        padding: 1 2;
    }

    CommandInputScreen #command-dialog Label {
        margin-bottom: 1;
    }

    CommandInputScreen #command-dialog Input {
        margin-bottom: 1;
    }

    CommandInputScreen #command-dialog .buttons {
        height: 3;
        align: right middle;
    }

    CommandInputScreen #command-dialog Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, instance_id: int, current_command: str) -> None:
        super().__init__()
        self.instance_id = instance_id
        self.current_command = current_command

    def compose(self) -> ComposeResult:
        with Vertical(id="command-dialog"):
            yield Label(f"Log command for instance #{self.instance_id}:")
            yield Input(
                value=self.current_command,
                placeholder="e.g. tail -f /root/train.log",
                id="command-input",
            )
            from textual.containers import Horizontal

            with Horizontal(classes="buttons"):
                yield Button("Apply", variant="primary", id="apply")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#command-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            value = self.query_one("#command-input", Input).value
            self.dismiss(value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
