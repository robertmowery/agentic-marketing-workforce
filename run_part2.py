"""Runs the Part 2 experiments that need a model and saves what happened.

Usage:
    python run_part2.py handoff [TRIALS]     # does a standing rule reach the writer?
    python run_part2.py window  [TRIALS]     # input growth, with and without compaction

Storage and state-scope claims need no model. See tests/test_part2_claims.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.sessions import InMemorySessionService

from workforce import cast, harness
from workforce.context import handoff, window
from workforce.topologies import coordinator, hybrid

RESULTS_DIR = Path(__file__).parent / "results"

HANDOFF_BUILDS: dict[str, Callable[[], BaseAgent]] = {
    "coordinator_guarded": lambda: coordinator.build(guarded=True),
    "hybrid": hybrid.build,
    "hybrid_with_rules": handoff.build_hybrid_with_rules,
}

WINDOW_BUILDS: dict[str, int | None] = {"no_compaction": None, "compaction_every_3": 3}


def _turn_row(rec: harness.RunRecord) -> dict[str, Any]:
    """Flatten one turn's record."""
    return {
        "seconds": round(rec.seconds, 1),
        "model_calls": rec.model_calls,
        "input_tokens": rec.input_tokens,
        "output_tokens": rec.output_tokens,
        "timed_out": rec.timed_out,
        "trace": rec.trace,
        "calls": rec.calls,
        "final": rec.final_text[:400],
    }


async def run_handoff(trials: int) -> list[dict[str, Any]]:
    """Give a standing rule, then a brief, and check the draft in each build.

    The rules build then gets a second, brand-new session for the same user
    with only the brief, to show the rule outliving the conversation.
    """
    rows = []
    for name, build in HANDOFF_BUILDS.items():
        for trial in range(trials):
            service = InMemorySessionService()
            records = await harness.converse(
                name,
                agent=build(),
                messages=[handoff.RULE_TURN, cast.BRIEF],
                session_service=service,
            )
            last = records[-1]
            # Everything the lead agent put into its handoffs, as one string.
            handed_over = json.dumps([c["args"] for r in records for c in r.calls])
            row: dict[str, Any] = {
                "experiment": "handoff",
                "build": name,
                "trial": trial,
                **handoff.check_draft(last.state),
                "rule_in_state": last.state.get(handoff.HOUSE_RULES_KEY),
                "rule_in_a_handoff": handoff.SIGN_OFF.lower() in handed_over.lower(),
                "input_tokens": sum(r.input_tokens for r in records),
                "output_tokens": sum(r.output_tokens for r in records),
                "model_calls": sum(r.model_calls for r in records),
                "draft": last.state.get("draft"),
                "turns": [_turn_row(r) for r in records],
            }
            if name == "hybrid_with_rules":
                later = await harness.converse(
                    name, agent=build(), messages=[cast.BRIEF], session_service=service
                )
                row["new_session"] = {
                    **handoff.check_draft(later[-1].state),
                    "draft": later[-1].state.get("draft"),
                    "turns": [_turn_row(r) for r in later],
                }
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "turns"}), flush=True)
    return rows


async def run_window(trials: int) -> list[dict[str, Any]]:
    """Run the long conversation with and without compaction."""
    rows = []
    for name, interval in WINDOW_BUILDS.items():
        for trial in range(trials):
            app = window.build_app(f"window_{name}", compaction_interval=interval)
            records = await harness.converse(name, app=app, messages=window.turns())
            answer = records[-1].final_text
            row = {
                "experiment": "window",
                "build": name,
                "trial": trial,
                "turns_completed": len(records),
                "recalled_po_number": window.PO_NUMBER in answer,
                "final_answer": answer[:200],
                "input_tokens_by_turn": [r.input_tokens for r in records],
                "output_tokens_by_turn": [r.output_tokens for r in records],
                "model_calls_by_turn": [r.model_calls for r in records],
                "input_tokens": sum(r.input_tokens for r in records),
                "output_tokens": sum(r.output_tokens for r in records),
                "compaction_input_tokens": records[-1].compaction_input_tokens,
                "compaction_output_tokens": records[-1].compaction_output_tokens,
                "timed_out": any(r.timed_out for r in records),
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


EXPERIMENTS = {"handoff": run_handoff, "window": run_window}


async def main(names: list[str], trials: int) -> None:
    """Run each named experiment and write one results file per experiment."""
    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = os.environ.get("RESULT_SUFFIX", "")
    for name in names:
        rows = await EXPERIMENTS[name](trials)
        (RESULTS_DIR / f"part2_{name}{suffix}.json").write_text(json.dumps(rows, indent=1))


def parse_args(argv: list[str]) -> tuple[list[str], int]:
    """Split arguments into experiment names and an optional trial count."""
    names = [arg for arg in argv if not arg.isdigit()] or list(EXPERIMENTS)
    unknown = [name for name in names if name not in EXPERIMENTS]
    if unknown:
        raise SystemExit(
            f"Unknown experiment(s): {', '.join(unknown)}. Choose from: {', '.join(EXPERIMENTS)}"
        )
    trials = next((int(arg) for arg in argv if arg.isdigit()), 1)
    return names, trials


if __name__ == "__main__":
    asyncio.run(main(*parse_args(sys.argv[1:])))
