"""APK decompilation: extract Java source and smali/resources from APKs."""

from pathlib import Path

from batuta.exceptions import DecompileError
from batuta.models.apk import DecompileResult
from batuta.utils.apk import validate_apk_path
from batuta.utils.deps import require
from batuta.utils.process import run_tool


class APKDecompiler:
    """Handles APK decompilation using jadx and apktool."""

    def __init__(
        self,
        apk_path: Path,
        output_dir: Path | None = None,
    ):
        """Initialize APK decompiler.

        Args:
            apk_path: Path to the APK file.
            output_dir: Root output directory. Defaults to ./<apk_stem>/.
        """
        self.apk_path = apk_path.resolve()
        self.output_dir = (
            output_dir.resolve() if output_dir else Path.cwd() / self.apk_path.stem
        )

    def validate(self) -> None:
        """Validate that APK exists and is a valid file.

        Raises:
            DecompileError: If APK is invalid.
        """
        validate_apk_path(
            self.apk_path, require_zip_header=True, error_cls=DecompileError
        )

    def decompile_java(self, output: Path) -> Path:
        """Decompile APK to Java source using jadx.

        Args:
            output: Output directory for Java sources.

        Returns:
            Path to output directory.

        Raises:
            DecompileError: If decompilation fails.
        """
        require("jadx")

        # jadx -d <output> <apk>
        # No -r (include resources) or -e (gradle export) by default
        cmd = ["jadx", "-d", str(output), str(self.apk_path)]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise DecompileError(f"jadx decompilation failed: {e}") from e

        if not output.is_dir():
            raise DecompileError(
                f"jadx completed but output directory not found: {output}"
            )

        return output

    def decompile_smali(self, output: Path) -> Path:
        """Decompile APK to smali and resources using apktool.

        Args:
            output: Output directory for smali/resources.

        Returns:
            Path to output directory.

        Raises:
            DecompileError: If decompilation fails.
        """
        require("apktool")

        # apktool d -o <output> <apk> -f
        # -f: force overwrite existing directory
        cmd = ["apktool", "d", "-o", str(output), str(self.apk_path), "-f"]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise DecompileError(f"apktool decompilation failed: {e}") from e

        if not output.is_dir():
            raise DecompileError(
                f"apktool completed but output directory not found: {output}"
            )

        return output

    def decompile(
        self,
        java: bool = True,
        smali: bool = True,
    ) -> DecompileResult:
        """Execute decompilation workflow.

        Args:
            java: Whether to decompile to Java source (jadx).
            smali: Whether to decompile to smali/resources (apktool).

        Returns:
            DecompileResult with paths and success status.

        Raises:
            DecompileError: If validation fails or both tools fail.
        """
        self.validate()

        if not java and not smali:
            raise DecompileError("At least one of java or smali must be True")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        java_dir: Path | None = None
        smali_dir: Path | None = None
        java_success = False
        smali_success = False

        # Decompile Java source
        if java:
            java_dir = self.output_dir / "java"
            try:
                self.decompile_java(java_dir)
                java_success = True
            except DecompileError:
                # Continue to try smali even if java fails
                if not smali:
                    raise

        # Decompile smali/resources
        if smali:
            smali_dir = self.output_dir / "smali"
            try:
                self.decompile_smali(smali_dir)
                smali_success = True
            except DecompileError:
                # If both failed, raise
                if java and not java_success:
                    raise DecompileError(
                        "Both jadx and apktool decompilation failed"
                    ) from None
                if not java:
                    raise

        return DecompileResult(
            apk_path=self.apk_path,
            output_dir=self.output_dir,
            java_dir=java_dir if java_success else None,
            smali_dir=smali_dir if smali_success else None,
            java_success=java_success,
            smali_success=smali_success,
        )
