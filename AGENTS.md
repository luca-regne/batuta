# AGENTS.md — batuta

Quick reference for AI coding agents working on batuta.

---

## Project Overview

**batuta** is a Python CLI tool for static Android application analysis. Like a conductor's baton that orchestrates an ensemble, it coordinates industry-standard RE tools (`apktool`, `jadx`, `baksmali`, `adb`) into a unified, scriptable pipeline designed for penetration testers and malware analysts.

**Core Philosophy:**

- Static analysis first
- Every command must be scriptable and composable (pipes, `grep`, `jq`)
- Workspace-based state — persist analysis artifacts across sessions
- Library-first architecture: core logic must be importable independently of the CLI

---

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies (when available)
uv sync --group dev

# Lint with ruff
uv run ruff check src/batuta/

# Auto-fix lint issues
uv run ruff check src/batuta/ --fix

# Type check with mypy
uv run mypy src/batuta/

# Run the CLI during development
uv run batuta --help
```

---

## Project Layout

```
src/batuta/
├── cli/           # Typer commands (thin layer, no business logic)
├── core/          # Business logic (importable as library)
├── models/        # Pydantic v2 data models
├── utils/         # Shared utilities (deps, output, process wrapper)
└── exceptions.py  # Custom exception hierarchy
```

---

## Tech Stack

| Purpose          | Library        |
| ---------------- | -------------- |
| CLI framework    | `typer`        |
| Terminal output  | `rich`         |
| Data validation  | `pydantic` v2  |
| APK/DEX parsing  | `androguard`   |
| Manifest parsing | `pyaxmlparser` |
| Testing          | `pytest`       |
| Linting          | `ruff`         |
| Type checking    | `mypy`         |

---

## Command Structure Reference

```
batuta
├── device
│   ├── list                    # List connected ADB devices
│   ├── shell [--device <id>]   # Open ADB shell
│   └── select <device-id>      # Set default device in workspace
│
├── apk
│   ├── pull <package>          # Pull APK from device
│   ├── install <apk>           # Install APK to device
│   ├── merge <dir>             # Merge split APKs from directory
│   ├── decompile <apk>         # Full decompile (smali + java + res)
│   ├── smali <apk>             # Smali only (via apktool)
│   ├── java <apk>              # Java only (via jadx)
│   └── resources <apk>         # Resources only (via apktool)
│
├── analyze
│   ├── framework <apk>         # Detect framework (RN, Flutter, Xamarin...)
│   ├── manifest <apk>          # Parse and display manifest info
│   ├── surface <apk>           # Attack surface (exported components)
│   └── secrets <apk>           # Scan for hardcoded secrets/endpoints
│
├── flutter
│   ├── patch <package|apk>     # Patch with reflutter, install, and dump Dart code
│   └── dump <package>          # Dump Dart code from instrumented app
│
└── workspace
    ├── init <package|apk>      # Create new analysis workspace
    ├── status                  # Show current workspace state
    └── clean                   # Remove intermediate artifacts
```

---

## Framework Detection Signatures

```python
FRAMEWORK_SIGNATURES = {
    "React Native": [
        "lib/arm64-v8a/libreactnativejni.so",
        "lib/x86/libreactnativejni.so",
        "assets/index.android.bundle",
        "com/facebook/react",
    ],
    "Flutter": [
        "lib/arm64-v8a/libflutter.so",
        "lib/x86_64/libflutter.so",
        "assets/flutter_assets/",
    ],
    "Xamarin": [
        "assemblies/Xamarin.Android.dll",
        "lib/x86/libmonosgen-2.0.so",
        "lib/arm64-v8a/libmonosgen-2.0.so",
    ],
    "Cordova / Ionic": [
        "assets/www/cordova.js",
        "assets/www/cordova_plugins.js",
    ],
    "Unity": [
        "lib/arm64-v8a/libunity.so",
        "assets/bin/Data/",
    ],
    "Kotlin Multiplatform": [
        "lib/arm64-v8a/libkotlin_lib.so",
    ],
}
```

Detection should use `zipfile.ZipFile` for performance — do not fully extract the APK just to detect frameworks.

---

## Code Style Guidelines

### Imports

Order imports in three groups separated by blank lines:

1. Standard library
2. Third-party packages
3. Local imports

```python
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from rich.console import Console
import typer

