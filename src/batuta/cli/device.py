"""CLI commands for device management."""

import json
import subprocess

import typer
from rich.table import Table

from batuta.core.adb import ADBWrapper
from batuta.exceptions import BatutaError
from batuta.utils.deps import require
from batuta.utils.output import console

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_devices(
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
) -> None:
    """List connected Android devices."""
    require("adb")
    console.set_json_mode(json_output)

    try:
        adb = ADBWrapper()
        devices = adb.list_devices()

        if json_output:
            output = [
                {
                    "id": d.id,
                    "state": d.state.value,
                    "model": d.model,
                    "product": d.product,
                    "available": d.is_available,
                }
                for d in devices
            ]
            typer.echo(json.dumps(output, indent=2))
            return

        if not devices.devices:
            console.print_warning("No devices connected")
            raise typer.Exit(1) from None

        table = Table(title="Connected Devices")
        table.add_column("ID", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Model")
        table.add_column("Product")

        for device in devices:
            state_style = "green" if device.is_available else "red"
            table.add_row(
                device.id,
                f"[{state_style}]{device.state.value}[/{state_style}]",
                device.model or "-",
                device.product or "-",
            )

        console.print(table)
        console.print_info(f"{len(devices.available)} device(s) available")

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None


@app.command("shell")
def shell(
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Target device ID.",
    ),
    command: list[str] | None = typer.Argument(
        None,
        help="Command to run (omit for interactive shell).",
    ),
) -> None:
    """Open ADB shell on a device or run a shell command."""
    require("adb")

    try:
        adb = ADBWrapper(device_id=device)
        target = adb.ensure_device()

        cmd = ["adb", "-s", target.id, "shell"]
        if command:
            cmd.extend(command)

        # Run interactively
        subprocess.run(cmd, check=False)

    except BatutaError as e:
        console.print_error(str(e))
        raise typer.Exit(1) from None
