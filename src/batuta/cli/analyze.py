"""CLI commands for APK analysis."""

import json
from pathlib import Path
from collections.abc import Callable, Sequence

import typer
from rich.table import Table

from batuta.core.analyzer import FrameworkDetector
from batuta.core.manifest import ManifestParser, get_sdk_label
from batuta.exceptions import BatutaError
from batuta.models.manifest import ActivityInfo, ComponentInfo, ProviderInfo
from batuta.utils.output import console

app = typer.Typer(no_args_is_help=True)


@app.command("framework")
def detect_framework(
    apk_path: Path = typer.Argument(
        ...,
        help="Path to the APK file to analyze.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    no_native_libs: bool = typer.Option(
        False,
        "--no-native-libs",
        help="Do not include native library listing in output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Detect cross-platform frameworks used in an APK.

    Analyzes the APK structure to identify frameworks like Flutter,
    React Native, Xamarin, Cordova, and Unity based on file signatures.
    """
    console.set_json_mode(json_output)

    try:
        detector = FrameworkDetector(apk_path)
        result = detector.detect(include_native_libs=not no_native_libs)

        if json_output:
            # Serialize Path to string for JSON output
            output = result.model_dump(mode="json")
            typer.echo(json.dumps(output, indent=2))
            return

        # Table/rich output
        if result.detected_frameworks:
            console.print("\n[bold]Frameworks Detected:[/bold]")
            for fw in result.detected_frameworks:
                console.print(f"  [cyan]{fw.name}[/cyan]")
                for matched in fw.matched_files:
                    console.print(f"    - {matched}")
        else:
            console.print_warning("No frameworks detected.")

        if result.native_libraries:
            lib_count = len(result.native_libraries)
            console.print(f"\n[bold]Native Libraries ({lib_count} files):[/bold]")
            for lib in result.native_libraries:
                console.print(f"  {lib}")

        console.print()

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("manifest")
def analyze_manifest(
    apk_path: Path = typer.Argument(
        ...,
        help="Path to the APK file to analyze.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    activities: bool = typer.Option(
        False,
        "--activities",
        "-a",
        help="Show detailed activities analysis.",
    ),
    services: bool = typer.Option(
        False,
        "--services",
        "-s",
        help="Show detailed services analysis.",
    ),
    receivers: bool = typer.Option(
        False,
        "--receivers",
        "-r",
        help="Show detailed broadcast receivers analysis.",
    ),
    providers: bool = typer.Option(
        False,
        "--providers",
        "-p",
        help="Show detailed content providers analysis.",
    ),
    all_components: bool = typer.Option(
        False,
        "--all-components",
        "-A",
        help="Show all component details (equivalent to -a -s -r -p).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Analyze AndroidManifest.xml for security assessment.

    Extracts package information, permissions, component details, and
    calculates the application's attack surface. By default, shows only
    general info and attack surface summary. Use component flags to see
    detailed analysis of activities, services, receivers, and providers.
    """
    console.set_json_mode(json_output)

    try:
        parser = ManifestParser(apk_path)
        result = parser.parse()

        if json_output:
            output = result.model_dump(mode="json")
            typer.echo(json.dumps(output, indent=2))
            return

        if all_components:
            activities = services = receivers = providers = True

        info = result.info
        console.print("\n[bold]Package Information[/bold]")
        console.print(f"  Package:       {info.package_name}")
        if info.version_name or info.version_code:
            version_str = info.version_name or "N/A"
            if info.version_code:
                version_str += f"  (build {info.version_code})"
            console.print(f"  Version:       {version_str}")

        if info.min_sdk:
            console.print(
                f"  Min SDK:       {info.min_sdk}  — {get_sdk_label(info.min_sdk)}"
            )
        if info.target_sdk:
            console.print(
                f"  Target SDK:    {info.target_sdk}  — {get_sdk_label(info.target_sdk)}"
            )

        console.print("\n[bold]Security Flags[/bold]")
        debuggable_color = "red" if info.debuggable else "green"
        console.print(
            f"  Debuggable:    [{debuggable_color}]{info.debuggable}[/{debuggable_color}]"
        )

        backup_color = "yellow" if info.allow_backup else "green"
        console.print(
            f"  Allow Backup:  [{backup_color}]{info.allow_backup}[/{backup_color}]"
        )

        cleartext_color = "yellow" if info.uses_cleartext_traffic else "green"
        console.print(
            f"  Cleartext:     [{cleartext_color}]{info.uses_cleartext_traffic}[/{cleartext_color}]"
        )

        nsc_color = "green" if info.network_security_config else "yellow"
        nsc_text = "present" if info.network_security_config else "absent"
        console.print(f"  Net Sec Config:[{nsc_color}]{nsc_text}[/{nsc_color}]")

        if info.permissions:
            console.print(
                f"\n[bold]Declared Permissions[/bold]  ({len(info.permissions)})"
            )
            for perm in info.permissions:
                console.print(f"  {perm}")

        if info.uses_permissions:
            console.print(
                f"\n[bold]Requested Permissions[/bold]  ({len(info.uses_permissions)})"
            )
            for perm in info.uses_permissions:
                console.print(f"  {perm}")

        # Attack Surface Summary
        surface = result.attack_surface
        console.print("\n[bold]Attack Surface Summary[/bold]")

        table = Table()
        table.add_column("Component", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Exported", justify="right")
        table.add_column("Unprotected", justify="right")

        def get_unprotected_count(components: Sequence[ComponentInfo]) -> int:
            return sum(
                1 for c in components if c.effectively_exported and c.permission is None
            )

        act_unprot = get_unprotected_count(result.activities)
        svc_unprot = get_unprotected_count(result.services)
        rcv_unprot = get_unprotected_count(result.receivers)
        prv_unprot = get_unprotected_count(result.providers)

        table.add_row(
            "Activities",
            str(surface.total_activities),
            str(surface.exported_activities),
            f"[red]{act_unprot}[/red]" if act_unprot else "0",
        )
        table.add_row(
            "Services",
            str(surface.total_services),
            str(surface.exported_services),
            f"[red]{svc_unprot}[/red]" if svc_unprot else "0",
        )
        table.add_row(
            "Broadcast Receivers",
            str(surface.total_receivers),
            str(surface.exported_receivers),
            f"[red]{rcv_unprot}[/red]" if rcv_unprot else "0",
        )
        table.add_row(
            "Content Providers",
            str(surface.total_providers),
            str(surface.exported_providers),
            f"[red]{prv_unprot}[/red]" if prv_unprot else "0",
        )

        console.print(table)

        console.print()
        if surface.unprotected_exported > 0:
            console.print(
                f"  [bold red]Unprotected exported components: {surface.unprotected_exported}[/bold red]"
            )
        if surface.grant_uri_providers > 0:
            console.print(
                f"  [yellow]Grant URI providers: {surface.grant_uri_providers}[/yellow]"
            )
        if surface.debuggable:
            console.print("  [bold red]App is debuggable[/bold red]")
        if surface.backup_enabled:
            console.print("  [yellow]Backup is enabled[/yellow]")
        if surface.cleartext_traffic:
            console.print("  [yellow]Cleartext traffic allowed[/yellow]")

        if activities:
            _print_component_table(
                "Activities",
                result.activities,
                extra_columns=[
                    ("Launch Mode", lambda a: getattr(a, "launch_mode", None) or "—")
                ],
            )

        if services:
            _print_component_table("Services", result.services)

        if receivers:
            _print_component_table("Broadcast Receivers", result.receivers)

        if providers:
            _print_provider_table(result.providers)

        console.print()

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


def _print_component_table(
    title: str,
    components: Sequence[ComponentInfo],
    extra_columns: list[tuple[str, Callable[[ComponentInfo], str]]] | None = None,
) -> None:
    """Print a table for a component type."""
    if not components:
        console.print(f"\n[bold]{title}[/bold]")
        console.print("  None declared")
        return

    console.print(f"\n[bold]{title}[/bold]  ({len(components)})")

    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Exported")
    table.add_column("Permission")
    table.add_column("Intent Filters")

    if extra_columns:
        for col_name, _ in extra_columns:
            table.add_column(col_name)

    for comp in components:
        if comp.effectively_exported and comp.permission is None:
            style = "red"
        elif comp.effectively_exported:
            style = "yellow"
        else:
            style = "dim"

        exported_str = "YES" if comp.effectively_exported else "no"
        permission_str = comp.permission or "—"

        if comp.intent_filters:
            filters_str = ", ".join(
                "/".join(f.actions[:2]) if f.actions else "/".join(f.categories[:2])
                for f in comp.intent_filters[:2]
            )
            if len(comp.intent_filters) > 2:
                filters_str += "..."
        else:
            filters_str = ""

        row = [comp.name, exported_str, permission_str, filters_str]

        if extra_columns:
            for _, getter in extra_columns:
                row.append(getter(comp))

        table.add_row(*row, style=style)

    console.print(table)


def _print_provider_table(providers: list) -> None:
    """Print content providers with additional details."""
    if not providers:
        console.print("\n[bold]Content Providers[/bold]")
        console.print("  None declared")
        return

    console.print(f"\n[bold]Content Providers[/bold]  ({len(providers)})")

    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Exported")
    table.add_column("Authorities")
    table.add_column("Permissions")
    table.add_column("Grant URI")

    for provider in providers:
        if provider.effectively_exported and provider.permission is None:
            style = "red"
        elif provider.effectively_exported:
            style = "yellow"
        else:
            style = "dim"

        exported_str = "YES" if provider.effectively_exported else "no"
        authorities_str = provider.authorities or "—"

        perms = []
        if provider.permission:
            perms.append(provider.permission)
        elif provider.read_permission or provider.write_permission:
            if provider.read_permission:
                perms.append(f"R:{provider.read_permission}")
            if provider.write_permission:
                perms.append(f"W:{provider.write_permission}")
        perm_str = ", ".join(perms) if perms else "—"

        grant_str = (
            "YES"
            if provider.grant_uri_permissions or provider.grant_uri_permission_paths
            else "no"
        )

        table.add_row(
            provider.name,
            exported_str,
            authorities_str,
            perm_str,
            grant_str,
            style=style,
        )

    console.print(table)

    for provider in providers:
        if provider.grant_uri_permission_paths:
            console.print(f"\n  [yellow]Grant URI paths for {provider.name}:[/yellow]")
            for path in provider.grant_uri_permission_paths:
                console.print(f"    {path}")
