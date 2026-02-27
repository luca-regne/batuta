# batuta

> Batuta is a Brazilian Portuguese word that means "baton" in English. Like a conductor's baton that directs an orchestra, **batuta** aims to be the main tool to orchestrates Android reverse engineering.

`batuta` is a Python CLI for static Android application analysis — designed for penetration testers, bug bounty hunters, and malware analysts. It wraps battle-tested RE tools (`apktool`, `jadx`, `adb`, `APKEditor`) behind a clean, composable interface.

---

## Features

- **APK pulling** — pull APKs by package name, app name, or filter pattern
- **Split APK support** — automatically detects split packages, pulls every part, and merges them via `batuta apk merge` or `--auto-merge`
- **Decompilation** — run `jadx` and/or `apktool` via `batuta apk decompile` or `batuta apk pull --decompile`
- **APK patching** — rebuild, align, sign, and optionally install via `batuta apk patch`
- **Interactive selection** — choose from multiple matches when searching (prompted automatically)
- **Scriptable by design** — every command supports `--json` output for piping into `jq`, `grep`, or custom tooling
- **Library-first architecture** — core logic is importable independently of the CLI

---

## Requirements

### Python

- Python >= 3.14

### External Tools

These must be installed and available on your `PATH`:

| Tool        | Purpose                                     | Install                                                                                   |
| ----------- | ------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `adb`       | Android Debug Bridge — device communication | [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) |
| `apktool`   | APK decoding, smali disassembly             | [Apktool Webiste](https://apktool.org/)                                                   |
| `jadx`      | Java/Kotlin decompilation                   | [Jadx GitHub Repository](https://github.com/skylot/jadx)                                  |
| `APKEditor` | Split APK merging                           | [APKEditor Repository](https://github.com/REAndroid/APKEditor)                            |

`batuta` checks for required tools at command entry and reports clear installation instructions when missing.

### Configuring APKEditor

`APKEditor` ships as a JAR file. Batuta resolves it in this order:

1. `APKEDITOR_JAR` environment variable (points to the `.jar` or its parent directory)
2. `~/.batuta/config.json` → `apkeditor_path`
3. Executable wrapper called `APKEditor` somewhere on `PATH`

Examples:

```bash
# 1. Environment variable (temporary for current shell)
export APKEDITOR_JAR="$HOME/tools/APKEditor/APKEditor.jar"

# 2. Config file (~/.batuta/config.json)
{
  "apkeditor_path": "~/tools/APKEditor/APKEditor.jar"
}

# 3. Wrapper script placed on PATH (e.g., /usr/local/bin/APKEditor)
#!/bin/bash
exec java -jar "$HOME/tools/APKEditor/APKEditor.jar" "$@"
```

You can point `apkeditor_path` to either the JAR file itself or the directory
containing `APKEditor.jar`. Batuta keeps the pulled split directory intact after
merging, regardless of the resolution method you use.

---

## Installation

Install from source with Poetry:

```bash
git clone https://github.com/luca-regne/batuta
cd batuta
poetry install
```

Or with pip:

```bash
pip install -e .
```

---

## Quick Start

```bash
# List connected devices
batuta device list

# Search for packages by name
batuta apk search google

# Get detailed info about a package
batuta apk info com.example.app

# Pull an APK (supports partial names and filters)
batuta apk pull youtube

# Pull with interactive selection when multiple matches (prompted automatically)

# Pull to a specific directory
batuta apk pull com.example.app --output ./apks/

# Pull and immediately decompile
batuta apk pull com.example.app --decompile

# Standalone decompile from local APK
batuta apk decompile ./apks/com.example.app.apk --java-only

# Merge a split APK directory (keeps original files)
batuta apk merge ./apks/com.example.app --output ./apks/com.example.app.merged.apk
```

---

## Command Reference

```
batuta
├── device
│   ├── list                       List connected ADB devices
│   └── shell [COMMAND...]         Open ADB shell (or run command)
│
└── apk
    ├── list                       List installed packages
    ├── search <query>             Search packages by name or filter
    ├── info <query>               Show detailed package information
    ├── pull <query>               Pull APK from connected device (optional decompile)
    ├── merge <dir>                Merge split APK folder into a single APK (keeps folder)
    ├── patch <apktool-dir>        Build/align/sign APK from apktool output
    └── decompile <apk>            Decompile APK to Java and/or smali
```

### Common Options

| Option           | Description                                        |
| ---------------- | -------------------------------------------------- |
| `--device`, `-d` | Target specific device by ID                       |
| `--json`, `-j`   | Output as JSON for scripting                       |
| `--system`, `-s` | Include system packages in search                  |
| `--decompile`    | (pull) Decompile after pulling (Java + smali)      |
| `--auto-merge`   | (pull) Merge split APK folders via APKEditor       |
| `--java-only`    | (pull/decompile) Limit to Java (`jadx`) output     |
| `--smali-only`   | (pull/decompile) Limit to smali/resources (`apktool`)

Split APK pulls always save the original directory of base/split parts.
Use `--auto-merge` for immediate merging (the folder stays untouched) or
run `batuta apk merge <dir>` later. When `--decompile` is supplied, splits
are merged automatically so jadx/apktool can run without extra steps.

### Examples

```bash
# JSON output for scripting
batuta device list --json | jq '.[0].id'
batuta apk search facebook --json | jq '.[].package_name'

# Target specific device
batuta apk pull com.example.app --device RX8WC00D7JE

# Include system packages
batuta apk list --system --filter android
```

---

## Library Usage

The core logic is importable independently of the CLI:

```python
from batuta.core.adb import ADBWrapper

# List devices
adb = ADBWrapper()
devices = adb.list_devices()
for device in devices:
    print(f"{device.id}: {device.model} ({device.state})")

# Search packages
packages = adb.search_packages("google")
for pkg in packages:
    print(f"{pkg.package_name} v{pkg.version_name}")

# Pull an APK
result = adb.pull_apk("com.example.app", output_dir=Path("./apks"))
print(f"Pulled to: {result.local_path}")
```

---

## Architecture

```
src/batuta/
├── cli/          # Typer commands — argument parsing and rich output only
├── core/         # Business logic — importable as a library
├── models/       # Pydantic v2 data models
├── utils/        # Shared utilities: deps checker, output helpers, process wrapper
└── exceptions.py # Typed exception hierarchy
```

Key architectural constraints:

- `cli/` never contains business logic — only calls into `core/`
- All subprocess invocations go through `utils/process.py`
- All external tool requirements are checked at command entry via `utils/deps.py`

---

## Development

```bash
# Install with dev dependencies
poetry install --with dev

# Lint
ruff check src/batuta/

# Auto-fix lint issues
ruff check src/batuta/ --fix

# Type check
mypy src/batuta/

# Run the CLI
poetry run batuta --help
```

---

## License

MIT
