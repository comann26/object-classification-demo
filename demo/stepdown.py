"""Automatic model/size step-down when measured fps stays below the floor.

See docs/design.md §3 "Model, device, input size": start at the configured
model with 640 px input; if fps stays below `runtime.fps_floor` for
`runtime.stepdown_after_s` continuously, step down one step at a time:
large@640 -> small@640 -> small@480 -> small@320. `VideoFile` and
`SyntheticSource` disable step-down entirely (§3 Clock) — the caller only
constructs a `StepDown` for a realtime source.
"""

from __future__ import annotations

from collections import deque

from demo.config import ScoringConfig

_EPS = 1e-9

# Steps taken *after* the starting point; the starting point itself
# (large@640 or small@640) is never returned, only what comes next.
_FROM_LARGE: tuple[tuple[str, int], ...] = (("small", 640), ("small", 480), ("small", 320))
_FROM_SMALL: tuple[tuple[str, int], ...] = (("small", 480), ("small", 320))


class StepDown:
    """Pure logic, no I/O: feed it (ts, fps), it tells you when to step down."""

    def __init__(self, cfg: ScoringConfig, large_available: bool) -> None:
        self._floor = cfg.runtime.fps_floor
        self._after_s = cfg.runtime.stepdown_after_s
        self._steps: deque[tuple[str, int]] = deque(_FROM_LARGE if large_available else _FROM_SMALL)
        self._below_since: float | None = None

    def observe(self, ts: float, fps: float) -> tuple[str, int] | None:
        """Call once per frame with the session clock `ts` and measured `fps`."""
        if not self._steps:
            return None
        if fps >= self._floor:
            self._below_since = None
            return None
        if self._below_since is None:
            self._below_since = ts
        if ts - self._below_since < self._after_s - _EPS:
            return None
        self._below_since = ts  # restart the timer so the next step needs its own stepdown_after_s
        return self._steps.popleft()
