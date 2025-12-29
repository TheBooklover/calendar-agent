# calendar_agent/planner.py
"""
Planning logic: convert FreeBusy busy blocks into free slots, then allocate goals.

This module is deterministic and testable:
- merge_busy_from_freebusy: merges busy intervals from multiple calendars
- normalize_intervals_tz: converts intervals into a single timezone (for sane printing/math)
- invert_busy_to_free: computes free intervals in a given work window
- propose_blocks: schedules goal blocks into free time (V0.5 slot-aware greedy baseline)

V0.5 changes (Option A1):
- Slot-aware packing: tries to place multiple goal blocks inside the same free slot.
- Buffer is applied *between* blocks inside a slot (not after the last block in the slot).
- Minimum block sizes are enforced per label, with an override hook for A1 demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional


@dataclass(frozen=True)
class Interval:
    """
    Simple time interval.
    """
    start: datetime
    end: datetime

    def minutes(self) -> int:
        """
        Return the length of the interval in whole minutes.
        """
        # Floor to whole minutes to keep behavior deterministic and predictable
        return int((self.end - self.start).total_seconds() // 60)


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


DEFAULT_BUFFER_MINUTES = 10

# Default minimum block sizes (minutes)
# NOTE: A1 demo wants Deep Work min=30; we implement that via override passed into propose_blocks.
DEFAULT_MIN_BLOCK_MINUTES: Dict[str, int] = {
    "Deep Work": 60,
    "Admin": 30,
    "Break/Lunch": 15,
}


def _min_block_minutes_for_label(label: str, overrides: Optional[Dict[str, int]] = None) -> int:
    """
    Return the minimum block length for a given label.

    - If overrides provided, they take precedence (used for A1 demo).
    - Otherwise use DEFAULT_MIN_BLOCK_MINUTES.
    - Unknown labels default to 15 minutes to avoid tiny fragments.
    """
    if overrides and label in overrides:
        return int(overrides[label])
    return int(DEFAULT_MIN_BLOCK_MINUTES.get(label, 15))


def propose_blocks(
    free: List[Interval],
    goals: List[Tuple[str, int]],
    buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
    min_block_minutes_by_label: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """
    Allocate goal blocks into free slots.

    V0.5 behavior (slot-aware greedy, deterministic):
    - Process free slots in chronological order.
    - For each slot, try to schedule multiple goal blocks inside the same slot.
    - Goals are attempted in the order provided (treat input order as priority).
    - Enforce per-label minimum block sizes.
    - Insert buffer *between* blocks inside a slot.
    - NEW (critical for A1 demo): allow PARTIAL allocation of a goal inside a slot
      to reserve room for a later goal in the same slot.

    Example (A1 demo):
      Slot: 80 min, Goals: Deep Work 60, Admin 30, Buffer 10
      => Deep Work 40 + Buffer 10 + Admin 30 (fits exactly), leaving Deep Work 20 unscheduled.
    """
    free_sorted = sorted(free, key=lambda x: x.start)
    remaining: Dict[str, int] = {label: int(minutes) for (label, minutes) in goals}

    proposals: List[Dict[str, Any]] = []
    buffer_delta = timedelta(minutes=int(buffer_minutes))

    def _next_goal_reserve(current_label: str) -> int:
        """
        Compute how many minutes we should reserve in the current slot for a DIFFERENT goal.

        We keep this rule simple and deterministic:
        - Look for the next goal in input order (after current_label) that still has remaining minutes.
        - Reserve (min_block + buffer) for it, so we can actually schedule it next.
        - If none exists, reserve 0.
        """
        seen_current = False
        for (label, _) in goals:
            if label == current_label:
                seen_current = True
                continue
            if not seen_current:
                continue
            if remaining.get(label, 0) <= 0:
                continue

            next_min = _min_block_minutes_for_label(label, overrides=min_block_minutes_by_label)
            # Reserve buffer + minimum block so the next goal can be placed.
            return int(buffer_minutes) + int(next_min)

        return 0

    for slot in free_sorted:
        cursor = slot.start
        remaining_in_slot = slot.minutes()
        if remaining_in_slot <= 0:
            continue

        while True:
            placed_anything = False

            for (label, _) in goals:
                if remaining.get(label, 0) <= 0:
                    continue

                min_block = _min_block_minutes_for_label(label, overrides=min_block_minutes_by_label)

                # If we can't fit even the minimum for this label, skip it.
                if remaining_in_slot < min_block:
                    continue

                # --- NEW: reserve room for the next goal (if any) ---
                reserve = _next_goal_reserve(label)

                # Max we can allocate *while leaving reserve room*
                # If reserve is too large, this could become <= 0.
                alloc_cap = max(0, remaining_in_slot - reserve)

                # Choose an allocation size:
                # - Prefer allocating up to alloc_cap (so we leave room for the next goal).
                # - But allocation must still be >= min_block.
                # - If alloc_cap is too small to meet min_block, fall back to filling as much as we can.
                if alloc_cap >= min_block:
                    alloc = min(remaining[label], alloc_cap)
                else:
                    # Can't reserve and still meet minimum -> just allocate what we can in this slot.
                    alloc = min(remaining[label], remaining_in_slot)

                # Enforce minimum block size.
                if alloc < min_block:
                    continue

                block_start = cursor
                block_end = cursor + timedelta(minutes=alloc)

                proposals.append(
                    {
                        "label": label,
                        "start": to_rfc3339(block_start),
                        "end": to_rfc3339(block_end),
                        "minutes": alloc,
                    }
                )

                remaining[label] -= alloc
                cursor = block_end
                remaining_in_slot -= alloc

                # Apply buffer ONLY if there is room for it.
                # (Buffer is between blocks; if it doesn't fit, slot ends.)
                if remaining_in_slot > 0:
                    if remaining_in_slot >= int(buffer_minutes):
                        cursor = cursor + buffer_delta
                        remaining_in_slot -= int(buffer_minutes)
                    else:
                        remaining_in_slot = 0

                placed_anything = True
                break  # restart goal loop (priority order)

            if not placed_anything or remaining_in_slot <= 0:
                break

    proposals.sort(key=lambda b: b["start"])
    return proposals
