"""CLI commands for APK analysis."""

import json
from pathlib import Path

import typer

from batuta.core.analyzer import FrameworkDetector
from batuta.exceptions import BatutaError
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