from batuta.core.analyzer import FrameworkDetector
from batuta.exceptions import BatonError
```

### Type Hints

- Use type hints on all function signatures
- Use `Path` from `pathlib` for file paths, not `str`
- Use Pydantic models for structured data, not raw dicts
- Prefer `list[str]` over `List[str]` (Python 3.9+ syntax)

```python
def detect_frameworks(apk_path: Path) -> list[str]:
    ...

def parse_manifest(apk_path: Path, output_format: str = "table") -> ManifestInfo:
    ...
```

### Naming Conventions

| Type         | Convention         | Example                                      |
| ------------ | ------------------ | -------------------------------------------- |
| Classes      | PascalCase         | `FrameworkDetector`, `ManifestParser`        |
| Functions    | snake_case         | `detect_frameworks`, `parse_manifest`        |
| Constants    | UPPER_SNAKE        | `FRAMEWORK_SIGNATURES`, `DEFAULT_TIMEOUT`    |
| Private      | Leading underscore | `_validate_path`, `_internal_cache`          |
| CLI commands | kebab-case         | `batuta apk decompile`, `batuta device list` |

### Error Handling

Define typed exceptions in `batuta/exceptions.py`:

```python
class BatonError(Exception): ...
class ToolNotFoundError(BatonError): ...
class DeviceNotConnectedError(BatonError): ...
class WorkspaceError(BatonError): ...
class APKParseError(BatonError): ...
```

- Raise typed exceptions in `core/` modules
- Catch and format them in `cli/` modules
- Use `typer.Exit(code=1)` for CLI errors, never `sys.exit()`

### Output

Always use `rich` for terminal output. Never use `print()`.

```python
from batuta.utils.output import console

console.print_success("APK pulled successfully")   # green
console.print_error("apktool not found")           # red
console.print_info("Decompiling...")               # blue
console.print_warning("No secrets found")          # yellow
```

All commands must support `--json` for machine-readable output.

---

## Architecture Rules

### 1. CLI layer contains NO business logic

```python
# CORRECT - cli/apk.py
@app.command()
def decompile(apk_path: Path):
    result = APKToolWrapper(apk_path).decode()
    console.print_success(f"Decompiled to {result.output_dir}")

# WRONG - business logic in CLI
@app.command()
def decompile(apk_path: Path):
    subprocess.run(["apktool", "d", str(apk_path)])  # NO
```

### 2. All subprocess calls go through the wrapper

```python
# CORRECT
from batuta.utils.process import run_tool
result = run_tool(["apktool", "d", str(apk_path)])

# WRONG - direct subprocess in core/
import subprocess
subprocess.run(["apktool", ...])  # NO
```

### 3. Check dependencies at command entry

```python
from batuta.utils.deps import require

@app.command()
def decompile(...):
    require("apktool", "jadx")  # Raises if missing
    ...
```

### 4. Core modules must be importable as a library

```python
# This must always work without CLI
from batuta.core.analyzer import FrameworkDetector
detector = FrameworkDetector("/path/to/app.apk")
frameworks = detector.detect()
```

---

## External Tools

Required on PATH (checked at runtime):

- `adb` - Android Debug Bridge
- `apktool` - APK decoding/smali
- `jadx` - Java decompilation
- `APKEditor` - Split APK merging

---

## Testing Guidelines

- Use `pytest` with `tmp_path` fixture for workspace tests
- Mock all subprocess calls — never run `adb` or `apktool` in unit tests
- Place small test APKs (< 1MB) in `tests/fixtures/`
- Every `core/` module must have a corresponding test file

---

## Quick Reference

| Task       | Command                   |
| ---------- | ------------------------- |
| Lint       | `ruff check src/batuta/`  |
| Type check | `mypy src/batuta/`        |
| Run CLI    | `python -m batuta --help` |
| Run tests  | `pytest tests/ -v`        |
