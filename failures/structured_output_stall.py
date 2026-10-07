"""Reproduction: requests with a response schema that never come back.

Sends the same writing request several ways, one after another, and records
how long each took and whether it returned at all:

    schema            response schema, default thinking
    schema_no_think   response schema, thinking budget 0
    json_by_request   no schema; the prompt asks for JSON
    json_mime_only    no schema; JSON response type set

This calls the model. Run it from the repo root:

    python -m failures.structured_output_stall [ROUNDS]

Results are written to results/part3_structured_output.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from workforce import cast

DEADLINE_MS = 45_000
RESULTS = Path(__file__).parent.parent / "results" / "part3_structured_output.json"

TASK = (
    "Write a launch email and LinkedIn post for the TrailLock 2 rooftop cargo"
    " system for fleet managers."
)
ASK_FOR_JSON = (
    " Reply with only a JSON object with the keys email_subject, email_body"
    " (under 120 words) and linkedin_post (under 80 words)."
)
_SCHEMA: dict[str, Any] = {"response_mime_type": "application/json", "response_schema": cast.Draft}

# name -> (prompt, config)
VARIANTS: dict[str, tuple[str, types.GenerateContentConfig | None]] = {
    "schema": (TASK, types.GenerateContentConfig(**_SCHEMA)),
    "schema_no_think": (
        TASK,
        types.GenerateContentConfig(
            **_SCHEMA, thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    ),
    "json_by_request": (TASK + ASK_FOR_JSON, None),
    "json_mime_only": (
        TASK + ASK_FOR_JSON,
        types.GenerateContentConfig(response_mime_type="application/json"),
    ),
}


def _is_valid_draft(text: str | None) -> bool:
    """Check a reply against the Draft contract."""
    cleaned = (text or "").strip().removeprefix("```json").removesuffix("```").strip()
    try:
        cast.Draft.model_validate_json(cleaned)
    except ValueError:
        return False
    return True


async def one_request(client: genai.Client, variant: str, attempt: int) -> dict[str, Any]:
    """Send one request with no retries and record what happened."""
    prompt, config = VARIANTS[variant]
    started = time.perf_counter()
    row: dict[str, Any] = {"variant": variant, "attempt": attempt}
    try:
        reply = await client.aio.models.generate_content(
            model=cast.MODEL, contents=prompt, config=config
        )
        row.update(returned=True, valid_draft=_is_valid_draft(reply.text))
    except Exception as exc:  # noqa: BLE001 - the failure is the measurement
        row.update(returned=False, error=f"{type(exc).__name__}: {exc}"[:120])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


async def main(rounds: int) -> None:
    """Run every variant ``rounds`` times, interleaved so conditions are shared."""
    load_dotenv()
    client = genai.Client(http_options=types.HttpOptions(timeout=DEADLINE_MS))
    rows = []
    for attempt in range(rounds):
        for variant in VARIANTS:
            rows.append(await one_request(client, variant, attempt))
            print(json.dumps(rows[-1]), flush=True)
    RESULTS.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
