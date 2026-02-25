"""CLI commands for APK management."""

import json
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.table import Table

from batuta.core.adb import ADBWrapper
from batuta.exceptions import BatutaError, MultiplePackagesFoundError
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
    table.add_column("App Name")
    table.add_column("Version")

    for i, pkg in enumerate(packages, 1):
        table.add_row(
            str(i),
            pkg.package_name,
            pkg.app_name or "-",
            pkg.version_name or "-",
        )

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
    filter_query: str = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter packages by name.",
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
            packages = adb.search_packages(filter_query, include_system=system)
        else:
            # Get basic package list
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

        if filter_query:
            # Show more details when filtering
            table.add_column("App Name")
            table.add_column("Version")
            table.add_column("Split")

            for pkg in packages:
                table.add_row(
                    pkg.package_name,
                    pkg.app_name or "-",
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
        help="Package name, app name, or filter.",
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

        try:
            pkg = adb.find_package(query, include_system=system)
        except MultiplePackagesFoundError:
            if select and not json_output:
                matches = adb.search_packages(query, include_system=system)
                pkg = _select_package(matches, query)
            else:
                raise

        if json_output:
            typer.echo(json.dumps(pkg.model_dump(exclude_none=True), indent=2))
            return

        console.print(f"\n[bold cyan]{pkg.package_name}[/bold cyan]\n")

        if pkg.app_name:
            console.print(f"  App Name:    {pkg.app_name}")
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
        help="Package name, app name, or filter to pull.",
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
    - App name (Example App)
    - Filter pattern (google, facebook)

    For split APKs, all parts are pulled into a directory.
    """
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)

        # Find the package
        try:
            pkg = adb.find_package(query, include_system=system)
        except MultiplePackagesFoundError:
            if select and not json_output:
                matches = adb.search_packages(query, include_system=system)
                pkg = _select_package(matches, query)
            else:
                raise

        if not json_output:
            console.print_info(f"Pulling {pkg.package_name}...")
            if pkg.is_split:
                console.print_info(f"  Split APK with {len(pkg.all_apk_paths)} parts")

        # Pull the APK
        with console.status("Pulling APK...") if not json_output else nullcontext():
            result = adb.pull_apk(pkg.package_name, output_dir=output_dir)

        if json_output:
            output_data = {
                "package_name": result.package_name,
                "local_path": str(result.local_path),
                "is_split": result.is_split,
            }
            if result.split_paths:
                output_data["split_paths"] = [str(p) for p in result.split_paths]
            typer.echo(json.dumps(output_data, indent=2))
            return

        console.print_success(f"Pulled to {result.local_path}")

        if result.is_split and result.split_paths:
            console.print_info(f"  {len(result.split_paths)} APK files:")
            for p in result.split_paths:
                console.print(f"    - {p.name}")

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("search")
def search_packages(
    query: str = typer.Argument(
        ...,
        help="Search query (package name, app name, or filter).",
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
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Search for packages by name or app label."""
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper(device_id=device)
        packages = adb.search_packages(query, include_system=system)

        if json_output:
            output = [pkg.model_dump(exclude_none=True) for pkg in packages]
            typer.echo(json.dumps(output, indent=2))
            return

        if not packages:
            console.print_warning(f"No packages found matching '{query}'")
            raise typer.Exit(1) from None

        table = Table(title=f"Packages matching '{query}' ({len(packages)})")
        table.add_column("Package Name", style="cyan")
        table.add_column("App Name")
        table.add_column("Version")
        table.add_column("Split")

        for pkg in packages:
            table.add_row(
                pkg.package_name,
                pkg.app_name or "-",
                pkg.version_name or "-",
                "Yes" if pkg.is_split else "No",
            )

        console.print(table)

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None
