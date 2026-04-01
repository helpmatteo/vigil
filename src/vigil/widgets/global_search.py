from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rich.markup import escape
from textual.app import ComposeResult
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header, Input, RichLog

if TYPE_CHECKING:
    from .instance_panel import InstancePanel


class GlobalSearchScreen(Screen):
    """Search across all instance log buffers simultaneously."""

    DEFAULT_CSS = """
    GlobalSearchScreen #search-box {
        dock: top;
        margin: 0 1;
    }

    GlobalSearchScreen #results {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("slash", "focus_search", "Search"),
    ]

    def __init__(self, panels: dict[int, InstancePanel]) -> None:
        super().__init__()
        self.panels = panels
        self._search_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder="Search all instances (regex supported)...", id="search-box")
        yield RichLog(id="results", highlight=False, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-box", Input).focus()

    def on_unmount(self) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
            self._search_timer = None

    def action_focus_search(self) -> None:
        self.query_one("#search-box", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-box":
            if self._search_timer is not None:
                self._search_timer.stop()
            value = event.value
            self._search_timer = self.set_timer(0.3, lambda: self._run_search(value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-box":
            if self._search_timer is not None:
                self._search_timer.stop()
                self._search_timer = None
            self._run_search(event.value)

    def _run_search(self, term: str) -> None:
        if not self.is_attached:
            return
        log = self.query_one("#results", RichLog)
        log.clear()

        if not term:
            return

        # Try regex first, fall back to substring
        use_regex = True
        try:
            pattern = re.compile(term, re.IGNORECASE)
        except re.error:
            use_regex = False
            needle = term.lower()

        total = 0
        max_per_instance = 100
        for iid, panel in sorted(list(self.panels.items())):
            label = f"#{iid}"
            if panel.instance_info.label:
                label += f" {panel.instance_info.label}"

            matches: list[str] = []
            for line in panel.get_log_lines():
                if use_regex:
                    if pattern.search(line):
                        matches.append(line)
                else:
                    if needle in line.lower():
                        matches.append(line)

            if matches:
                display = matches[-max_per_instance:]
                truncated = len(matches) > max_per_instance
                header = f"[bold cyan]━━━ {label} ({len(matches)} matches"
                if truncated:
                    header += f", showing last {max_per_instance}"
                header += ") ━━━[/bold cyan]"
                log.write(header)
                for line in display:
                    log.write(f"  {escape(line)}")
                total += len(matches)

        if total == 0:
            log.write("[dim]No matches found.[/dim]")
        else:
            log.write(f"\n[bold]{total} total matches[/bold]")
