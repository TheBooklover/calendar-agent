"""
tests/test_cli_smoke.py

CLI smoke tests:
- Ensure basic commands parse and execute without crashing.
- We do NOT assert on output content here; we only care about stability.

Note:
- If the CLI evolves, keep these tests minimal and robust.
"""

from __future__ import annotations

from calendar_agent.cli import main


def test_cli_plan_smoke() -> None:
    # Minimal invocation: deterministic (AI disabled by default)
    exit_code = main(["plan", "--goals", '[["Deep Work",120],["Email",30]]', "--buffer", "10"])
    assert exit_code == 0


def test_cli_apply_smoke_dry_run() -> None:
    # Apply uses simulated writer and should be safe by default
    exit_code = main(["apply", "--goals", '[["Deep Work",120],["Email",30]]', "--buffer", "10", "--dry-run"])
    assert exit_code == 0
