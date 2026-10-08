# Copyright 2026 Robert H. Mowery III
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run the Part 7 checks against the deployed service.

Usage:
    python run_part7.py auth URL
    python run_part7.py sessions URL [ROUNDS]
    python run_part7.py team URL [TRIALS]
    python run_part7.py cold URL [REQUESTS]

``auth``      call the service with and without an identity token.
``sessions``  create a session, then ask for it back in bursts and record
              which instance answered and whether it had the session.
``team``      the Part 2 conversation over HTTP: a standing rule in one
              request, the brief in the next, then check the draft.
``cold``      time a first request and the ones after it.

Results go to results/part7_<check>_<label>.json, where the label is how the
service says it keeps sessions (``memory`` or ``agentengine``).

The identity token comes from ``gcloud auth print-identity-token``, so the
account that runs this needs the run.invoker role on the service.
"""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from workforce import cast
from workforce.context import handoff

RESULTS = Path(__file__).parent / "results"
APP = "marketing_team"
USER = "dana"


def token() -> str:
    """Return an identity token for the signed-in gcloud account."""
    done = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def call(
    method: str, url: str, auth: str | None, body: dict[str, Any] | None = None, timeout: int = 300
) -> tuple[int, Any, float]:
    """Make one request and return (status, parsed body or text, seconds)."""
    headers = {"Authorization": f"Bearer {auth}"} if auth else {}
    started = time.monotonic()
    reply = requests.request(method, url, headers=headers, json=body, timeout=timeout)
    seconds = round(time.monotonic() - started, 2)
    try:
        return reply.status_code, reply.json(), seconds
    except ValueError:
        return reply.status_code, reply.text[:300], seconds


def save(check: str, base: str, auth: str, payload: Any) -> None:
    """Write one check's results, named for how the service keeps sessions."""
    label = call("GET", f"{base}/whoami", auth)[1]["sessions"]
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"part7_{check}_{label}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {path.name}")


def check_auth(base: str) -> None:
    """Call the service without a token, then with one."""
    auth = token()
    rows = {
        "no_token": call("GET", f"{base}/whoami", None)[0],
        "with_token": call("GET", f"{base}/whoami", auth)[0],
    }
    print(rows)
    save("auth", base, auth, rows)


def check_sessions(base: str, rounds: int) -> None:
    """Create one session, then look for it from whichever instance answers."""
    auth = token()
    sessions = f"{base}/apps/{APP}/users/{USER}/sessions"
    status, created, _ = call("POST", sessions, auth, {})
    if status != 200:
        raise RuntimeError(f"could not create a session: {status} {created}")
    session_id = created["id"]

    def look(_: int) -> dict[str, Any]:
        # Two requests on one connection pool can land on different instances,
        # so the instance is only a strong hint, not proof.
        who = call("GET", f"{base}/whoami", auth)[1]
        found = call("GET", f"{sessions}/{session_id}", auth)[0]
        return {"instance": who.get("instance"), "status": found}

    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for _ in range(rounds):
            rows.extend(pool.map(look, range(6)))
    found = sum(1 for row in rows if row["status"] == 200)
    print(
        f"{found} of {len(rows)} lookups found the session;",
        f"{len({row['instance'] for row in rows})} instances answered",
    )
    save("sessions", base, auth, {"session": session_id, "lookups": rows})


def _final_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for event in events:
        state.update((event.get("actions") or {}).get("stateDelta") or {})
    return state


def check_team(base: str, trials: int) -> None:
    """Send the standing rule, then the brief, as two separate requests."""
    auth = token()
    rows = []
    for trial in range(trials):
        row: dict[str, Any] = {"trial": trial}
        sessions = f"{base}/apps/{APP}/users/{USER}-{uuid.uuid4().hex[:6]}/sessions"
        user = sessions.split("/users/")[1].split("/")[0]
        session_id = call("POST", sessions, auth, {})[1]["id"]
        state: dict[str, Any] = {}
        for name, text in (("rule", handoff.RULE_TURN), ("brief", cast.BRIEF)):
            body = {
                "app_name": APP,
                "user_id": user,
                "session_id": session_id,
                "new_message": {"role": "user", "parts": [{"text": text}]},
            }
            status, events, seconds = call("POST", f"{base}/run", auth, body)
            row[f"{name}_status"], row[f"{name}_seconds"] = status, seconds
            if status != 200:
                row[f"{name}_error"] = str(events)[:200]
                break
            state.update(_final_state(events))
            row[f"{name}_input_tokens"] = sum(
                (event.get("usageMetadata") or {}).get("promptTokenCount", 0) for event in events
            )
        row.update(handoff.check_draft(state))
        rows.append(row)
        print(json.dumps(row), flush=True)
    save("team", base, auth, rows)


def check_cold(base: str, requests_count: int) -> None:
    """Time a run of requests; the first one pays for any cold start."""
    auth = token()
    rows = []
    for index in range(requests_count):
        status, who, seconds = call("GET", f"{base}/whoami", auth)
        rows.append(
            {
                "request": index,
                "status": status,
                "seconds": seconds,
                "instance": who.get("instance") if isinstance(who, dict) else None,
            }
        )
        print(rows[-1], flush=True)
    save("cold", base, auth, rows)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    check, target = sys.argv[1], sys.argv[2].rstrip("/")
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    if check == "auth":
        check_auth(target)
    elif check == "sessions":
        check_sessions(target, count or 5)
    elif check == "team":
        check_team(target, count or 3)
    elif check == "cold":
        check_cold(target, count or 6)
    else:
        print(__doc__)
        sys.exit(1)
