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

Costs in the article use the listed Gemini API price for `gemini-3.5-flash` at the time of the runs: $1.50 per million input tokens and $9.00 per million output tokens, with thinking billed as output. Model output varies from run to run, so expect your token counts to land near these, not on them.

## Layout

| Path | Holds |
| --- | --- |
| `workforce/cast.py` | The shared agents, stub tools, and output contracts |
| `workforce/topologies/` | One module per build |
| `workforce/harness.py` | Runs a build and records calls, tokens, timing, and a trace |
| `run_part1.py` | Command-line runner |
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

Part 1 is complete. Later installments cover context and state, loops and judges, MCP and outside tools, retrieval, cross-project trust, and operations. Code for each lands here as its article publishes.

## License

Copyright 2026 Robert H. Mowery III. Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
