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

These tests construct agents and workflows but never call a model, so they are free and finish in about a second.

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

Costs in the article use the listed Gemini API price for `gemini-3.5-flash` at the time of the runs: $1.50 per million input tokens and $9.00 per million output tokens, with thinking billed as output. Model output varies from run to run, so expect your token counts to land near these, not on them.

## Layout

| Path | Holds |
| --- | --- |
| `workforce/cast.py` | The shared agents, stub tools, and output contracts |
| `workforce/topologies/` | One module per build |
| `workforce/context/` | Part 2: handoff and context-window experiments |
| `workforce/review/` | Part 3: the review loop and the judge test |
| `workforce/harness.py` | Runs a build, single message or multi-turn, and records calls, tokens, timing, and a trace |
| `run_part1.py`, `run_part2.py`, `run_part3.py` | Command-line runners |
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

Parts 1 to 3 are complete. Later installments cover MCP and outside tools, retrieval, cross-project trust, and operations. Code for each lands here as its article publishes.

## License

Copyright 2026 Robert H. Mowery III. Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
