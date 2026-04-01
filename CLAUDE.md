# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install with dev dependencies
uv sync --group dev

# Lint
ruff check src/batuta/

# Auto-fix lint issues
ruff check src/batuta/ --fix

# Type check (strict mode)
mypy src/batuta/

# Run the CLI
uv run batuta --help
```

## Architecture

```
src/batuta/
├── cli/          # Typer commands — argument parsing and rich output only
├── core/         # Business logic — importable as a library
├── models/       # Pydantic v2 data models
├── utils/        # Shared utilities: deps checker, output helpers, process wrapper
└── exceptions.py # Typed exception hierarchy
```

### Key Constraints

- `cli/` **never** contains business logic — it only calls into `core/`
- All subprocess invocations go through `utils/process.py` (`run_tool()`)
- All external tool requirements are checked at command entry via `utils/deps.py` (`require()`)
- mypy is configured in strict mode — all new code must be fully typed

### Exception Hierarchy

All exceptions inherit from `BatutaError`. Use typed subclasses (`ToolNotFoundError`, `ADBError`, `ProcessError`, etc.) rather than bare exceptions. `ProcessError` is raised automatically by `run_tool()` on non-zero exit.

### External Tool Resolution

`utils/deps.py` checks for `adb`, `apktool`, `jadx`, and `APKEditor`. Call `require("tool")` at the top of any CLI command that needs an external tool. `APKEditor` has special resolution logic: `APKEDITOR_JAR` env var → `~/.batuta/config.json` → `APKEditor` wrapper on `PATH`.

### Ruff Config Notes

`B008` (function calls in defaults) is suppressed for `src/batuta/cli/*.py` because Typer uses this pattern by design.
