# calendar_agent/planner.py
"""
Planning logic: convert FreeBusy busy blocks into free slots, then allocate goals.

This module is deterministic and testable:
- merge_busy_from_freebusy: merges busy intervals from multiple calendars
- normalize_intervals_tz: converts intervals into a single timezone (for sane printing/math)
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
    Parse an RFC3339 / ISO-8601 datetime string into a timezone-aware datetime.

    Notes:
    - Google often returns RFC3339 with timezone offsets (e.g., +00:00).
    - Python's datetime.fromisoformat can parse offsets.
    - If Google returns a trailing 'Z' (UTC), convert it to '+00:00'.
    """
    # Replace 'Z' with '+00:00' for compatibility with fromisoformat
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def to_rfc3339(dt: datetime) -> str:
    """
    Convert a datetime to RFC3339 string (Google accepts ISO-8601 with timezone).
    """
    return dt.isoformat()


def normalize_intervals_tz(intervals: List[Interval], tz) -> List[Interval]:
    """
    Convert all interval start/end datetimes to a single timezone.

    Why:
    - FreeBusy often returns UTC timestamps (+00:00)
    - Your planning windows are likely local (America/Toronto)
    - Mixing timezones is valid, but printing can look confusing,
      and you can end up with "start in UTC, end in local" when debugging.

    Args:
        intervals: list of Interval objects with timezone-aware datetimes
        tz: a tzinfo object (e.g., ZoneInfo("America/Toronto"))

    Returns:
        New list of intervals converted into tz (same instants in time).
    """
    out: List[Interval] = []
    for it in intervals:
        out.append(
            Interval(
                start=it.start.astimezone(tz),
                end=it.end.astimezone(tz),
            )
        )
    return out


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
        A merged list of non-overlapping busy intervals (timezone-aware datetimes).
        The timezone is whatever Google returned (often UTC).
    """
    all_busy: List[Interval] = []

    # Collect all busy intervals across all calendars
    for _, data in calendars_busy.items():
        for b in data.get("busy", []):
            start = parse_rfc3339(b["start"])
            end = parse_rfc3339(b["end"])
            if end > start:
                all_busy.append(Interval(start=start, end=end))

    # Sort by start time
    all_busy.sort(key=lambda x: x.start)

    # Merge overlaps
    merged: List[Interval] = []
    for it in all_busy:
        if not merged:
            merged.append(it)
            continue

        last = merged[-1]

        # If the new interval starts after the last ends, it doesn't overlap
        if it.start > last.end:
            merged.append(it)
        else:
            # Otherwise, merge by extending the end if needed
            merged[-1] = Interval(start=last.start, end=max(last.end, it.end))

    return merged


def invert_busy_to_free(work_start: datetime, work_end: datetime, busy: List[Interval]) -> List[Interval]:
    """
    Given a work window and busy blocks, return free intervals within the work window.

    Important:
    - This function assumes all datetimes are timezone-aware.
    - It's OK if busy intervals are in a different timezone than work_start/work_end;
      Python compares aware datetimes by absolute time correctly.
    - For clean debugging/printing, normalize busy intervals first (optional).

    Args:
        work_start/work_end: the window you care about
        busy: busy intervals (ideally merged)

    Returns:
        List of free intervals within [work_start, work_end].
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

    # Sort clipped intervals by start time
    clipped.sort(key=lambda x: x.start)

    free: List[Interval] = []
    cursor = work_start

    for b in clipped:
        # If there's a gap between cursor and the next busy start, that's free time
        if b.start > cursor:
            free.append(Interval(start=cursor, end=b.start))

        # Move cursor forward to the end of the busy interval
        cursor = max(cursor, b.end)

        # If we've reached or passed the end of the work window, stop
        if cursor >= work_end:
            break

    # Anything after the last busy interval until work_end is also free
    if cursor < work_end:
        free.append(Interval(start=cursor, end=work_end))

    return [f for f in free if f.end > f.start]


def propose_blocks(free: List[Interval], goals: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
    """
    Allocate goal blocks into free slots.

    Baseline behavior (greedy):
    - Sort free slots by length (largest first)
    - Fill each goal into the largest available slots
    - If a goal doesn't fit in one slot, it will be split across multiple slots

    Args:
        free: list of free intervals
        goals: list of (label, minutes)

    Returns:
        List of proposed blocks:
            {
              "label": str,
              "start": RFC3339,
              "end": RFC3339,
              "minutes": int
            }
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

            # Shrink the current slot by the amount we used
            free_sorted[i] = Interval(start=block_end, end=slot.end)
            remaining -= use

            # If the slot is exhausted, move on
            if int((free_sorted[i].end - free_sorted[i].start).total_seconds() // 60) <= 0:
                i += 1

    return proposals
