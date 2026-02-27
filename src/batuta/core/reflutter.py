"""Flutter APK instrumentation with reflutter."""

import json
import tempfile
import time
from pathlib import Path

from batuta.core.analyzer import FrameworkDetector
from batuta.core.patcher import APKPatcher
from batuta.exceptions import (
    DartDumpError,
    FlutterError,
    ReflutterError,
)
from batuta.models.flutter import DumpResult, FlutterPatchResult
from batuta.utils.apk import get_package_name, validate_apk_path
from batuta.utils.deps import require
from batuta.utils.process import run_tool


class ReflutterPatcher:
    """Handles Flutter APK patching and instrumentation with reflutter."""

    def __init__(self, apk_path: Path):
        """Initialize reflutter patcher.

        Args:
            apk_path: Path to the Flutter APK to patch.
        """
        self.apk_path = apk_path.resolve()
        self.package_name = get_package_name(self.apk_path, error_cls=FlutterError)

    def validate_flutter(self) -> None:
        """Verify that the APK is a Flutter application.

        Raises:
            FlutterError: If APK is not a Flutter app.
        """
        validate_apk_path(self.apk_path, error_cls=FlutterError)
        detector = FrameworkDetector(self.apk_path)
        result = detector.detect(include_native_libs=False)

        is_flutter = any(fw.name == "Flutter" for fw in result.detected_frameworks)

        if not is_flutter:
            detected_names = [fw.name for fw in result.detected_frameworks]
            raise FlutterError(
                f"APK is not a Flutter application. "
                f"Detected frameworks: {detected_names or 'None'}"
            )

    def patch(self, output_dir: Path | None = None) -> Path:
        """Patch APK with reflutter.

        Args:
            output_dir: Directory to run reflutter in. Uses temp dir if None.

        Returns:
            Path to reflutter-patched APK (release.RE.apk).

        Raises:
            ReflutterError: If patching fails.
        """
        require("reflutter")

        work_dir = output_dir or Path(tempfile.mkdtemp(prefix="batuta-reflutter-"))

        try:
            # reflutter <apk>
            cmd = ["reflutter", str(self.apk_path)]

            # Run reflutter in the working directory
            run_tool(cmd, check=True, cwd=str(work_dir))

            # reflutter outputs release.RE.apk in the current directory
            patched_apk = work_dir / "release.RE.apk"
            if not patched_apk.exists():
                raise ReflutterError(
                    f"reflutter completed but output APK not found: {patched_apk}"
                )

            return patched_apk

        except Exception as e:
            raise ReflutterError(f"reflutter patching failed: {e}") from e

    def sign_patched_apk(
        self,
        patched_apk: Path,
        output_path: Path | None = None,
    ) -> Path:
        """Sign reflutter-patched APK using apksigner.

        Args:
            patched_apk: Path to the reflutter-patched APK.
            output_path: Output path for signed APK. Auto-generated if None.

        Returns:
            Path to signed APK.

        Raises:
            FlutterError: If signing fails.
        """
        require("apktool", "apksigner", "keytool", "zipalign")

        # First, we need to decode with apktool to get a directory for APKPatcher
        with tempfile.TemporaryDirectory(prefix="batuta-sign-") as tmpdir:
            tmp_path = Path(tmpdir)

            # Decode the patched APK with apktool
            decoded_dir = tmp_path / "decoded"
            decode_cmd = [
                "apktool",
                "d",
                "-o",
                str(decoded_dir),
                str(patched_apk),
                "-f",
            ]

            try:
                run_tool(decode_cmd, check=True)
            except Exception as e:
                raise FlutterError(f"Failed to decode patched APK: {e}") from e

            # Use APKPatcher to rebuild, align, and sign
            if output_path is None:
                output_path = (
                    patched_apk.parent / f"{self.package_name}-reflutter-signed.apk"
                )

            patcher = APKPatcher(decoded_dir, output_path)

            try:
                result = patcher.patch(sign=True, align=True)
                return result.output_path
            except Exception as e:
                raise FlutterError(f"Failed to sign patched APK: {e}") from e

    @staticmethod
    def dump_dart_code(
        package_name: str,
        output_path: Path | None = None,
        format_json: bool = True,
        device_id: str | None = None,
        check_root: bool = True,
    ) -> DumpResult:
        """Dump Dart code from instrumented Flutter app.

        Args:
            package_name: Package name of the instrumented app.
            output_path: Output file path. Defaults to ./<package>_dump.dart.
            format_json: Whether to format output as JSON.
            device_id: Target device ID (optional).
            check_root: Whether to verify root access before dumping.

        Returns:
            DumpResult with dump information.

        Raises:
            DartDumpError: If dumping fails.
        """
        require("adb")

        # Set output path
        if output_path is None:
            output_path = Path.cwd() / f"{package_name}_dump.dart"

        # Build adb command
        adb_cmd = ["adb"]
        if device_id:
            adb_cmd.extend(["-s", device_id])

        # Check root access if requested
        if check_root:
            check_cmd = adb_cmd + ["shell", "su", "-c", "id"]
            try:
                run_tool(check_cmd, check=True, capture_output=True)
            except Exception as e:
                raise DartDumpError(
                    f"Root access required for Dart dump. "
                    f"Ensure device is rooted and 'adb root' works: {e}"
                ) from e

        # Dump Dart code
        dump_cmd = adb_cmd + [
            "shell",
            "su",
            "-c",
            f"cat /data/data/{package_name}/dump.dart",
        ]

        try:
            result = run_tool(dump_cmd, check=True, capture_output=True)
            dump_content = result.stdout

            if not dump_content or dump_content.strip() == "":
                raise DartDumpError(
                    "Dump file is empty. Ensure the app has been started "
                    "at least once after installation."
                )

            # Write to file
            output_path.write_text(dump_content, encoding="utf-8")

        except Exception as e:
            raise DartDumpError(f"Failed to dump Dart code: {e}") from e

        # Try to format as JSON
        formatted_path = None
        if format_json:
            try:
                json_data = json.loads(dump_content)
                formatted_path = output_path.with_suffix(".json")
                formatted_path.write_text(
                    json.dumps(json_data, indent=2), encoding="utf-8"
                )
            except json.JSONDecodeError:
                # Not valid JSON, skip formatting
                pass

        return DumpResult(
            package_name=package_name,
            dump_path=output_path,
            formatted_path=formatted_path,
            success=True,
            auto_started=False,
        )

    @staticmethod
    def auto_start_app(
        package_name: str,
        device_id: str | None = None,
        wait_seconds: int = 8,
    ) -> bool:
        """Auto-start Flutter app using monkey.

        Args:
            package_name: Package name to start.
            device_id: Target device ID (optional).
            wait_seconds: Seconds to wait after starting.

        Returns:
            True if app was started successfully, False otherwise.
        """
        require("adb")

        # Build adb command
        adb_cmd = ["adb"]
        if device_id:
            adb_cmd.extend(["-s", device_id])

        # Use monkey to launch the app
        monkey_cmd = adb_cmd + [
            "shell",
            "monkey",
            "-p",
            package_name,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]

        try:
            run_tool(monkey_cmd, check=True, capture_output=True)
            # Wait for app to initialize
            time.sleep(wait_seconds)
            return True
        except Exception:
            return False

    def patch_and_install(
        self,
        device_id: str | None = None,
        skip_dump: bool = False,
        wait_for_user: bool = False,
        force: bool = False,
        output_dir: Path | None = None,
    ) -> FlutterPatchResult:
        """Full workflow: validate → patch → sign → install → dump.

        Args:
            device_id: Target device ID.
            skip_dump: Skip the Dart code dump step.
            wait_for_user: Wait for user to start app (vs auto-start).
            force: Skip Flutter validation.
            output_dir: Directory for output files.

        Returns:
            FlutterPatchResult with operation details.

        Raises:
            FlutterError: If any step fails.
        """
        require("adb", "reflutter", "apktool", "apksigner", "keytool", "zipalign")

        # Validate Flutter (unless forced)
        if not force:
            self.validate_flutter()

        # Set output directory
        if output_dir is None:
            output_dir = Path.cwd()
        output_dir = output_dir.resolve()

        # Patch with reflutter
        with tempfile.TemporaryDirectory(prefix="batuta-flutter-") as tmpdir:
            tmp_path = Path(tmpdir)

            patched_apk = self.patch(output_dir=tmp_path)

            # Sign the patched APK
            signed_apk = self.sign_patched_apk(
                patched_apk,
                output_path=output_dir / f"{self.package_name}-reflutter-signed.apk",
            )

            # Uninstall old version
            adb_cmd = ["adb"]
            if device_id:
                adb_cmd.extend(["-s", device_id])

            # Uninstall old version (ignore errors if not installed)
            uninstall_cmd = adb_cmd + ["uninstall", self.package_name]
            run_tool(uninstall_cmd, check=False, capture_output=True)

            # Install patched APK
            install_cmd = adb_cmd + ["install", str(signed_apk)]
            try:
                run_tool(install_cmd, check=True)
                installed = True
            except Exception as e:
                raise FlutterError(f"Failed to install patched APK: {e}") from e

            # Dump Dart code (unless skipped)
            dump_result = None
            if not skip_dump:
                # Auto-start or wait for user
                if wait_for_user:
                    # Interactive prompt
                    msg = (
                        f"\n[batuta] Please start the app "
                        f"'{self.package_name}' on the device."
                    )
                    print(msg)
                    input("Press Enter when the app has started...")
                else:
                    # Try auto-start
                    auto_started = self.auto_start_app(
                        self.package_name, device_id=device_id
                    )
                    if not auto_started:
                        print(
                            f"\n[batuta] Could not auto-start app. "
                            f"Please start '{self.package_name}' manually."
                        )
                        input("Press Enter when the app has started...")

                # Attempt dump
                try:
                    dump_result = self.dump_dart_code(
                        self.package_name,
                        output_path=output_dir / f"{self.package_name}_dump.dart",
                        device_id=device_id,
                    )
                    dump_result.auto_started = not wait_for_user
                except DartDumpError as e:
                    # Don't fail the entire operation, just report
                    print(f"\n[batuta] Warning: {e}")
                    print(
                        f"[batuta] You can manually dump later with: "
                        f"batuta flutter dump {self.package_name}"
                    )

            return FlutterPatchResult(
                package_name=self.package_name,
                original_apk=self.apk_path,
                patched_apk=patched_apk,
                signed_apk=signed_apk,
                installed=installed,
                dump_result=dump_result,
            )
