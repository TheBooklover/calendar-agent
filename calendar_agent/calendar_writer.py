"""
calendar_agent/calendar_writer.py

V1.0 (portfolio) goal:
- Provide a stable interface for "applying" planned blocks to a calendar.
- For V1.0 we implement a simulated writer (safe by default).
- A real provider writer (Google, etc.) can be added later without touching planning logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


Blocks = List[Dict[str, Any]]


@dataclass(frozen=True)
class WriteResult:
    """
    Result of an apply operation.

    For V1.0, this is intentionally simple and testable.
    """
    dry_run: bool
    events_created: int
    # Keep an audit trail for explainability / debugging
    rendered_events: List[str]


class CalendarWriter(Protocol):
    """
    CalendarWriter is the boundary between planning and external calendar systems.

    Real implementations (V1.1+):
    - GoogleCalendarWriter
    - OutlookCalendarWriter
    """
    def create_events(self, *, blocks: Blocks, dry_run: bool = True) -> WriteResult:
        ...


class SimulatedCalendarWriter:
    """
    Safe default writer:
    - Never writes to external systems
    - Renders what would be created
    """
    def create_events(self, *, blocks: Blocks, dry_run: bool = True) -> WriteResult:
        rendered: List[str] = []

        for b in blocks:
            # Keep this resilient to dict shape changes across planner iterations
            label = str(b.get("label", "Untitled"))
            start = b.get("start")
            end = b.get("end")
            minutes = b.get("minutes")

            # Render a compact "event-like" line for portfolio demos
            rendered.append(f"{label} | start={start} end={end} minutes={minutes}")

        # In dry-run we "pretend" these would be created
        return WriteResult(
            dry_run=dry_run,
            events_created=0 if dry_run else len(blocks),
            rendered_events=rendered,
        )
