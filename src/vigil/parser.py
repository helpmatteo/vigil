from __future__ import annotations

import math
import re
import statistics
from collections import deque
from dataclasses import dataclass, field

SPARKLINE_BLOCKS = "▁▂▃▄▅▆▇█"


@dataclass
class MetricState:
    current: dict[str, str] = field(default_factory=dict)
    previous: dict[str, str] = field(default_factory=dict)
    history: dict[str, deque[float]] = field(default_factory=dict)

    MAX_HISTORY: int = 60

    def __init__(self, max_history: int = 60) -> None:
        self.current = {}
        self.previous = {}
        self.history = {}
        self.MAX_HISTORY = max_history

    def update(self, new_metrics: dict[str, str]) -> None:
        for k, v in new_metrics.items():
            if k in self.current:
                self.previous[k] = self.current[k]
            self.current[k] = v
            if k not in self.history:
                self.history[k] = deque(maxlen=self.MAX_HISTORY)
            try:
                self.history[k].append(float(v.replace(",", "")))
            except ValueError:
                pass

    def direction(self, key: str) -> str:
        if key not in self.previous or key not in self.current:
            return "neutral"
        try:
            old = float(self.previous[key].replace(",", ""))
            new = float(self.current[key].replace(",", ""))
            if new < old:
                return "down"
            elif new > old:
                return "up"
        except ValueError:
            pass
        return "neutral"

    def sparkline(self, key: str) -> str:
        if key not in self.history or len(self.history[key]) < 2:
            return ""
        values = list(self.history[key])
        lo, hi = min(values), max(values)
        if hi == lo:
            return SPARKLINE_BLOCKS[4] * len(values)
        return "".join(
            SPARKLINE_BLOCKS[min(int((v - lo) / (hi - lo) * 7), 7)]
            for v in values
        )

    def has_nan(self) -> str | None:
        """Return the first metric key whose current value is NaN or Inf."""
        for k, v in self.current.items():
            try:
                f = float(v.replace(",", ""))
                if math.isnan(f) or math.isinf(f):
                    return k
            except ValueError:
                pass
        return None

    def has_plateau(self, key: str, window: int = 8, threshold: float = 1e-4) -> bool:
        """Return True if the last `window` values of `key` have stdev < threshold."""
        window = max(window, 2)
        if key not in self.history or len(self.history[key]) < window:
            return False
        recent = list(self.history[key])[-window:]
        return statistics.stdev(recent) < threshold

    def reset(self) -> None:
        """Clear all tracked state. Useful when the log command changes."""
        self.current.clear()
        self.previous.clear()
        self.history.clear()


class MetricParser:
    def __init__(self, patterns: list[str]) -> None:
        self.patterns: list[re.Pattern[str]] = []
        self.warnings: list[str] = []
        for p in patterns:
            try:
                self.patterns.append(re.compile(p, re.IGNORECASE))
            except re.error as exc:
                self.warnings.append(f"Skipping invalid pattern {p!r}: {exc}")

        # Build keyword set from literal prefixes in pattern source strings
        # for a fast pre-filter. Extract the word immediately before each named
        # group (e.g. "loss" from r"loss[:\s=]+(?P<loss>...)") and also include
        # the group name itself as a fallback.
        keywords: set[str] = set()
        for pat in self.patterns:
            for group_name in pat.groupindex:
                keywords.add(group_name)
            # Extract literal words that precede named groups in the source
            for m in re.finditer(r"([a-z_][a-z0-9_]*)\b[^(]*\(\?P<", pat.pattern, re.IGNORECASE):
                keywords.add(m.group(1).lower())
        self._keywords: frozenset[str] = frozenset(keywords)

    def parse_line(self, line: str) -> dict[str, str]:
        line_lower = line.lower()
        if self._keywords and not any(k in line_lower for k in self._keywords):
            return {}

        metrics: dict[str, str] = {}
        for pattern in self.patterns:
            match = pattern.search(line)
            if match:
                for key, value in match.groupdict().items():
                    if value is not None:
                        metrics[key] = value
        return metrics
