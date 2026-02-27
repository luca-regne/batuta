"""CLI commands for Flutter app instrumentation."""

import json
from pathlib import Path

import typer

from batuta.core.adb import ADBWrapper
from batuta.core.merger import SplitAPKMerger
from batuta.core.reflutter import ReflutterPatcher
from batuta.exceptions import BatutaError
from batuta.utils.deps import require
from batuta.utils.output import console

app = typer.Typer(no_args_is_help=True)


@app.command("patch")
def patch_flutter_app(
    target: str = typer.Argument(
        ...,
        help="Package name or APK file path to patch.",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID (required if target is package name).",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for patched files (default: current directory).",
    ),
    skip_dump: bool = typer.Option(
        False,
        "--skip-dump",
        help="Skip Dart code dump step (only patch and install).",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help="Wait for user to manually start app (vs auto-start).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip Flutter framework validation.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Patch Flutter APK with reflutter and install on device.

    This command instruments a Flutter app for Dart code dumping:
    1. Pull APK from device (if package name provided) or use local APK
    2. Validate it's a Flutter app (unless --force)
    3. Patch with reflutter for code dumping
    4. Sign patched APK with debug keystore
    5. Uninstall original app
    6. Install patched APK
    7. Auto-start app (or wait for manual start with --wait)
    8. Dump Dart code (unless --skip-dump)

    Examples:
        # Patch installed app by package name
        batuta flutter patch com.example.app

        # Patch local APK file
        batuta flutter patch app.apk

        # Skip dump, only patch and install
        batuta flutter patch com.example.app --skip-dump

        # Wait for manual app start instead of auto-launch
        batuta flutter patch com.example.app --wait
    """
    console.set_json_mode(json_output)

    try:
        # Determine if target is package name or APK file
        target_path = Path(target)
        if target_path.exists() and target_path.is_file():
            # Local APK file
            apk_path = target_path
            console.print_info(f"Using local APK: {apk_path}")
        else:
            # Treat as package name - pull from device
            require("adb")
            console.print_info(f"Pulling APK for package: {target}")

            if not device:
                # Try to use default device
                adb = ADBWrapper()
                devices = adb.list_devices()
                if len(devices.available) == 0:
                    console.print_error("No devices connected")
                    raise typer.Exit(1)
                if len(devices.available) > 1:
                    console.print_error(
                        "Multiple devices connected. Use --device to specify target."
                    )
                    raise typer.Exit(1)
            else:
                adb = ADBWrapper(device_id=device)

            # Get package info (to validate package exists)
            adb.get_package_info(target)

            # Pull APK(s)
            with console.status("Pulling APK from device..."):
                pulled = adb.pull_apk(target, output_dir=output or Path.cwd())

            # If split, merge automatically
            if pulled.is_split and pulled.split_paths:
                console.print_info("Split APK detected, merging...")
                split_dir = pulled.split_paths[0].parent
                merger = SplitAPKMerger(split_dir)
                with console.status("Merging split APKs..."):
                    merged_path = merger.merge()
                apk_path = merged_path
                console.print_success(f"Merged APK: {merged_path}")
            else:
                apk_path = pulled.local_path

        # Set output directory
        output_dir = output.resolve() if output else Path.cwd()

        # Patch and install
        patcher = ReflutterPatcher(apk_path)

        with console.status("Patching APK with reflutter..."):
            result = patcher.patch_and_install(
                device_id=device,
                skip_dump=skip_dump,
                wait_for_user=wait,
                force=force,
                output_dir=output_dir,
            )

        # Output results
        if json_output:
            output_data = {
                "package_name": result.package_name,
                "original_apk": str(result.original_apk),
                "signed_apk": str(result.signed_apk),
                "installed": result.installed,
            }
            if result.dump_result:
                output_data["dump"] = {
                    "success": result.dump_result.success,
                    "dump_path": str(result.dump_result.dump_path),
                    "formatted_path": (
                        str(result.dump_result.formatted_path)
                        if result.dump_result.formatted_path
                        else None
                    ),
                }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            console.print_success(
                f"Flutter app patched and installed: {result.package_name}"
            )
            console.print(f"\n  Signed APK: {result.signed_apk}")
            if result.dump_result and result.dump_result.success:
                console.print(f"  Dart dump:  {result.dump_result.dump_path}")
                if result.dump_result.formatted_path:
                    console.print(f"  JSON dump:  {result.dump_result.formatted_path}")
            console.print()

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("dump")
def dump_dart_code(
    package: str = typer.Argument(
        ...,
        help="Package name of instrumented Flutter app.",
    ),
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: ./<package>_dump.dart).",
    ),
    no_format: bool = typer.Option(
        False,
        "--no-format",
        help="Don't format output as JSON.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """Dump Dart code from instrumented Flutter app.

    This command extracts Dart code from a Flutter app that has been
    patched with reflutter. The app must be running on a rooted device.

    The dump is saved to a .dart file and optionally formatted as JSON.

    Examples:
        # Dump Dart code
        batuta flutter dump com.example.app

        # Specify output location
        batuta flutter dump com.example.app --output dump.dart

        # Skip JSON formatting
        batuta flutter dump com.example.app --no-format
    """
    console.set_json_mode(json_output)

    try:
        require("adb")

        with console.status("Dumping Dart code..."):
            result = ReflutterPatcher.dump_dart_code(
                package_name=package,
                output_path=output,
                format_json=not no_format,
                device_id=device,
            )

        if json_output:
            output_data = {
                "package_name": result.package_name,
                "success": result.success,
                "dump_path": str(result.dump_path),
                "formatted_path": (
                    str(result.formatted_path) if result.formatted_path else None
                ),
            }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            console.print_success(f"Dart code dumped: {result.dump_path}")
            if result.formatted_path:
                console.print_info(f"JSON formatted: {result.formatted_path}")

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None
