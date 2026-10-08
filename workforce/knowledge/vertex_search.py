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

"""The same company library, served by Vertex AI Search.

``library.search`` is forty lines of keyword matching that runs on a laptop.
This module puts the same eight documents in a Vertex AI Search data store and
searches them there, so the experiment in this part can be run against a
hosted search service as well.

It talks to the Discovery Engine REST API with the credentials the rest of the
repo already uses, so there is nothing extra to install. Creating a data store
is billable; ``python -m workforce.knowledge.vertex_search delete`` removes it.

    python -m workforce.knowledge.vertex_search setup    # create and load
    python -m workforce.knowledge.vertex_search search "fleet price"
    python -m workforce.knowledge.vertex_search delete
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession

from workforce.knowledge import library

API = "https://discoveryengine.googleapis.com/v1"
DATA_STORE_ID = os.environ.get("CORVANE_DATA_STORE", "corvane-library")


def _project() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT (see .env.example).")
    return project


def _session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    session = AuthorizedSession(credentials)
    # User credentials need a project to bill the request to.
    session.headers["x-goog-user-project"] = _project()
    return session


def collection() -> str:
    """Return the resource name that holds the data store."""
    return f"projects/{_project()}/locations/global/collections/default_collection"


def data_store() -> str:
    """Return the data store's full resource name."""
    return f"{collection()}/dataStores/{DATA_STORE_ID}"


def _wait(session: AuthorizedSession, operation: dict[str, Any], timeout_s: int = 300) -> None:
    """Wait for a long-running operation, if the reply is one."""
    name = operation.get("name", "")
    deadline = time.monotonic() + timeout_s
    while "/operations/" in name and not operation.get("done"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"{name} did not finish in {timeout_s} seconds")
        time.sleep(5)
        operation = session.get(f"{API}/{name}").json()
    if "error" in operation:
        raise RuntimeError(operation["error"])


def setup() -> None:
    """Create the data store if it is missing, then write every document to it.

    The store holds structured documents: each one is a small JSON record with
    a title, the date it took effect, and its text. Writing a document that
    already exists replaces it, so this is safe to run twice.
    """
    session = _session()
    if session.get(f"{API}/{data_store()}").status_code == 404:
        created = session.post(
            f"{API}/{collection()}/dataStores",
            params={"dataStoreId": DATA_STORE_ID},
            json={
                "displayName": "Corvane Outdoor library (fictional)",
                "industryVertical": "GENERIC",
                "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
                "contentConfig": "NO_CONTENT",
            },
        )
        created.raise_for_status()
        _wait(session, created.json())
    branch = f"{API}/{data_store()}/branches/default_branch/documents"
    for doc in library.DOCUMENTS:
        written = session.patch(
            f"{branch}/{doc.doc_id}",
            params={"allowMissing": "true"},
            json={"structData": {"title": doc.title, "effective": doc.effective, "text": doc.text}},
        )
        written.raise_for_status()


def delete() -> None:
    """Delete the data store and everything in it."""
    session = _session()
    removed = session.delete(f"{API}/{data_store()}")
    if removed.status_code != 404:
        removed.raise_for_status()
        _wait(session, removed.json())


def search(query: str, limit: int = 3) -> list[library.Document]:
    """Return the ``limit`` documents Vertex AI Search ranks highest for the query.

    The result is the same shape ``library.search`` returns, so the agents in
    this part cannot tell which search they were given.
    """
    found = _session().post(
        f"{API}/{data_store()}/servingConfigs/default_search:search",
        json={"query": query, "pageSize": limit},
    )
    found.raise_for_status()
    documents = []
    for result in found.json().get("results", []):
        doc = library.get(result["document"]["id"])
        if doc is not None:
            documents.append(doc)
    return documents


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        setup()
        print(f"Loaded {len(library.DOCUMENTS)} documents into {data_store()}")
        print("Indexing takes a few minutes before searches return them.")
    elif command == "delete":
        delete()
        print(f"Deleted {data_store()}")
    elif command == "search":
        for hit in search(" ".join(sys.argv[2:])):
            print(hit.doc_id, "|", hit.effective, "|", hit.title)
    else:
        print(__doc__)
