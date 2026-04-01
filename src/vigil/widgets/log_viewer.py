from __future__ import annotations

import re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, RichLog
from textual.widgets.option_list import Option

from ..storage import LogStorage


class LogViewerScreen(Screen):
    """Browse historical log files from ~/.vast-logs/."""

    DEFAULT_CSS = """
    LogViewerScreen #viewer-layout {
        height: 1fr;
    }

    LogViewerScreen #log-list {
        width: 35;
        min-width: 25;
        border-right: solid $accent;
    }

    LogViewerScreen #viewer-right {
        width: 1fr;
    }

    LogViewerScreen #viewer-search {
        dock: top;
        margin: 0 0;
        width: 1fr;
    }

    LogViewerScreen #log-content {
        width: 1fr;
    }

    LogViewerScreen #empty-viewer {
        width: 1fr;
        content-align: center middle;
        color: $text-muted;
        padding: 4;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("slash", "focus_search", "Search"),
    ]

    def __init__(self, storage: LogStorage) -> None:
        super().__init__()
        self.storage = storage
        self._path_map: dict[str, Path] = {}
        self._loaded_lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            OptionList(*self._build_options(), id="log-list"),
            Vertical(
                Input(placeholder="Search loaded log...", id="viewer-search"),
                RichLog(
                    id="log-content",
                    highlight=True,
                    markup=False,
                    wrap=True,
                    auto_scroll=False,
                ),
                id="viewer-right",
            ),
            id="viewer-layout",
        )
        yield Footer()

    def _build_options(self) -> list[Option]:
        options: list[Option] = []
        instances = self.storage.list_instances()

        if not instances:
            return [Option("No logs found", disabled=True)]

        for iid in instances:
            # Instance header (disabled, acts as section label)
            options.append(Option(f"--- Instance #{iid} ---", disabled=True))
            sessions = self.storage.list_sessions(iid)
            for session in sessions:
                size_kb = session.stat().st_size // 1024
                label = f"  {session.name}  ({size_kb}KB)"
                opt_id = str(session)
                self._path_map[opt_id] = session
                options.append(Option(label, id=opt_id))

        return options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id
        if opt_id is None or opt_id not in self._path_map:
            return

        path = self._path_map[opt_id]
        log = self.query_one("#log-content", RichLog)
        log.clear()
        log.write("Loading...")
        self.run_worker(self._load_log(path), exclusive=True, group="log-loader")

    async def _load_log(self, path: Path) -> None:
        import asyncio

        lines = await asyncio.to_thread(self.storage.read_lines, path)
        if not self.is_attached:
            return
        self._loaded_lines = lines
        log = self.query_one("#log-content", RichLog)
        log.clear()
        for line in lines:
            log.write(line)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "viewer-search":
            self._filter_log(event.value)

    def _filter_log(self, term: str) -> None:
        log = self.query_one("#log-content", RichLog)
        log.clear()
        if not term:
            for line in self._loaded_lines:
                log.write(line)
            return
        try:
            pattern = re.compile(term, re.IGNORECASE)

            def matcher(line):
                return pattern.search(line) is not None
        except re.error:
            needle = term.lower()

            def matcher(line):
                return needle in line.lower()
        for line in self._loaded_lines:
            if matcher(line):
                log.write(line)

    def action_focus_search(self) -> None:
        self.query_one("#viewer-search", Input).focus()
