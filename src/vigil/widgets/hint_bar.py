from __future__ import annotations

from typing import TYPE_CHECKING

from textual.timer import Timer
from textual.widgets import Static

if TYPE_CHECKING:
    from ..state import AppState


class HintBar(Static):
    """Contextual hint bar that shows one-at-a-time onboarding hints."""

    DEFAULT_CSS = """
    HintBar {
        dock: bottom;
        height: 1;
        background: $surface-lighten-1;
        color: $text-muted;
        padding: 0 2;
        display: none;
    }
    """

    HINTS = [
        {
            "id": "focus_panel",
            "text": "💡 Press 1-9 to focus a panel — number shown in title",
            "delay_after_prev": 5.0,  # First hint: 5s after panels appear
        },
        {
            "id": "search_logs",
            "text": "💡 Press / to search and filter logs",
            "delay_after_prev": 60.0,
        },
        {
            "id": "help_overlay",
            "text": "💡 Press ? to see all keyboard shortcuts",
            "delay_after_prev": 60.0,
        },
        {
            "id": "compare_metrics",
            "text": "💡 Press m to compare metrics across instances",
            "delay_after_prev": 60.0,
            "min_instances": 2,
        },
    ]

    def __init__(self, state: AppState) -> None:
        super().__init__("", id="hint-bar")
        self.state = state
        self._current_hint_idx = 0
        self._timer: Timer | None = None
        self._auto_dismiss_timer: Timer | None = None
        self._active = False
        self._panels_appeared = False
        self._hint4_attempts = 0

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop()

    def on_mount(self) -> None:
        # Skip already-completed hints
        while self._current_hint_idx < len(self.HINTS):
            hint = self.HINTS[self._current_hint_idx]
            if self.state.is_hint_completed(hint["id"]):
                self._current_hint_idx += 1
            else:
                break

    def notify_panels_appeared(self) -> None:
        """Called by the app when panels first appear."""
        if self._panels_appeared:
            return
        self._panels_appeared = True
        self._schedule_next_hint()

    def notify_action(self, action: str) -> None:
        """Called by the app when a relevant action is performed.

        Maps actions to hint IDs:
        - "focus_panel" when 1-9 pressed
        - "search" when / pressed
        - "help" when ? pressed
        - "metrics_overview" when m pressed
        """
        if not self._active:
            return

        hint = self.HINTS[self._current_hint_idx] if self._current_hint_idx < len(self.HINTS) else None
        if not hint:
            return

        # Map actions to hint IDs
        action_to_hint = {
            "focus_panel": "focus_panel",
            "search": "search_logs",
            "help": "help_overlay",
            "metrics_overview": "compare_metrics",
        }
        hint_id = action_to_hint.get(action)
        if hint_id and hint_id == hint["id"]:
            self._dismiss_current()

    def _schedule_next_hint(self) -> None:
        """Schedule the next uncompleted hint."""
        if self._current_hint_idx >= len(self.HINTS):
            return
        if self._timer is not None:
            self._timer.stop()

        hint = self.HINTS[self._current_hint_idx]
        delay = hint["delay_after_prev"]

        self._timer = self.set_timer(delay, self._show_hint)

    def _show_hint(self) -> None:
        """Display the current hint."""
        if not self.is_attached:
            return
        if self._current_hint_idx >= len(self.HINTS):
            return

        # Don't show hints if a screen is pushed on top
        try:
            if len(self.app.screen_stack) > 1:
                if self._timer is not None:
                    self._timer.stop()
                self._timer = self.set_timer(5.0, self._show_hint)
                return
        except Exception:
            return

        hint = self.HINTS[self._current_hint_idx]

        # Check min_instances requirement
        if "min_instances" in hint:
            try:
                panel_count = len(self.app._panels)
                if panel_count < hint["min_instances"]:
                    # Check again in 60 seconds, timeout after 10 minutes
                    self._hint4_attempts += 1
                    if self._hint4_attempts > 10:  # 10 * 60s = 10 minutes
                        self.state.complete_hint(hint["id"])
                        self._current_hint_idx += 1
                        return
                    if self._timer is not None:
                        self._timer.stop()
                    self._timer = self.set_timer(60.0, self._show_hint)
                    return
                else:
                    self._hint4_attempts = 0
            except Exception:
                pass

        self.update(hint["text"])
        self.display = True
        self._active = True

        # Auto-dismiss after 30 seconds
        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
        self._auto_dismiss_timer = self.set_timer(30.0, self._auto_dismiss)

    def _auto_dismiss(self) -> None:
        """Auto-dismiss the current hint after timeout."""
        self._dismiss_current()

    def _dismiss_current(self) -> None:
        """Dismiss the current hint and schedule the next one."""
        if not self._active:
            return
        if self._auto_dismiss_timer:
            self._auto_dismiss_timer.stop()
            self._auto_dismiss_timer = None

        if self._current_hint_idx < len(self.HINTS):
            hint = self.HINTS[self._current_hint_idx]
            self.state.complete_hint(hint["id"])
            self._current_hint_idx += 1

        self.display = False
        self._active = False
        self._schedule_next_hint()

    def dismiss_by_escape(self) -> None:
        """Called when Escape is pressed and a hint is showing."""
        if self._active:
            self._dismiss_current()
