from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_STATE_PATH = Path.home() / ".config" / "vigil" / "state.json"


@dataclass
class AppState:
    hints_completed: list[str] = field(default_factory=list)
    _state_path: Path = field(default_factory=lambda: DEFAULT_STATE_PATH, repr=False, compare=False)

    def is_hint_completed(self, hint_id: str) -> bool:
        return hint_id in self.hints_completed

    def complete_hint(self, hint_id: str) -> None:
        if hint_id not in self.hints_completed:
            self.hints_completed.append(hint_id)
            self.save()

    def save(self, path: Path | None = None) -> None:
        target = path or self._state_path
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {"hints_completed": self.hints_completed}
        # Atomic write
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent), suffix=".tmp", prefix=".state_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def reset(self) -> None:
        self.hints_completed.clear()
        try:
            self._state_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_state(state_path: Path | None = None) -> AppState:
    path = state_path or DEFAULT_STATE_PATH
    state = AppState(_state_path=path)
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data.get("hints_completed"), list):
                state.hints_completed = data["hints_completed"]
        except (json.JSONDecodeError, OSError):
            pass  # Corrupted state — start fresh
    return state
