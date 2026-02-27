"""APK file validation and parsing utilities."""

import re
from pathlib import Path

from batuta.exceptions import BatutaError

# ZIP file magic header (APKs are ZIP files)
ZIP_FILE_HEADER = b"PK\x03\x04"


def validate_apk_path(
    apk_path: Path,
    *,
    require_zip_header: bool = False,
    error_cls: type[BatutaError] = BatutaError,
) -> None:
    """Validate that an APK file path is valid.

    Performs the following checks:
    - File exists
    - Path is a file (not a directory)
    - File has .apk extension
    - Optionally: file starts with ZIP magic header

    Args:
        apk_path: Path to the APK file to validate.
        require_zip_header: If True, also verify the file starts with ZIP header.
        error_cls: Exception class to raise on validation failure.

    Raises:
        BatutaError (or subclass): If validation fails.
    """
    if not apk_path.exists():
        raise error_cls(f"APK not found: {apk_path}")

    if not apk_path.is_file():
        raise error_cls(f"Not a file: {apk_path}")

    if apk_path.suffix.lower() != ".apk":
        raise error_cls(f"Not an APK file (expected .apk extension): {apk_path}")

    if require_zip_header:
        try:
            with apk_path.open("rb") as f:
                header = f.read(4)
        except OSError as e:
            raise error_cls(f"Failed to read APK header: {e}") from e

        if len(header) < len(ZIP_FILE_HEADER):
            raise error_cls("File is too small to be a valid APK")

        if header != ZIP_FILE_HEADER:
            raise error_cls(
                f"Header mismatch. Expected: {ZIP_FILE_HEADER!r}, got: {header!r}"
            )


def get_package_name(
    apk_path: Path,
    *,
    error_cls: type[BatutaError] = BatutaError,
) -> str:
    """Extract package name from APK file.

    Tries multiple methods in order:
    1. aapt from Android SDK (most reliable)
    2. pyaxmlparser library
    3. Filename heuristic (fallback)

    Args:
        apk_path: Path to the APK file.
        error_cls: Exception class to raise on failure.

    Returns:
        Package name (e.g., 'com.example.app').

    Raises:
        BatutaError (or subclass): If package name cannot be extracted.
    """
    # Method 1: Try aapt from Android SDK
    try:
        from batuta.utils.android_sdk import get_build_tools_path
        from batuta.utils.process import run_tool

        build_tools = get_build_tools_path()
        aapt = build_tools / "aapt"
        if aapt.exists():
            result = run_tool(
                [str(aapt), "dump", "badging", str(apk_path)],
                check=False,
                capture_output=True,
            )

            if result.success:
                # Parse: package: name='com.example.app' versionCode='1' ...
                match = re.search(r"package: name='([^']+)'", result.stdout)
                if match:
                    return match.group(1)
    except Exception:
        pass

    # Method 2: Try pyaxmlparser (installed with batuta)
    try:
        from pyaxmlparser import APK  # type: ignore[import-untyped]

        apk = APK(str(apk_path))
        if apk.package:
            return str(apk.package)
    except Exception:
        pass

    # Method 3: Extract from filename (fallback heuristic)
    stem = apk_path.stem
    # Remove version numbers and common suffixes
    stem = re.sub(r"-\d+\.\d+.*$", "", stem)  # Remove version like -4.7.1
    for suffix in ["_merged", "-merged", "-signed", "-aligned", "-debugSigned"]:
        stem = stem.replace(suffix, "")
    # Convert underscores back to dots if it looks like a package
    if "_" in stem and "." not in stem:
        stem = stem.replace("_", ".")

    # Validate result
    if "." not in stem:
        raise error_cls(
            f"Could not extract package name from APK. "
            f"Filename heuristic gave: '{stem}' which doesn't look like a "
            f"package name. Please ensure aapt or pyaxmlparser is available."
        )

    return stem
