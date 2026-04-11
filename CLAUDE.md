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

There are no automated tests. Validate changes by running the CLI directly.

## CLI Structure

Three top-level command groups:

| Group            | Commands                                                        | Purpose                             |
| ---------------- | --------------------------------------------------------------- | ----------------------------------- |
| `batuta apk`     | `list`, `search`, `info`, `pull`, `merge`, `decompile`, `patch` | Device/APK management               |
| `batuta analyze` | `manifest`, `framework`                                         | Static analysis without decompiling |
| `batuta device`  | (device management)                                             | ADB device operations               |

All commands accept `--json` / `-j` for machine-readable output. When `--json` is active, `console.*` output is suppressed — only `typer.echo(json.dumps(...))` goes to stdout.

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

### Output Pattern

Use `utils/output.py`'s global `console` singleton for all terminal output. Call `console.set_json_mode(json_output)` at the start of every command. In JSON mode all `console.*` calls are no-ops — use `typer.echo(json.dumps(...))` for structured output.

### Exception Hierarchy

All exceptions inherit from `BatutaError`. Use typed subclasses (`ToolNotFoundError`, `ADBError`, `ProcessError`, etc.) rather than bare exceptions. `ProcessError` is raised automatically by `run_tool()` on non-zero exit.

CLI commands catch `BatutaError`, print via `console.print_error()`, and `raise typer.Exit(1) from None`.

### External Tool Resolution

- `utils/deps.py` checks for external required tools such as `adb`, `apktool`, `jadx`, and `APKEditor`.
- Call `require("tool")` at the top of any CLI command that needs an external tool.
- For special cases, such as `APKEditor` jar file, use a special resolution logic:
  1. `APKEDITOR_JAR` env var
  2. `~/.batuta/config.json`
  3. `APKEditor` wrapper on `PATH`.

### Ruff Config Notes

`B008` (function calls in defaults) is suppressed for `src/batuta/cli/*.py` because Typer uses this pattern by design.
