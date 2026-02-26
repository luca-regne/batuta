"""APK patching: build, align, and sign APKs from apktool directories."""

import tempfile
from pathlib import Path

from batuta.exceptions import APKAlignError, APKBuildError, APKSignError
from batuta.models.apk import PatchResult
from batuta.utils.android_sdk import get_apksigner, get_zipalign
from batuta.utils.deps import require
from batuta.utils.process import run_tool


class APKPatcher:
    """Handles APK building, aligning, and signing from apktool directories."""

    # Default keystore location
    DEFAULT_KEYSTORE_DIR = Path.home() / ".batuta"
    DEFAULT_KEYSTORE_NAME = "debug.keystore"
    DEFAULT_KEY_ALIAS = "androiddebugkey"
    DEFAULT_STORE_PASS = "android"
    DEFAULT_KEY_PASS = "android"

    def __init__(
        self,
        apktool_dir: Path,
        output_path: Path | None = None,
    ):
        """Initialize APK patcher.

        Args:
            apktool_dir: Path to apktool-decoded directory.
            output_path: Output APK path. Defaults to <dir>-patched.apk.
        """
        self.apktool_dir = apktool_dir.resolve()
        self.output_path = (
            output_path.resolve()
            if output_path
            else self.apktool_dir.parent / f"{self.apktool_dir.name}-patched.apk"
        )

    def validate(self) -> None:
        """Validate that apktool_dir is a valid apktool directory.

        Raises:
            APKBuildError: If directory is invalid.
        """
        if not self.apktool_dir.is_dir():
            raise APKBuildError(f"Directory not found: {self.apktool_dir}")

        apktool_yml = self.apktool_dir / "apktool.yml"
        if not apktool_yml.is_file():
            raise APKBuildError(
                f"Not a valid apktool directory (missing apktool.yml): "
                f"{self.apktool_dir}"
            )

    def build(self, output: Path) -> Path:
        """Build APK from apktool directory.

        Args:
            output: Output APK path.

        Returns:
            Path to built APK.

        Raises:
            APKBuildError: If build fails.
        """
        require("apktool")

        cmd = ["apktool", "b", str(self.apktool_dir), "-o", str(output)]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise APKBuildError(f"Failed to build APK: {e}") from e

        if not output.is_file():
            raise APKBuildError(f"Build completed but APK not found: {output}")

        return output

    def align(self, input_apk: Path, output: Path) -> Path:
        """Align APK using zipalign.

        Args:
            input_apk: Input APK path.
            output: Output aligned APK path.

        Returns:
            Path to aligned APK.

        Raises:
            APKAlignError: If alignment fails.
        """
        zipalign = get_zipalign()

        # zipalign -p 4 input.apk output.apk
        # -p: page-align shared object files
        # 4: 4-byte alignment (required for Android)
        cmd = [str(zipalign), "-P", "16", "4", str(input_apk), str(output)]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise APKAlignError(f"Failed to align APK: {e}") from e

        if not output.is_file():
            raise APKAlignError(f"Alignment completed but APK not found: {output}")

        return output

    def sign(
        self,
        input_apk: Path,
        output: Path,
        keystore: Path,
        key_alias: str = DEFAULT_KEY_ALIAS,
        keystore_pass: str = DEFAULT_STORE_PASS,
        key_pass: str = DEFAULT_KEY_PASS,
    ) -> Path:
        """Sign APK using apksigner.

        Args:
            input_apk: Input APK path.
            output: Output signed APK path.
            keystore: Keystore file path.
            key_alias: Key alias in keystore.
            keystore_pass: Keystore password.
            key_pass: Key password.

        Returns:
            Path to signed APK.

        Raises:
            APKSignError: If signing fails.
        """
        apksigner = get_apksigner()

        cmd = [
            str(apksigner),
            "sign",
            "--ks",
            str(keystore),
            "--ks-key-alias",
            key_alias,
            "--ks-pass",
            f"pass:{keystore_pass}",
            "--key-pass",
            f"pass:{key_pass}",
            "--out",
            str(output),
            str(input_apk),
        ]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise APKSignError(f"Failed to sign APK: {e}") from e

        if not output.is_file():
            raise APKSignError(f"Signing completed but APK not found: {output}")

        return output

    def verify(self, apk: Path) -> bool:
        """Verify APK signature.

        Args:
            apk: APK path to verify.

        Returns:
            True if verification passed.

        Raises:
            APKSignError: If verification fails.
        """
        apksigner = get_apksigner()

        cmd = [str(apksigner), "verify", "--verbose", str(apk)]

        try:
            result = run_tool(cmd, check=False)
            return result.success
        except Exception as e:
            raise APKSignError(f"Failed to verify APK: {e}") from e

    def generate_debug_keystore(self) -> Path:
        """Generate a debug keystore if it doesn't exist.

        Returns:
            Path to debug keystore.

        Raises:
            APKSignError: If keystore generation fails.
        """
        require("keytool")

        # Create keystore directory if needed
        self.DEFAULT_KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)
        keystore_path = self.DEFAULT_KEYSTORE_DIR / self.DEFAULT_KEYSTORE_NAME

        if keystore_path.is_file():
            return keystore_path

        # Generate new debug keystore
        cmd = [
            "keytool",
            "-genkey",
            "-v",
            "-keystore",
            str(keystore_path),
            "-alias",
            self.DEFAULT_KEY_ALIAS,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "10000",
            "-storepass",
            self.DEFAULT_STORE_PASS,
            "-keypass",
            self.DEFAULT_KEY_PASS,
            "-dname",
            "CN=Debug, OU=Debug, O=Debug, L=Debug, ST=Debug, C=US",
        ]

        try:
            run_tool(cmd, check=True)
        except Exception as e:
            raise APKSignError(f"Failed to generate debug keystore: {e}") from e

        if not keystore_path.is_file():
            raise APKSignError(
                f"Keystore generation completed but file not found: {keystore_path}"
            )

        return keystore_path

    def patch(
        self,
        sign: bool = True,
        align: bool = True,
        verify_signature: bool = False,
        keystore: Path | None = None,
        key_alias: str = DEFAULT_KEY_ALIAS,
        keystore_pass: str = DEFAULT_STORE_PASS,
        key_pass: str = DEFAULT_KEY_PASS,
    ) -> PatchResult:
        """Execute full patch workflow: build, align, sign.

        Args:
            sign: Whether to sign the APK.
            align: Whether to align the APK.
            verify_signature: Whether to verify signature after signing.
            keystore: Keystore path. If None and sign=True, generates debug keystore.
            key_alias: Key alias for signing.
            keystore_pass: Keystore password.
            key_pass: Key password.

        Returns:
            PatchResult with details of the patch operation.

        Raises:
            APKBuildError: If build fails.
            APKAlignError: If alignment fails.
            APKSignError: If signing or verification fails.
        """
        self.validate()

        keystore_generated = False
        verified: bool | None = None

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Step 1: Build
            built_apk = tmp_path / "built.apk"
            self.build(built_apk)

            current_apk = built_apk

            # Step 2: Align (if requested)
            if align:
                aligned_apk = tmp_path / "aligned.apk"
                self.align(current_apk, aligned_apk)
                current_apk = aligned_apk

            # Step 3: Sign (if requested)
            if sign:
                # Get or generate keystore
                if keystore is None:
                    keystore = self.generate_debug_keystore()
                    keystore_generated = True

                self.sign(
                    current_apk,
                    self.output_path,
                    keystore,
                    key_alias,
                    keystore_pass,
                    key_pass,
                )

                # Step 4: Verify (if requested)
                if verify_signature:
                    verified = self.verify(self.output_path)
            else:
                # No signing, just copy to output
                import shutil

                shutil.copy2(current_apk, self.output_path)

        return PatchResult(
            source_dir=self.apktool_dir,
            output_path=self.output_path,
            signed=sign,
            aligned=align,
            verified=verified,
            keystore_generated=keystore_generated,
        )
