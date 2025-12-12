# calendar_agent/planner.py
"""
Planning logic: convert FreeBusy busy blocks into free slots, then allocate goals.

This module is deterministic and testable:
- merge_busy_from_freebusy: merges busy intervals from multiple calendars
- invert_busy_to_free: computes free intervals in a given work window
- propose_blocks: schedules goal blocks into free time (greedy baseline)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Interval:
    """
    Simple time interval.
    """
    start: datetime
    end: datetime


def parse_rfc3339(dt_str: str) -> datetime:
    """
    Parse an RFC3339 / ISO-8601 datetime string into a datetime object.

    Notes:
    - Google often returns RFC3339 with timezone offsets, which datetime.fromisoformat supports.
    - If Z is present, convert to +00:00.
    """
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def to_rfc3339(dt: datetime) -> str:
    """
    Convert datetime to RFC3339 string.
    """
    return dt.isoformat()


def merge_busy_from_freebusy(calendars_busy: Dict[str, Any]) -> List[Interval]:
    """
    Merge busy blocks from a FreeBusy response into one consolidated busy list.

    Args:
        calendars_busy: Output from freebusy.query, typically:
            {
              "calId": {"busy": [{"start": "...", "end": "..."}, ...]},
              ...
            }

    Returns:
        A merged list of non-overlapping busy intervals.
    """
    all_busy: List[Interval] = []

    for _, data in calendars_busy.items():
        for b in data.get("busy", []):
            start = parse_rfc3339(b["start"])
            end = parse_rfc3339(b["end"])
            if end > start:
                all_busy.append(Interval(start=start, end=end))

    # Sort then merge overlaps
    all_busy.sort(key=lambda x: x.start)

    merged: List[Interval] = []
    for it in all_busy:
        if not merged:
            merged.append(it)
            continue

        last = merged[-1]
        if it.start > last.end:
            merged.append(it)
        else:
            merged[-1] = Interval(start=last.start, end=max(last.end, it.end))

    return merged


def invert_busy_to_free(work_start: datetime, work_end: datetime, busy: List[Interval]) -> List[Interval]:
    """
    Given a work window and busy blocks, return free intervals within the work window.

    Args:
        work_start/work_end: the window you care about
        busy: busy intervals (ideally merged)

    Returns:
        List of free intervals.
    """
    if work_end <= work_start:
        return []

    # Clip busy blocks to the work window and ignore anything outside
    clipped: List[Interval] = []
    for b in busy:
        start = max(b.start, work_start)
        end = min(b.end, work_end)
        if end > start:
            clipped.append(Interval(start=start, end=end))

    clipped.sort(key=lambda x: x.start)

    free: List[Interval] = []
    cursor = work_start

    for b in clipped:
        if b.start > cursor:
            free.append(Interval(start=cursor, end=b.start))
        cursor = max(cursor, b.end)
        if cursor >= work_end:
            break

    if cursor < work_end:
        free.append(Interval(start=cursor, end=work_end))

    return [f for f in free if f.end > f.start]


def propose_blocks(free: List[Interval], goals: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
    """
    Allocate goal blocks into free slots.

    Baseline behavior:
    - Sort free slots by length (largest first)
    - Fill each goal greedily into the largest available slots

    Args:
        free: list of free intervals
        goals: list of (label, minutes)

    Returns:
        List of proposed blocks with RFC3339 start/end.
    """
    free_sorted = sorted(free, key=lambda x: (x.end - x.start), reverse=True)

    proposals: List[Dict[str, Any]] = []

    for label, minutes in goals:
        remaining = int(minutes)
        i = 0

        while remaining > 0 and i < len(free_sorted):
            slot = free_sorted[i]
            slot_minutes = int((slot.end - slot.start).total_seconds() // 60)

            if slot_minutes <= 0:
                i += 1
                continue

            use = min(remaining, slot_minutes)
            block_start = slot.start
            block_end = slot.start + timedelta(minutes=use)

            proposals.append(
                {
                    "label": label,
                    "start": to_rfc3339(block_start),
                    "end": to_rfc3339(block_end),
                    "minutes": use,
                }
            )

            # Shrink slot
            free_sorted[i] = Interval(start=block_end, end=slot.end)
            remaining -= use

            # Move on if slot is exhausted
            if int((free_sorted[i].end - free_sorted[i].start).total_seconds() // 60) <= 0:
                i += 1

    return proposals
