"""APK file validation utilities."""

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
