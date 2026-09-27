"""Object-to-person linker: which person is holding which threat object.

All continuous-overlap timing is by `ts` (seconds), never frame counts.
See docs/design.md §3 Link.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from demo.config import ScoringConfig
from demo.contracts import BBox, Link, Track

_EPS = 1e-9


def overlap(obj: BBox, person: BBox, expand_side: float, expand_top: float) -> float:
    """area(obj ∩ expanded person) ÷ area(obj). Not clamped to [0, 1]."""
    x1, y1, x2, y2 = person
    w, h = x2 - x1, y2 - y1
    ex1, ex2 = x1 - expand_side * w, x2 + expand_side * w
    ey1, ey2 = y1 - expand_top * h, y2

    ox1, oy1, ox2, oy2 = obj
    obj_area = max(0.0, ox2 - ox1) * max(0.0, oy2 - oy1)
    if obj_area <= 0.0:
        return 0.0

    iw = max(0.0, min(ox2, ex2) - max(ox1, ex1))
    ih = max(0.0, min(oy2, ey2) - max(oy1, ey1))
    return (iw * ih) / obj_area


@dataclass
class _LinkState:
    person_id: int
    object_class: str
    object_likelihood: float
    linked_s: float = 0.0
    last_ts: float | None = None
    prev_visible: bool = True
    below_since: float | None = None  # overlap < min, continuous, while visible
    out_of_view_since: float | None = None
    overlap_hist: deque[tuple[float, float]] = field(default_factory=deque)
    transfer_since: dict[int, float] = field(default_factory=dict)  # other person_id -> ts


class Linker:
    def __init__(self, cfg: ScoringConfig) -> None:
        self._cfg = cfg.link
        self._links: dict[int, _LinkState] = {}
        self._form_since: dict[int, dict[int, float]] = {}
        self._first_ts: dict[int, float] = {}
        self._broken_ts: dict[int, float] = {}
        self._events: list[tuple[Literal["formed", "broken"], Link]] = []

    def update(self, ts: float, people: list[Track], objects: list[Track]) -> list[Link]:
        people_by_id = {p.track_id: p for p in people}
        self._carry_over_restarts(people, objects, people_by_id)

        present = set()
        for obj in objects:
            present.add(obj.track_id)
            self._first_ts.setdefault(obj.track_id, obj.first_ts)
            st = self._links.get(obj.track_id)
            if st is not None:
                self._update_linked(ts, obj, people_by_id, st)
            else:
                self._update_unlinked(ts, obj, people_by_id)

        for oid in [o for o in self._links if o not in present]:
            self._break(oid, ts)
        for oid, st in [(o, s) for o, s in self._links.items() if s.person_id not in people_by_id]:
            self._break(oid, ts)
        for oid in [o for o in self._form_since if o not in present]:
            del self._form_since[oid]

        return sorted(
            (self._to_link(oid, st, ts) for oid, st in self._links.items()),
            key=lambda link: link.object_id,
        )

    def _carry_over_restarts(
        self, people: list[Track], objects: list[Track], people_by_id: dict[int, Track]
    ) -> None:
        """A restarted track takes over its predecessor's link state (design.md §3 Track)."""
        person_restart = {
            p.restarted_from: p.track_id
            for p in people
            if p.restarted_from is not None and p.restarted_from not in people_by_id
        }
        for st in self._links.values():
            if st.person_id in person_restart:
                st.person_id = person_restart[st.person_id]

        object_ids = {o.track_id for o in objects}
        for obj in objects:
            old_id = obj.restarted_from
            if old_id is not None and old_id in self._links and old_id not in object_ids:
                self._links[obj.track_id] = self._links.pop(old_id)

    def events(self) -> list[tuple[Literal["formed", "broken"], Link]]:
        ev, self._events = self._events, []
        return ev

    def unattended_s(self, object_id: int, ts: float) -> float | None:
        if object_id in self._links:
            return None
        since = self._broken_ts.get(object_id, self._first_ts.get(object_id))
        return None if since is None else ts - since

    # -- unlinked: candidate formation / transfer timers -------------------

    def _update_unlinked(self, ts: float, obj: Track, people_by_id: dict[int, Track]) -> None:
        c = self._cfg
        timers = self._form_since.setdefault(obj.track_id, {})
        overlaps: dict[int, float] = {}
        for pid, person in people_by_id.items():
            ov = overlap(obj.bbox, person.bbox, c.expand_side, c.expand_top)
            overlaps[pid] = ov
            if ov >= c.min_overlap - _EPS:
                timers.setdefault(pid, ts)
            else:
                timers.pop(pid, None)
        for pid in [p for p in timers if p not in people_by_id]:
            del timers[pid]

        qualifying = [pid for pid, since in timers.items() if ts - since >= c.form_s - _EPS]
        if qualifying:
            winner = max(qualifying, key=lambda pid: overlaps[pid])
            self._form(obj, winner, ts, overlaps[winner])

    def _form(self, obj: Track, person_id: int, ts: float, ov: float) -> None:
        st = _LinkState(
            person_id=person_id,
            object_class=obj.class_name,
            object_likelihood=obj.likelihood,
            last_ts=ts,
            prev_visible=obj.visible,
        )
        st.overlap_hist.append((ts, ov))
        self._links[obj.track_id] = st
        self._form_since.pop(obj.track_id, None)
        self._events.append(("formed", self._to_link(obj.track_id, st, ts)))

    # -- linked: fade / break / transfer -------------------------------

    def _update_linked(
        self, ts: float, obj: Track, people_by_id: dict[int, Track], st: _LinkState
    ) -> None:
        c = self._cfg
        st.object_class = obj.class_name
        st.object_likelihood = obj.likelihood

        if not obj.visible:
            if st.out_of_view_since is None:
                st.out_of_view_since = ts
                st.below_since = None  # invisible time never counts toward break_s
            out_of_view_s = ts - st.out_of_view_since
            st.prev_visible = False
            st.last_ts = ts
            if out_of_view_s > c.fade_s + _EPS:
                self._break(obj.track_id, ts)
            return

        was_out_of_view = st.out_of_view_since is not None
        st.out_of_view_since = None
        if st.prev_visible and st.last_ts is not None:
            st.linked_s += ts - st.last_ts
        st.prev_visible = True
        st.last_ts = ts

        person = people_by_id.get(st.person_id)
        if person is None:
            return  # cleaned up by the caller once every object is processed

        ov = overlap(obj.bbox, person.bbox, c.expand_side, c.expand_top)
        st.overlap_hist.append((ts, ov))
        while st.overlap_hist and st.overlap_hist[0][0] < ts - 1.0 - _EPS:
            st.overlap_hist.popleft()

        if ov >= c.min_overlap - _EPS:
            st.below_since = None
        elif was_out_of_view:
            # First frame back from out-of-view, not overlapping the holder: breaks immediately
            # rather than getting a fresh break_s grace period (design.md §3 Link).
            self._break(obj.track_id, ts)
            return
        else:
            if st.below_since is None:
                st.below_since = ts
            elif ts - st.below_since >= c.break_s - _EPS:
                self._break(obj.track_id, ts)
                return

        overlaps: dict[int, float] = {}
        for pid, other in people_by_id.items():
            if pid == st.person_id:
                continue
            ov2 = overlap(obj.bbox, other.bbox, c.expand_side, c.expand_top)
            overlaps[pid] = ov2
            if ov2 >= c.min_overlap - _EPS:
                st.transfer_since.setdefault(pid, ts)
            else:
                st.transfer_since.pop(pid, None)
        for pid in [p for p in st.transfer_since if p not in people_by_id or p == st.person_id]:
            del st.transfer_since[pid]

        qualifying = [
            pid for pid, since in st.transfer_since.items() if ts - since >= c.form_s - _EPS
        ]
        if qualifying:
            winner = max(qualifying, key=lambda pid: overlaps[pid])
            self._break(obj.track_id, ts)
            self._form(obj, winner, ts, overlaps[winner])

    def _break(self, object_id: int, ts: float) -> None:
        st = self._links.pop(object_id, None)
        if st is None:
            return
        self._events.append(("broken", self._to_link(object_id, st, ts)))
        self._broken_ts[object_id] = ts

    def _to_link(self, object_id: int, st: _LinkState, ts: float) -> Link:
        c = self._cfg
        mean_ov = (
            sum(ov for _, ov in st.overlap_hist) / len(st.overlap_hist) if st.overlap_hist else 0.0
        )
        ramp = min(1.0, st.linked_s / c.strength_full_s) if c.strength_full_s > 0 else 1.0
        base = mean_ov * ramp

        if st.out_of_view_since is not None:
            out_of_view_s = ts - st.out_of_view_since
            fade = max(0.0, 1.0 - out_of_view_s / c.fade_s) if c.fade_s > 0 else 0.0
            strength = base * fade
        else:
            out_of_view_s = None
            strength = base

        return Link(
            person_id=st.person_id,
            object_id=object_id,
            object_class=st.object_class,
            object_likelihood=st.object_likelihood,
            linked_s=st.linked_s,
            strength=strength,
            out_of_view_s=out_of_view_s,
        )
