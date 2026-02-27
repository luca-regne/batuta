"""Utilities for merging split APK directories into a single APK."""

from pathlib import Path

from batuta.exceptions import APKMergeError
from batuta.utils.deps import get_apkeditor_command, require
from batuta.utils.process import run_tool


class SplitAPKMerger:
    """Merge split APK folders using APKEditor."""

    def __init__(self, split_dir: Path, output_path: Path | None = None):
        self.split_dir = split_dir.resolve()
        self.output_path = (
            output_path.resolve() if output_path else self._default_output_path()
        )

    def _default_output_path(self) -> Path:
        return self.split_dir.parent / f"{self.split_dir.name}.merged.apk"

    def _validate(self) -> list[Path]:
        if not self.split_dir.exists():
            raise APKMergeError(f"Split APK directory not found: {self.split_dir}")
        if not self.split_dir.is_dir():
            raise APKMergeError(f"Split APK path is not a directory: {self.split_dir}")

        apk_files = sorted(self.split_dir.glob("*.apk"))
        if not apk_files:
            raise APKMergeError(
                f"No APK files found in {self.split_dir}. Did you pull split APKs?"
            )

        return apk_files

    def merge(self) -> Path:
        """Run APKEditor merge workflow and return merged APK path."""

        self._validate()
        require("APKEditor")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()

        base_cmd = get_apkeditor_command()
        if base_cmd is None:
            raise APKMergeError(
                "APKEditor command could not be resolved. Set APKEDITOR_JAR, "
                "configure ~/.batuta/config.json (apkeditor_path), "
                "or add an APKEditor wrapper to PATH."
            )

        cmd = base_cmd + [
            "merge",
            "-i",
            str(self.split_dir),
            "-o",
            str(self.output_path),
        ]

        try:
            run_tool(cmd, check=True)
        except Exception as exc:
            raise APKMergeError(f"APKEditor merge failed: {exc}") from exc

        if not self.output_path.exists():
            raise APKMergeError(
                "APKEditor reported success but merged APK was not created: "
                f"{self.output_path}"
            )

        return self.output_path
