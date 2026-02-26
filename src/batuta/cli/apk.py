"""CLI commands for APK management."""

import json
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.table import Table

from batuta.core.adb import ADBWrapper
from batuta.exceptions import (
    BatutaError,
    MultiplePackagesFoundError,
    PackageNotFoundError,
)
from batuta.models.apk import PackageInfo
from batuta.utils.deps import require
from batuta.utils.output import console

app = typer.Typer(no_args_is_help=True)


def _select_package(packages: list[PackageInfo], query: str) -> PackageInfo:
    """Interactive package selection."""
    console.print(f"\n[yellow]Multiple packages match '{query}':[/yellow]\n")

    table = Table()
    table.add_column("#", style="cyan", width=4)
    table.add_column("Package Name", style="green")

    for i, pkg in enumerate(packages, 1):
        table.add_row(str(i), pkg.package_name)

    console.print(table)
    console.print()

    while True:
        try:
            choice = typer.prompt("Select package number (or 'q' to quit)")
            if choice.lower() == "q":
                raise typer.Abort()

            idx = int(choice) - 1
            if 0 <= idx < len(packages):
                return packages[idx]

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
    select: bool = typer.Option(
        False,
        "--select",
        help="Interactive selection if multiple matches.",
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

        # Fast search first, then get full details for selected package
        try:
            match = adb.find_package(query, include_system=system)
        except MultiplePackagesFoundError:
            if select and not json_output:
                matches = adb.search_packages(query, include_system=system)
                match = _select_package(matches, query)
            else:
                raise

        # Fetch full package details
        pkg = adb.get_package_info(match.package_name)

        if json_output:
            typer.echo(json.dumps(pkg.model_dump(exclude_none=True), indent=2))
            return

        console.print(f"\n[bold cyan]{pkg.package_name}[/bold cyan]\n")
        if pkg.version_name:
            console.print(f"  Version:     {pkg.version_name}")
        if pkg.version_code:
            console.print(f"  Version Code: {pkg.version_code}")
        if pkg.apk_path:
            console.print(f"  APK Path:    {pkg.apk_path}")
        if pkg.is_split:
            console.print(f"  Split APKs:  {len(pkg.split_apks or [])} files")
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
    select: bool = typer.Option(
        False,
        "--select",
        help="Interactive selection if multiple matches.",
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
    """
    require("adb")
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
            except MultiplePackagesFoundError:
                if select and not json_output:
                    matches = adb.search_packages(query, include_system=system)
                    match = _select_package(matches, query)
                else:
                    raise
            package_names = [match.package_name]

        results = []

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

        if json_output:
            output_items = []
            for result in results:
                item = {
                    "package_name": result.package_name,
                    "local_path": str(result.local_path),
                    "is_split": result.is_split,
                }
                if result.split_paths:
                    item["split_paths"] = [str(p) for p in result.split_paths]
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
