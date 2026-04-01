from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """\
[bold]Vast.ai Dashboard[/bold]

[bold cyan]Navigation[/bold cyan]
  1-9      Focus instance panel (number shown in title)
  Tab      Next panel
  Escape   Back / unfocus / close search

[bold cyan]Views[/bold cyan]
  i        Instance manager  [dim](details, SSH commands)[/dim]
  l        Historical log viewer  [dim](/ to search)[/dim]
  m        Metrics comparison table  [dim](auto-refreshes)[/dim]
  G        Global search across all instances

[bold cyan]Instance Actions[/bold cyan]  [dim](focus a panel first)[/dim]
  c        Change log command
  r        Force SSH reconnect
  n        nvidia-smi output  [dim](r to refresh)[/dim]
  D        Stop/destroy instance  [dim](y to confirm)[/dim]

[bold cyan]Log Control[/bold cyan]  [dim](focus a panel first)[/dim]
  /        Search / filter logs  [dim](regex supported)[/dim]
  p        Pause / resume log rendering
  f        Toggle auto-scroll follow mode

[bold cyan]Alerts[/bold cyan]  [dim](configurable per-type)[/dim]
  [dim]NaN/Inf in metrics → red border + notification + webhook[/dim]
  [dim]Plateau → red border + notification + webhook[/dim]
  [dim]Stall (no output) → alert + webhook[/dim]
  [dim]Alerts auto-clear when values return to normal[/dim]
  [dim]Webhooks: raw, Slack, or Discord format[/dim]

[bold cyan]Other[/bold cyan]
  S        Setup wizard (configure API key, presets)
  ?        Toggle this help
  q        Quit
"""


class HelpOverlay(ModalScreen[None]):
    """Modal help overlay showing all keybindings."""

    DEFAULT_CSS = """
    HelpOverlay {
        align: center middle;
    }

    HelpOverlay #help-dialog {
        width: 64;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: solid $surface-lighten-3;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("escape", "dismiss_help", "Close"),
        ("question_mark", "dismiss_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static(HELP_TEXT, markup=True)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
