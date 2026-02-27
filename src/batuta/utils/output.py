"""Rich console helpers for terminal output."""

from typing import Any

from rich.console import Console as RichConsole
from rich.status import Status


class Console:
    """Wrapper around rich.Console with convenience methods."""

    def __init__(self) -> None:
        self._console = RichConsole()
        self._json_mode = False

    def set_json_mode(self, enabled: bool) -> None:
        """Enable or disable JSON mode (suppresses rich output)."""
        self._json_mode = enabled

    @property
    def json_mode(self) -> bool:
        """Check if JSON mode is enabled."""
        return self._json_mode

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to console (suppressed in JSON mode)."""
        if not self._json_mode:
            self._console.print(*args, **kwargs)

    def print_success(self, message: str) -> None:
        """Print a success message in green."""
        if not self._json_mode:
            self._console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message in red."""
        if not self._json_mode:
            self._console.print(f"[red]✗[/red] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message in blue."""
        if not self._json_mode:
            self._console.print(f"[blue]ℹ[/blue] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message in yellow."""
        if not self._json_mode:
            self._console.print(f"[yellow]⚠[/yellow] {message}")

    def status(self, message: str) -> Status:
        """Create a status spinner context manager."""
        return self._console.status(message)


# Global console instance
console = Console()
