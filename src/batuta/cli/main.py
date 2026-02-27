"""Root CLI application for batuta."""

import typer

from batuta import __version__
from batuta.cli import analyze, apk, device

app = typer.Typer(
    name="batuta",
    help="Orchestrate Android reverse engineering tools into a unified pipeline.",
    no_args_is_help=True,
)

# Register subcommands
app.add_typer(analyze.app, name="analyze", help="Static APK analysis utilities")
app.add_typer(device.app, name="device", help="Manage connected Android devices")
app.add_typer(apk.app, name="apk", help="Pull and manage APK files")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"batuta {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """batuta - Android security analysis pipeline."""
    pass


if __name__ == "__main__":
    app()
