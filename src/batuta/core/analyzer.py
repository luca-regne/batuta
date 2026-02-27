"""APK analysis: detect cross-platform frameworks and native libraries."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from batuta.exceptions import AnalysisError
from batuta.models.analyze import FrameworkMatch, FrameworkResult


class FrameworkDetector:
    """Detect cross-platform frameworks in APK files."""

    FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
        "Flutter": [
            "lib/arm64-v8a/libflutter.so",
            "lib/armeabi-v7a/libflutter.so",
            "lib/x86_64/libflutter.so",
            "assets/flutter_assets/",
        ],
        "React Native": [
            "lib/arm64-v8a/libreactnativejni.so",
            "lib/armeabi-v7a/libreactnativejni.so",
            "lib/x86/libreactnativejni.so",
            "lib/x86_64/libreactnativejni.so",
            "assets/index.android.bundle",
        ],
        "Xamarin": [
            "assemblies/Xamarin.Android.dll",
            "assemblies/Mono.Android.dll",
            "lib/arm64-v8a/libmonosgen-2.0.so",
            "lib/armeabi-v7a/libmonosgen-2.0.so",
        ],
        "Cordova": [
            "assets/www/cordova.js",
            "assets/www/cordova_plugins.js",
        ],
        "Unity": [
            "lib/arm64-v8a/libunity.so",
            "lib/armeabi-v7a/libunity.so",
            "assets/bin/Data/",
        ],
    }

    def __init__(self, apk_path: Path):
        """Initialize framework detector.

        Args:
            apk_path: Path to the APK file to analyze.
        """
        self.apk_path = apk_path.resolve()

    def _validate_apk(self) -> None:
        """Validate that APK exists and is a valid file.

        Raises:
            AnalysisError: If APK is invalid.
        """
        if not self.apk_path.exists():
            raise AnalysisError(f"APK not found: {self.apk_path}")

        if not self.apk_path.is_file():
            raise AnalysisError(f"Not a file: {self.apk_path}")

        if not self.apk_path.suffix.lower() == ".apk":
            raise AnalysisError(
                f"Not an APK file (expected .apk extension): {self.apk_path}"
            )

    def _collect_native_libs(self, namelist: list[str]) -> list[str]:
        """Extract native library paths from APK file list.

        Args:
            namelist: List of file paths in the APK.

        Returns:
            Sorted list of .so file paths.
        """
        return sorted(entry for entry in namelist if entry.endswith(".so"))

    def _detect_frameworks(self, namelist: list[str]) -> list[FrameworkMatch]:
        """Detect frameworks based on signature matching.

        Args:
            namelist: List of file paths in the APK.

        Returns:
            List of detected frameworks with matched evidence.
        """
        # Convert to set for O(1) lookups
        files_set = set(namelist)
        # Also track directory prefixes for directory-based signatures
        detected: list[FrameworkMatch] = []

        for framework, signatures in self.FRAMEWORK_SIGNATURES.items():
            matched_files: list[str] = []

            for sig in signatures:
                if sig.endswith("/"):
                    # Directory signature: check if any file starts with this path
                    for entry in namelist:
                        if entry.startswith(sig):
                            matched_files.append(sig)
                            break
                elif sig in files_set:
                    matched_files.append(sig)

            if matched_files:
                detected.append(
                    FrameworkMatch(
                        name=framework,
                        matched_files=sorted(set(matched_files)),
                    )
                )

        # Sort by framework name for deterministic output
        return sorted(detected, key=lambda m: m.name)

    def detect(self, include_native_libs: bool = True) -> FrameworkResult:
        """Analyze APK and return detected frameworks and native libraries.

        Args:
            include_native_libs: If True, include list of all native libraries.

        Returns:
            FrameworkResult with detected frameworks and native libraries.

        Raises:
            AnalysisError: If APK cannot be read or is invalid.
        """
        self._validate_apk()

        try:
            with ZipFile(self.apk_path, "r") as apk_zip:
                namelist = apk_zip.namelist()
        except BadZipFile as e:
            raise AnalysisError(f"Invalid APK (not a valid ZIP file): {e}") from e
        except OSError as e:
            raise AnalysisError(f"Failed to read APK: {e}") from e

        detected_frameworks = self._detect_frameworks(namelist)
        native_libraries = (
            self._collect_native_libs(namelist) if include_native_libs else []
        )

        return FrameworkResult(
            apk_path=self.apk_path,
            detected_frameworks=detected_frameworks,
            native_libraries=native_libraries,
        )
