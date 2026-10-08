# Agentic Marketing Workforce

Reference code for the article series **From Pilot to Production: Engineering the Agentic Workforce** by Robert H. Mowery III ([robertmowery.com](https://robertmowery.com)).

The example company, Corvane Outdoor, is invented. The code is real: every snippet in the technical articles is copied from this repo, and every claim about what the framework does or refuses to do is backed by a test.

- **Framework:** Google Agent Development Kit for Python, pinned to `google-adk==2.11.0`
- **Model:** `gemini-3.5-flash`
- **Python:** 3.11 or later

## Part 1: three ways to wire an agent team

Part 1 builds the same team of five specialists (three researchers, a copywriter, a brand judge) several ways and measures each one against the same campaign brief.

| Build | File | Who decides the next step |
| --- | --- | --- |
| `coordinator` | `workforce/topologies/coordinator.py` | The model. One Director with five sub-agents. |
| `coordinator_guarded` | same, `build(guarded=True)` | The model, with specialist transfers disabled. |
| `graph` | `workforce/topologies/graph.py` | Code. A `Workflow` with a fan-out and a join. |
| `graph_sequential` | same, `build(parallel=False)` | Code. The researchers run one after another. |
| `hybrid` | `workforce/topologies/hybrid.py` | A Director up front, with the graph as its one tool. |
| `legacy` | `workforce/topologies/legacy.py` | Code, on the deprecated `SequentialAgent` and `ParallelAgent`. |

## Part 2: four ways a team loses what it was told

Part 2 looks for the four failures behind "the agent forgot": the session was never stored, the fact was saved in the wrong scope, it was never handed to the agent doing the work, or it was crowded out of the context window.

| Failure | Where | Needs a model |
| --- | --- | --- |
| Storage | `tests/test_part2_claims.py` | No |
| Scope | `tests/test_part2_claims.py` | No |
| Handoff | `workforce/context/handoff.py`, `run_part2.py handoff` | Yes |
| Window | `workforce/context/window.py`, `run_part2.py window` | Yes |

```bash
.venv/bin/python -m pytest -q tests/test_part2_claims.py   # storage and scope, no model calls
.venv/bin/python run_part2.py handoff 3    # does a standing rule reach the writer?
.venv/bin/python run_part2.py window 3     # input growth, with and without compaction
```

The handoff experiment gives the Director a standing rule in one turn and the brief in the next, then checks the saved draft. Each result row records every function call with its arguments, so you can see what one agent actually handed another.

## Part 3: three ways a team gets stuck

Part 3 builds a review loop (writer, brand review, legal review) and looks at three ways it fails to finish: a loop with no exit, two reviewers whose rules contradict, and a join that waits on a branch that never ran.

| Subject | Where | Needs a model |
| --- | --- | --- |
| Loops, routed edges, the skipped join | `tests/test_part3_claims.py` | No |
| Four builds of the review loop | `workforce/review/loop.py`, `run_part3.py loops` | Yes |
| Judge consistency on planted faults | `workforce/review/judge.py`, `run_part3.py judge` | Yes |
| Requests with a response schema stalling | `failures/structured_output_stall.py` | Yes |

```bash
.venv/bin/python -m pytest -q tests/test_part3_claims.py   # no model calls
RUN_TIMEOUT_S=300 .venv/bin/python run_part3.py loops 3     # plain, conflicting, capped, ranked
.venv/bin/python run_part3.py judge 5      # four drafts, each scored five times
.venv/bin/python -m failures.structured_output_stall 6
```

The `conflict_uncapped` build is meant not to finish: brand review requires the warranty and legal review forbids it, so `RUN_TIMEOUT_S` is what ends the run. The agents in this part ask for JSON in the instruction and validate the reply in code instead of setting a response schema, because requests with a schema often failed to return on this model during these runs. `failures/structured_output_stall.py` reproduces that comparison.

## Part 4: what an outside tool hands your agent

Part 4 connects one designer agent to an outside tool over the Model Context Protocol three ways: every tool the server offers, only the four the job needs, and every tool with a person approving the dangerous ones. The tool, DesignDesk, is a fictional stand-in that runs locally and keeps an audit log, so results are counted from what the server did, not from what the agent reported.

| Subject | Where | Needs a model |
| --- | --- | --- |
| What each connection exposes; descriptions pass through unmodified | `tests/test_part4_claims.py` | No |
| The MCP server and its audit log | `workforce/tools/design_server.py` | No |
| Three connections against a clean and a poisoned server | `workforce/tools/access.py`, `run_part4.py` | Yes |

```bash
.venv/bin/python -m pytest -q tests/test_part4_claims.py   # starts the server, no model calls
.venv/bin/python run_part4.py 10           # 9 setups x 10 runs
```

The poisoned server plants one instruction, either in data a tool returns or in a tool description, asking the agent to delete two designs and share one publicly. It is planted in a local stub for measurement and reaches nothing outside this process.

## Part 5: answering from the company's documents

Part 5 gives one sales-desk agent a small company library three ways: no documents, a search tool, and a search tool that returns each document's effective date along with rules for using it. The library is fictional. The experiment runs twice: on a local keyword match, which runs the same on every machine with nothing to set up, and on a Vertex AI Search data store holding the same eight documents.

| Subject | Where | Needs a model |
| --- | --- | --- |
| What the search returns, and the code check on cited figures | `tests/test_part5_claims.py` | No |
| The same tools on either search, and how the built-in build is graded | `tests/test_part5_vertex.py` | No |
| The library and the keyword search | `workforce/knowledge/library.py` | No |
| The same library in Vertex AI Search | `workforce/knowledge/vertex_search.py` | No, but it needs a data store |
| Three builds, four questions, graded in code | `workforce/knowledge/answer.py`, `run_part5.py` | Yes |

```bash
.venv/bin/python -m pytest -q tests/test_part5_claims.py tests/test_part5_vertex.py   # no model calls
.venv/bin/python run_part5.py 10           # 3 builds x 4 questions x 10 runs, keyword search

# The second run. Creating a data store is billable; see infra/README.md.
.venv/bin/python -m workforce.knowledge.vertex_search setup
.venv/bin/python run_part5.py 10 vertex    # the same search tools on Vertex AI Search
.venv/bin/python run_part5.py 10 grounded  # ADK's built-in VertexAiSearchTool
.venv/bin/python -m workforce.knowledge.vertex_search delete
```

The library holds two price lists, one superseded and never removed, and one question that no document answers. Every reply is graded in code: right, stale, gave both, declined, or answered what the documents do not say, plus any figure that appears in the answer and in none of the documents it cites.

## Part 6: defenses, and a person who approves

Part 6 goes back to the planted instruction from Part 4 and gives the designer every tool again. It compares three defenses (nothing, a warning in the instruction, and a code callback that refuses a dangerous call the marketer's request did not ask for), then answers the confirmation from Part 4 with two stand-ins for a person: one that approves everything and one that reads the request first.

| Subject | Where | Needs a model |
| --- | --- | --- |
| What the guard reads, what it blocks, and the two approvers | `tests/test_part6_claims.py` | No |
| The warning and the code guard | `workforce/trust/guard.py` | Yes |
| A run that pauses for approval and continues | `workforce/trust/approval.py` | Yes |

```bash
.venv/bin/python -m pytest -q tests/test_part6_claims.py   # no model calls
.venv/bin/python run_part6.py defenses 10
.venv/bin/python run_part6.py approval 10
```

Harm is counted from the stub server's audit log, never from the agent's own account of what it did.

## Part 7: running the team as a service

Part 7 puts the Part 2 team behind an HTTP endpoint on Cloud Run and checks what changes once more than one copy of it is running: who may call it, where a conversation lives between requests, and how long a first request takes.

| Subject | Where |
| --- | --- |
| The service: ADK's FastAPI app around the team | `deploy/main.py`, `deploy/agents/marketing_team/agent.py` |
| Container and deploy script (private service, its own service account) | `Dockerfile`, `deploy/deploy.sh` |
| Cloud setup as code: APIs, service account, session store, data store | `infra/` |
| The checks: auth, sessions across instances, the team over HTTP, cold start | `run_part7.py` |

```bash
cd infra && terraform init && terraform apply && cd ..      # see infra/README.md first
deploy/deploy.sh corvane-marketing-team memory://           # sessions in each instance's memory
.venv/bin/python run_part7.py sessions SERVICE_URL
deploy/deploy.sh corvane-marketing-team "$(terraform -chdir=infra output -raw session_service_uri)"
.venv/bin/python run_part7.py sessions SERVICE_URL
```

Everything in this part is billable and none of it is needed for Parts 1 to 6. `infra/README.md` has the teardown. Nothing in `infra/` or `deploy/` holds a key, a password, or a token: Terraform and the scripts sign in with your own gcloud login.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # set your own Google Cloud project
gcloud auth application-default login
```

The project needs the Vertex AI API enabled. Authentication uses Application Default Credentials, so no key or secret goes in `.env`.

## Check the framework claims (no model calls)

```bash
.venv/bin/python -m pytest -q
```

These tests construct agents and workflows but never call a model, so they are free and finish in a few seconds. The Part 4 tests start a local MCP server as a subprocess.

## Run a build (calls the model)

```bash
.venv/bin/python run_part1.py graph 3            # build name, number of trials
RUN_TIMEOUT_S=180 RESULT_SUFFIX=_180s .venv/bin/python run_part1.py coordinator 3
```

Each run prints one JSON line per trial and writes `results/part1_<build><suffix>.json`. The `coordinator` build is the runaway described in the article: nothing inside it stops the loop, so `RUN_TIMEOUT_S` is the most you will spend on a trial.

A new Google Cloud project has a low default quota. Run builds one at a time; the agents already retry rate-limit errors.

## Reproduce the article's numbers

| Claim | Evidence |
| --- | --- |
| Calls, tokens, and completion per build | `results/part1_*_180s.json` (three trials each, 180-second cutoff) |
| The first runaway trace | `results/part1_coordinator_first_run.json` |
| Sequential versus parallel research timing | `spans` in `results/part1_graph.json` and `results/part1_graph_sequential.json` |
| A sequential chain loses research without a state template | `python -m failures.sequential_state` |
| Deprecation text, `Workflow` sub-agent refusal, tool schema rule | `tests/test_part1_claims.py` |
| Part 2: sessions, state prefixes, direct state writes | `tests/test_part2_claims.py` |
| Part 2: standing rule followed or broken, per build | `results/part2_handoff.json` and `results/part2_handoff_run1.json` |
| Part 2: input tokens per turn, compaction cost | `results/part2_window.json` and `results/part2_window_run1.json` |
| Part 3: calls, tokens, and outcome per loop build | `results/part3_loops.json` (three trials each, 300-second cutoff) |
| Part 3: judge verdicts on four planted drafts | `results/part3_judge.json` |
| Part 3: replies returned with and without a response schema | `results/part3_structured_output.json` |
| Part 3: cycles, the unstopped loop, the skipped join | `tests/test_part3_claims.py` |
| Part 4: harmful calls, pauses, exports, and tokens per connection | `results/part4_access.json` (ten runs per setup) and `results/part4_access_run1.json` |
| Part 4: tool exposure, filter, confirmation scope, description pass-through | `tests/test_part4_claims.py` |
| Part 5: outcome per build and question, searches, and tokens | `results/part5_answers.json` (ten runs per cell) |
| Part 5: search behavior, date visibility, the figure check, the grader | `tests/test_part5_claims.py` |
| Part 5: the same builds on Vertex AI Search | `results/part5_answers_vertex.json` (ten runs per cell) |
| Part 5: ADK's built-in search tool, with the documents the service cited | `results/part5_answers_grounded.json` |
| Part 6: harmful calls per defense | `results/part6_defenses.json` (ten runs per defense and server) |
| Part 6: what each approver was shown and approved | `results/part6_approval.json` |
| Part 6: the guard and the approvers | `tests/test_part6_claims.py` |
| Part 7: calls with and without an identity token | `results/part7_auth_memory.json` |
| Part 7: session lookups across three instances | `results/part7_sessions_memory.json`, `results/part7_sessions_agentengine.json` |
| Part 7: the two-request conversation over HTTP | `results/part7_team_memory.json`, `results/part7_team_agentengine.json` |

Costs in the article use the listed Gemini API price for `gemini-3.5-flash` at the time of the runs: $1.50 per million input tokens and $9.00 per million output tokens, with thinking billed as output. Model output varies from run to run, so expect your token counts to land near these, not on them.

## Layout

| Path | Holds |
| --- | --- |
| `workforce/cast.py` | The shared agents, stub tools, and output contracts |
| `workforce/topologies/` | One module per build |
| `workforce/context/` | Part 2: handoff and context-window experiments |
| `workforce/review/` | Part 3: the review loop and the judge test |
| `workforce/tools/` | Part 4: the DesignDesk MCP server and the three connections |
| `workforce/knowledge/` | Part 5: the company library, its two searches, and the answering agent |
| `workforce/trust/` | Part 6: the code guard and the approval run |
| `deploy/`, `Dockerfile` | Part 7: the team as a Cloud Run service |
| `infra/` | Terraform for the Google Cloud resources Parts 5 and 7 use |
| `workforce/harness.py` | Runs a build, single message or multi-turn, and records calls, tokens, timing, and a trace |
| `run_part1.py` to `run_part7.py` | Command-line runners |
| `failures/` | Reproductions of failures the articles describe (these call the model) |
| `tests/` | Framework claims, checked without a model |
| `results/` | Recorded runs behind the published numbers |

## Development

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest -q
```

## Roadmap

Parts 1 to 7 are complete.

## License

Copyright 2026 Robert H. Mowery III. Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
