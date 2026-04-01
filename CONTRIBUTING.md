# Contributing to Vigil

Thanks for your interest in contributing. Vigil is a TUI tool for
monitoring ML training jobs on cloud GPU instances. Contributions from
ML researchers and practitioners are welcome.

## Setup

```bash
git clone https://github.com/<your-fork>/vigil.git
cd vigil
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
python -m pytest tests/ -x -q
```

## Project Structure

```
src/vigil/
    app.py              # Textual app entry point and screen management
    config.py           # YAML config loading, validation, persistence
    discovery.py        # Provider API client (instance discovery)
    collector.py        # Async SSH log streaming with reconnection
    parser.py           # Regex-based metric parsing
    storage.py          # Local log persistence (~/.vigil/logs/)
    alerts.py           # Alert detection (NaN, plateau, stall)
    notifications.py    # Desktop and webhook alert dispatch
    ssh.py              # SSH connection management
    presets.py          # Framework detection and metric presets
    state.py            # Persistent UI/onboarding state
    widgets/            # Textual widgets (panels, sparklines, tables, overlays)
tests/
    ...                 # Mirrors src layout
```

## Adding a New Metric Pattern

Metric patterns live in `src/vigil/config.py` as `DEFAULT_METRIC_PATTERNS`.
Each pattern is a regex with named capture groups. To add one:

1. Add your regex to the `DEFAULT_METRIC_PATTERNS` list in `config.py`. Use a named
   group for the value, e.g. `r"grad_norm[=:\s]+(?P<grad_norm>[\d.]+)"`.
2. Add a test in `tests/test_parser.py` with representative log lines.
3. If the metric needs special visualization (e.g., it should go up, not down),
   add it to the appropriate list (`decrease_good` or `increase_good`) in `config.py`.

Users can also define custom patterns in their `config.yaml` without code
changes.

## Adding a New Widget or Screen

Widgets are Textual components in `src/vigil/widgets/`.

1. Create a new file under `widgets/` with a class inheriting from the
   appropriate Textual base (`Static`, `Widget`, `Container`, etc.).
2. Keep the widget self-contained: it should accept data via messages or
   reactive attributes, not reach into global state.
3. Register it in the relevant screen's `compose()` method.
4. Export it from `widgets/__init__.py`.
5. Add tests for any non-trivial logic the widget contains.

For a new screen, subclass `textual.screen.Screen` and register it in
`app.py`.

## Code Style

- Standard Python 3. Use type hints for function signatures and class
  attributes.
- No strict formatter is enforced yet. Keep code readable and consistent
  with the surrounding files.
- Docstrings on public classes and functions.

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Make your changes. Add or update tests as needed.
3. Run `python -m pytest tests/ -x -q` and confirm everything passes.
4. Open a PR against `main` with a clear description of what changed and why.
5. Keep PRs focused -- one feature or fix per PR.

## Reporting Issues

Open a GitHub issue with:
- What you expected to happen.
- What actually happened (include tracebacks if applicable).
- Your Python version, OS, and vigil version (`vigil --version` or `python -c "import vigil; print(vigil.__version__)"`).
