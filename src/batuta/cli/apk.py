"""CLI commands for APK management."""

import json
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.table import Table

from batuta.core.adb import ADBWrapper
from batuta.core.decompiler import APKDecompiler
from batuta.exceptions import (
    BatutaError,
    MultiplePackagesFoundError,
    PackageNotFoundError,
)
from batuta.models.apk import DecompileResult, PackageInfo
from batuta.utils.deps import require
from batuta.utils.output import console

app = typer.Typer(no_args_is_help=True)


def _display_package_table(packages: list[PackageInfo], query: str) -> None:
    """Display a table of packages for selection."""
    console.print(f"\n[yellow]Multiple packages match '{query}':[/yellow]\n")

    table = Table()
    table.add_column("#", style="cyan", width=4)
    table.add_column("Package Name", style="green")

    for i, pkg in enumerate(packages, 1):
        table.add_row(str(i), pkg.package_name)

    console.print(table)
    console.print()


def _parse_selection(choice: str, max_idx: int) -> list[int] | None:
    """Parse user selection input.

    Supports:
    - Single number: "1"
    - Comma-separated: "1,3,5"
    - Ranges: "1-5"
    - Mixed: "1,3-5,7"
    - All: "a" or "all"

    Returns list of 0-based indices or None if invalid.
    """
    choice = choice.strip().lower()

    if choice in ("a", "all"):
        return list(range(max_idx))

    indices: set[int] = set()
    parts = choice.replace(" ", "").split(",")

    for part in parts:
        if "-" in part:
            # Range: "1-5"
            try:
                start, end = part.split("-", 1)
                start_idx = int(start) - 1
                end_idx = int(end) - 1
                if start_idx < 0 or end_idx >= max_idx or start_idx > end_idx:
                    return None
                indices.update(range(start_idx, end_idx + 1))
            except ValueError:
                return None
        else:
            # Single number
            try:
                idx = int(part) - 1
                if idx < 0 or idx >= max_idx:
                    return None
                indices.add(idx)
            except ValueError:
                return None

    return sorted(indices) if indices else None


def _select_package(
    packages: list[PackageInfo], query: str, multiple: bool = False
) -> list[PackageInfo]:
    """Interactive package selection.

    Args:
        packages: List of packages to select from.
        query: Original search query (for display).
        multiple: If True, allow selecting multiple packages.

    Returns:
        List of selected PackageInfo objects.
    """
    _display_package_table(packages, query)

    if multiple:
        prompt_msg = "Select packages (e.g., 1,3-5 or 'a' for all, 'q' to quit)"
    else:
        prompt_msg = "Select package number (or 'q' to quit)"

    while True:
        choice = typer.prompt(prompt_msg)
        if choice.lower() == "q":
            raise typer.Abort()

        if multiple:
            indices = _parse_selection(choice, len(packages))
            if indices is not None:
                return [packages[i] for i in indices]
            console.print_error(
                f"Invalid selection. Enter 1-{len(packages)}, ranges (1-3), "
                "comma-separated (1,3,5), or 'a' for all"
            )
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(packages):
                    return [packages[idx]]
                console.print_error(f"Invalid choice. Enter 1-{len(packages)}")
            except ValueError:
                console.print_error("Please enter a number")


