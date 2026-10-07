# Contributing

This repository is the reference code for a published article series. Its first job is to match the articles exactly, so that a reader who copies a snippet gets what the article describes.

## Reporting a problem

Open an issue if a build does not behave the way an article says it does. Please include:

- The output of `pip show google-adk` (the code is pinned to one ADK release on purpose)
- The command you ran
- The JSON line the runner printed, or the test failure

Different token counts from run to run are expected. A different outcome, such as a build that finishes when the article says it loops, is worth an issue.

## Proposing a change

Pull requests are welcome for bugs, clearer documentation, and updates for a newer ADK release. Before you open one:

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest -q
```

Two things to know before you edit agent code:

- Every `instruction`, `description`, tool docstring, and Pydantic schema is sent to the model. Rewording one changes the experiment, and the recorded results in `results/` no longer describe the code.
- Each article's numbers come from the files in `results/`. A change that alters behavior needs fresh runs to go with it.

## License

By contributing, you agree that your contributions are licensed under the Apache License, Version 2.0.
