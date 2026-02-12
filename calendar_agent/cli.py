"""
calendar_agent/cli.py

V1.0 CLI:
- plan: run planning (deterministic baseline, optional AI augmentation)
- apply: run planning then apply via CalendarWriter (simulated in V1.0)

Note:
- This CLI is intentionally minimal and portfolio-friendly.
- It demonstrates: orchestration + safety + explainability.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from calendar_agent.calendar_writer import SimulatedCalendarWriter
from calendar_agent.planner import Interval
from calendar_agent.planning.orchestrator import plan_with_optional_ai


def _parse_goals(raw: str) -> List[Tuple[str, int]]:
    """
    Parse goals from a simple JSON string.

    Expected format:
      '[["Deep Work", 120], ["Email", 30]]'

    (Keeps CLI un-opinionated and easy to demo.)
    """
    data = json.loads(raw)
    goals: List[Tuple[str, int]] = []
    for item in data:
        # Minimal input validation for V1.0
        label = str(item[0])
        minutes = int(item[1])
        goals.append((label, minutes))
    return goals


def _print_plan_result(result: Any) -> None:
    """
    Print a human-friendly summary.

    We rely on PlanResult fields you created, but keep this defensive so the CLI
    doesn't break if you evolve block dict shape later.
    """
    print("\n=== PlanResult ===")
    print(f"AI attempted: {getattr(result, 'ai_attempted', None)}")
    print(f"AI used:      {getattr(result, 'ai_used', None)}")
    print(f"AI error:     {getattr(result, 'ai_error', None)}")
    print(f"AI val errs:  {getattr(result, 'ai_validation_errors', None)}")

    baseline = getattr(result, "baseline_blocks", [])
    final = getattr(result, "final_blocks", [])

    print(f"\nBaseline blocks: {len(baseline)}")
    print(f"Final blocks:    {len(final)}")

    # Print a small sample to keep output readable
    for i, b in enumerate(final[:10]):
        label = b.get("label", "Untitled")
        minutes = b.get("minutes")
        start = b.get("start")
        end = b.get("end")
        print(f"  {i+1}. {label} | {minutes}m | {start} -> {end}")

    if len(final) > 10:
        print(f"  ... ({len(final) - 10} more)")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calendar-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # plan
    p_plan = sub.add_parser("plan", help="Generate a plan (deterministic baseline, optional AI)")
    p_plan.add_argument("--goals", required=True, help='JSON list e.g. \'[["Deep Work", 120], ["Email", 30]]\'')
    p_plan.add_argument("--buffer", type=int, default=10, help="Buffer minutes between blocks")
    p_plan.add_argument("--enable-ai", action="store_true", help="Enable AI augmentation (requires wiring ai_reasoner)")
    p_plan.add_argument("--dry-run", action="store_true", help="No-op flag for symmetry (plan never writes)")

    # apply
    p_apply = sub.add_parser("apply", help="Generate a plan and apply it using a writer (simulated in V1.0)")
    p_apply.add_argument("--goals", required=True, help='JSON list e.g. \'[["Deep Work", 120], ["Email", 30]]\'')
    p_apply.add_argument("--buffer", type=int, default=10, help="Buffer minutes between blocks")
    p_apply.add_argument("--enable-ai", action="store_true", help="Enable AI augmentation (requires wiring ai_reasoner)")
    p_apply.add_argument("--dry-run", action="store_true", help="Default: simulate writes")

    args = parser.parse_args(argv)

    # Lazy AI wiring: only attempt AI if the user enabled it
    ai_reasoner = None
    if bool(getattr(args, 'enable_ai', False)):
        from calendar_agent.planning.ai_factory import build_ai_reasoner  # local import to avoid hard dependency
        ai_reasoner = build_ai_reasoner()


    # NOTE: For V1.0 we intentionally keep "free" empty in CLI to avoid coupling
    # to calendar free/busy parsing. Demo scripts can pass real intervals.
    now = datetime.now()
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=4)
    free = [Interval(start=start, end=end)]
    goals = _parse_goals(args.goals)

    # For V1.0 portfolio demo:
    # - AI is “available” only if you pass an ai_reasoner object.
    # - You can wire your real reasoner here later (V1.0.1) without changing CLI UX.


    result = plan_with_optional_ai(
        free=free,
        goals=goals,
        buffer_minutes=args.buffer,
        enable_ai=bool(args.enable_ai),
        ai_reasoner=ai_reasoner,
    )

    _print_plan_result(result)

    if args.cmd == "apply":
        writer = SimulatedCalendarWriter()
        write_result = writer.create_events(blocks=getattr(result, "final_blocks", []), dry_run=bool(args.dry_run))
        print("\n=== Apply ===")
        print(f"dry_run:        {write_result.dry_run}")
        print(f"events_created: {write_result.events_created}")
        print("rendered_events:")
        for line in write_result.rendered_events[:20]:
            print(f"  - {line}")
        if len(write_result.rendered_events) > 20:
            print(f"  ... ({len(write_result.rendered_events) - 20} more)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