@app.command("list")
def list_packages(
    filter_query: str = typer.Argument(
        None,
        help="Query to filter package names.",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Include system packages.",
    ),
    detailed: bool = typer.Option(
        False,
        "--detailed",
        help="Fetch full package metadata (slower).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """List installed packages on device."""
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)

        if filter_query:
            packages = adb.search_packages(
                filter_query,
                include_system=system,
                detailed=detailed,
            )
        else:
            if detailed:
                # Get all package names then fetch details
                pkg_names = adb.list_packages(include_system=system)
                packages = []
                for name in pkg_names:
                    try:
                        packages.append(adb.get_package_info(name))
                    except Exception:
                        packages.append(PackageInfo(package_name=name))
            else:
                pkg_names = adb.list_packages(include_system=system)
                packages = [PackageInfo(package_name=name) for name in pkg_names]

        if json_output:
            output = [pkg.model_dump(exclude_none=True) for pkg in packages]
            typer.echo(json.dumps(output, indent=2))
            return

        if not packages:
            console.print_warning("No packages found")
            raise typer.Exit(1) from None

        table = Table(title=f"Installed Packages ({len(packages)})")
        table.add_column("Package Name", style="cyan")

        if detailed:
            table.add_column("Version")
            table.add_column("Split")

            for pkg in packages:
                table.add_row(
                    pkg.package_name,
                    pkg.version_name or "-",
                    "Yes" if pkg.is_split else "No",
                )
        else:
            for pkg in packages:
                table.add_row(pkg.package_name)

        console.print(table)

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("info")
def package_info(
    query: str = typer.Argument(
        ...,
        help="Package name or filter (substring match).",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Include system packages in search.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Show detailed information about a package."""
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)

        try:
            match = adb.find_package(query, include_system=system)
        except MultiplePackagesFoundError:
            if not json_output:
                matches = adb.search_packages(query, include_system=system)
                selected = _select_package(matches, query, multiple=False)
                match = selected[0]
            else:
                raise

        pkg = adb.get_package_info(match.package_name)

        if json_output:
            typer.echo(json.dumps(pkg.model_dump(exclude_none=True), indent=2))
            return

        console.print(f"\n[bold cyan]{pkg.package_name}[/bold cyan]\n")
        if pkg.version_name:
            console.print(f"  Version:      {pkg.version_name}")
        if pkg.version_code:
            console.print(f"  Version Code: {pkg.version_code}")
        if pkg.min_sdk:
            console.print(f"  Min SDK:      {pkg.min_sdk}")
        if pkg.target_sdk:
            console.print(f"  Target SDK:   {pkg.target_sdk}")
        if pkg.signing_version:
            console.print(f"  Signing Ver:  {pkg.signing_version}")
        if pkg.apk_path:
            console.print(f"  APK Path:     {pkg.apk_path}")
        if pkg.is_split:
            console.print(f"  Split APKs:   {len(pkg.split_apks or [])} files")
            for split in pkg.split_apks or []:
                console.print(f"               - {Path(split).name}")

        console.print()

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("pull")
def pull_apk(
    query: str = typer.Argument(
        ...,
        help="Package name or filter to pull (substring match).",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    output_dir: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: current directory).",
    ),
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Include system packages in search.",
    ),
    pull_all: bool = typer.Option(
        False,
        "--all",
        help="Pull all packages matching the filter instead of selecting one.",
    ),
    decompile: bool = typer.Option(
        False,
        "--decompile",
        help="Decompile APK after pulling (Java + smali).",
    ),
    java_only: bool = typer.Option(
        False,
        "--java-only",
        help="With --decompile: only decompile to Java source.",
    ),
    smali_only: bool = typer.Option(
        False,
        "--smali-only",
        help="With --decompile: only decompile to smali/resources.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Pull APK from connected device.

    Supports pulling by:
    - Exact package name (com.example.app)
    - Partial package name (example.app)
    - Filter pattern (google, facebook)

    For split APKs, all parts are pulled into a directory.

    Use --decompile to automatically decompile after pulling.
    Note: --decompile does not support split APKs yet.
    """
    require("adb")

    if (java_only or smali_only) and not decompile:
        console.print_error("--java-only and --smali-only require --decompile")
        raise typer.Exit(1)

    if java_only and smali_only:
        console.print_error("Cannot use both --java-only and --smali-only")
        raise typer.Exit(1)

    if decompile:
        if not smali_only:
            require("jadx")
        if not java_only:
            require("apktool")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)

        # Determine which packages to pull (fast search, no metadata)
        if pull_all:
            matches = adb.search_packages(query, include_system=system)
            if not matches:
                raise PackageNotFoundError(query)
            package_names = [m.package_name for m in matches]
        else:
            try:
                match = adb.find_package(query, include_system=system)
                package_names = [match.package_name]
            except MultiplePackagesFoundError:
                if not json_output:
                    matches = adb.search_packages(query, include_system=system)
                    selected = _select_package(matches, query, multiple=True)
                    package_names = [m.package_name for m in selected]
                else:
                    raise

        results = []
        decompile_results: list[DecompileResult | None] = []

        for package_name in package_names:
            if not json_output:
                console.print_info(f"Pulling {package_name}...")

            status_label = f"Pulling {package_name}"
            with console.status(status_label) if not json_output else nullcontext():
                result = adb.pull_apk(package_name, output_dir=output_dir)

            results.append(result)

            if not json_output:
                console.print_success(f"Pulled to {result.local_path}")

                if result.is_split and result.split_paths:
                    console.print_info(f"  {len(result.split_paths)} APK files:")
                    for p in result.split_paths:
                        console.print(f"    - {p.name}")

            if decompile:
                if result.is_split:
                    if not json_output:
                        console.print_warning(
                            "  Skipping decompile: split APKs not supported yet. "
                        )
                    decompile_results.append(None)
                else:
                    if not json_output:
                        console.print_info(f"  Decompiling {result.local_path.name}...")

                    decompiler = APKDecompiler(result.local_path)
                    do_java = not smali_only
                    do_smali = not java_only

                    with (
                        console.status("  Decompiling...")
                        if not json_output
                        else nullcontext()
                    ):
                        dec_result = decompiler.decompile(java=do_java, smali=do_smali)

                    decompile_results.append(dec_result)

                    if not json_output:
                        console.print_success(
                            f"  Decompiled to {dec_result.output_dir}"
                        )

        if json_output:
            output_items = []
            for i, result in enumerate(results):
                item: dict[str, object] = {
                    "package_name": result.package_name,
                    "local_path": str(result.local_path),
                    "is_split": result.is_split,
                }
                if result.split_paths:
                    item["split_paths"] = [str(p) for p in result.split_paths]

                if decompile and i < len(decompile_results):
                    decompile_item = decompile_results[i]
                    if decompile_item is not None:
                        dec_data: dict[str, object] = {
                            "output_dir": str(decompile_item.output_dir),
                            "java_success": decompile_item.java_success,
                            "smali_success": decompile_item.smali_success,
                        }
                        if decompile_item.java_dir:
                            dec_data["java_dir"] = str(decompile_item.java_dir)
                        if decompile_item.smali_dir:
                            dec_data["smali_dir"] = str(decompile_item.smali_dir)
                        item["decompile"] = dec_data
                    else:
                        item["decompile"] = None  # Split APK, skipped

                output_items.append(item)

            payload: list[dict[str, object]] | dict[str, object]
            if pull_all or len(output_items) > 1:
                payload = output_items
            else:
                payload = output_items[0]

            typer.echo(json.dumps(payload, indent=2))
            return

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("search")
def search_packages(
    query: str = typer.Argument(
        ...,
        help="Search query (substring match against package names).",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Include system packages.",
    ),
    detailed: bool = typer.Option(
        False,
        "--detailed",
        help="Fetch full package metadata (slower).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Search for packages by name.

    By default, searches package names only (fast).
    Use --detailed to fetch full package metadata (slower).
    """
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)
        packages = adb.search_packages(query, include_system=system, detailed=detailed)

        if json_output:
            output = [pkg.model_dump(exclude_none=True) for pkg in packages]
            typer.echo(json.dumps(output, indent=2))
            return

        if not packages:
            console.print_warning(f"No packages found matching '{query}'")
            raise typer.Exit(1) from None

        table = Table(title=f"Packages matching '{query}' ({len(packages)})")
        table.add_column("Package Name", style="cyan")

        if detailed:
            table.add_column("Version")
            table.add_column("Split")

            for pkg in packages:
                table.add_row(
                    pkg.package_name,
                    pkg.version_name or "-",
                    "Yes" if pkg.is_split else "No",
                )
        else:
            for pkg in packages:
                table.add_row(pkg.package_name)

        console.print(table)

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("patch")
def patch_apk(
    apktool_dir: Path = typer.Argument(
        ...,
        help="Path to apktool-decoded directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output APK path (default: <dir>-patched.apk).",
    ),
    keystore: Path = typer.Option(
        None,
        "--keystore",
        "-k",
        help="Keystore file (default: auto-generate debug keystore).",
    ),
    key_alias: str = typer.Option(
        "androiddebugkey",
        "--key-alias",
        help="Key alias in keystore.",
    ),
    keystore_pass: str = typer.Option(
        "android",
        "--keystore-pass",
        help="Keystore password.",
    ),
    key_pass: str = typer.Option(
        "android",
        "--key-pass",
        help="Key password.",
    ),
    no_sign: bool = typer.Option(
        False,
        "--no-sign",
        help="Skip signing step.",
    ),
    no_align: bool = typer.Option(
        False,
        "--no-align",
        help="Skip zipalign step.",
    ),
    verify: bool = typer.Option(
        False,
        "--verify",
        help="Verify APK signature after signing.",
    ),
    install: bool = typer.Option(
        False,
        "--install",
        help="Install APK to connected device (replaces existing).",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID (for --install).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Build, align, and sign APK from apktool directory.

    Takes a modified apktool-decoded directory and produces a
    signed APK ready for installation.

    Workflow: apktool build -> zipalign -> apksigner

    Examples:

        # Basic usage with auto-generated debug keystore
        batuta apk patch ./com.example.app/

        # Custom output path
        batuta apk patch ./com.example.app/ -o ./patched.apk

        # Use custom keystore
        batuta apk patch ./com.example.app/ -k release.keystore --key-alias mykey

        # Build only (no signing)
        batuta apk patch ./com.example.app/ --no-sign --no-align

        # Patch, verify, and install
        batuta apk patch ./com.example.app/ --verify --install
    """
    from batuta.core.patcher import APKPatcher

    require("apktool")
    console.set_json_mode(json_output)

    try:
        patcher = APKPatcher(apktool_dir, output)

        if not json_output:
            console.print_info(f"Patching {apktool_dir.name}...")

        # Run patch workflow
        with console.status("Building APK...") if not json_output else nullcontext():
            result = patcher.patch(
                sign=not no_sign,
                align=not no_align,
                verify_signature=verify,
                keystore=keystore,
                key_alias=key_alias,
                keystore_pass=keystore_pass,
                key_pass=key_pass,
            )

        if not json_output:
            console.print_success(f"Patched APK: {result.output_path}")

            details = []
            if result.aligned:
                details.append("aligned")
            if result.signed:
                details.append("signed")
            if result.keystore_generated:
                details.append("debug keystore generated")
            if result.verified is not None:
                details.append(
                    "verified" if result.verified else "[red]verification failed[/red]"
                )

            if details:
                console.print_info(f"  Steps: {', '.join(details)}")

        # Install if requested
        if install:
            require("adb")

            if not json_output:
                console.print_info("Installing to device...")

            with console.status("Installing...") if not json_output else nullcontext():
                # Use -r to replace existing app
                from batuta.utils.process import run_tool

                cmd = ["adb"]
                if device:
                    cmd.extend(["-s", device])
                cmd.extend(["install", "-r", str(result.output_path)])
                run_tool(cmd, check=True)

            if not json_output:
                console.print_success("Installed successfully")

        if json_output:
            output_data = {
                "source_dir": str(result.source_dir),
                "output_path": str(result.output_path),
                "signed": result.signed,
                "aligned": result.aligned,
                "verified": result.verified,
                "keystore_generated": result.keystore_generated,
                "installed": install,
            }
            typer.echo(json.dumps(output_data, indent=2))

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("decompile")
def decompile_apk(
    apk_path: Path = typer.Argument(
        ...,
        help="Path to APK file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    output_dir: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: ./<apk_name>/).",
    ),
    java_only: bool = typer.Option(
        False,
        "--java-only",
        help="Only decompile to Java source (jadx).",
    ),
    smali_only: bool = typer.Option(
        False,
        "--smali-only",
        help="Only decompile to smali/resources (apktool).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Decompile APK to Java source and smali/resources.

    Uses jadx for Java source decompilation and apktool for
    smali disassembly and resource extraction.

    Output structure:

        <output_dir>/
        ├── java/    # Java source (jadx)
        └── smali/   # Smali + resources (apktool)

    Examples:

        # Full decompile (Java + smali)
        batuta apk decompile app.apk

        # Java source only
        batuta apk decompile app.apk --java-only

        # Smali/resources only
        batuta apk decompile app.apk --smali-only

        # Custom output directory
        batuta apk decompile app.apk -o ./analysis/
    """
    console.set_json_mode(json_output)

    # Validate mutually exclusive options
    if java_only and smali_only:
        console.print_error("Cannot use both --java-only and --smali-only")
        raise typer.Exit(1)

    # Determine what to decompile
    do_java = not smali_only
    do_smali = not java_only

    # Check required tools
    if do_java:
        require("jadx")
    if do_smali:
        require("apktool")

    try:
        decompiler = APKDecompiler(apk_path, output_dir)

        if not json_output:
            targets = []
            if do_java:
                targets.append("Java")
            if do_smali:
                targets.append("smali")
            console.print_info(f"Decompiling {apk_path.name} ({', '.join(targets)})...")

        with console.status("Decompiling...") if not json_output else nullcontext():
            result = decompiler.decompile(java=do_java, smali=do_smali)

        if json_output:
            output_data: dict[str, object] = {
                "apk_path": str(result.apk_path),
                "output_dir": str(result.output_dir),
                "java_success": result.java_success,
                "smali_success": result.smali_success,
            }
            if result.java_dir:
                output_data["java_dir"] = str(result.java_dir)
            if result.smali_dir:
                output_data["smali_dir"] = str(result.smali_dir)
            typer.echo(json.dumps(output_data, indent=2))
            return

        # Display results
        console.print_success(f"Decompiled to {result.output_dir}")

        if result.java_success and result.java_dir:
            console.print_info(f"  Java source: {result.java_dir}")
        elif do_java and not result.java_success:
            console.print_warning("  Java decompilation failed")

        if result.smali_success and result.smali_dir:
            console.print_info(f"  Smali/resources: {result.smali_dir}")
        elif do_smali and not result.smali_success:
            console.print_warning("  Smali decompilation failed")

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None
