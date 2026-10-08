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

"""The web app Cloud Run starts: ADK's API server around one agent package.

Two settings come from the environment so the same image can be deployed more
than one way:

``SESSION_SERVICE_URI``  where conversations are kept. ``memory://`` keeps them
                         inside one process. ``agentengine://<id>`` keeps them
                         in Agent Engine sessions, outside any instance.
``TRACE_TO_CLOUD``       set to ``1`` to send traces to Cloud Trace.

Run locally with:
    uvicorn deploy.main:app --port 8080
"""

from __future__ import annotations

import os
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app

AGENTS_DIR = str(Path(__file__).parent / "agents")
SESSION_SERVICE_URI = os.environ.get("SESSION_SERVICE_URI", "memory://")

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    web=False,
    trace_to_cloud=os.environ.get("TRACE_TO_CLOUD") == "1",
)


@app.get("/whoami")
def whoami() -> dict[str, str]:
    """Report which instance answered and where it keeps sessions.

    Cloud Run sets ``K_REVISION``; the instance id is read from the metadata
    server on first use. This endpoint exists for the Part 7 experiments.
    """
    return {
        "revision": os.environ.get("K_REVISION", "local"),
        "instance": _instance_id(),
        "sessions": SESSION_SERVICE_URI.split("://", 1)[0],
    }


_INSTANCE: list[str] = []


def _instance_id() -> str:
    if not _INSTANCE:
        import urllib.request

        request = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/id",
            headers={"Metadata-Flavor": "Google"},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as reply:
                _INSTANCE.append(reply.read().decode()[-12:])
        except OSError:
            _INSTANCE.append(f"local-{os.getpid()}")
    return _INSTANCE[0]
