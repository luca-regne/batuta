"""Subprocess wrapper for all external tool invocations."""

import subprocess
from dataclasses import dataclass

from batuta.exceptions import ProcessError


@dataclass
class ProcessResult:
    """Result of a subprocess execution."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Check if the command succeeded."""
        return self.returncode == 0

    @property
    def output(self) -> str:
        """Get stdout, stripping trailing whitespace."""
        return self.stdout.strip()

    @property
    def lines(self) -> list[str]:
        """Get stdout as a list of non-empty lines."""
        return [line for line in self.stdout.strip().split("\n") if line]


def run_tool(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    timeout: float | None = None,
    cwd: str | None = None,
) -> ProcessResult:
    """Run an external tool command.

    Args:
        command: Command and arguments to run.
        check: If True, raise ProcessError on non-zero exit.
        capture_output: If True, capture stdout and stderr.
        timeout: Optional timeout in seconds.
        cwd: Working directory for the command.

    Returns:
        ProcessResult with command output.

    Raises:
        ProcessError: If check=True and command returns non-zero.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as e:
        raise ProcessError(command, -1, f"Command timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise ProcessError(command, -1, f"Command not found: {command[0]}") from e

    proc_result = ProcessResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout if capture_output else "",
        stderr=result.stderr if capture_output else "",
    )

    if check and not proc_result.success:
        raise ProcessError(command, result.returncode, result.stderr)

    return proc_result
