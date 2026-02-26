"""ADB wrapper for device and package management."""

import contextlib
import re
import shutil
from pathlib import Path

from batuta.exceptions import (
    APKPullError,
    DeviceNotFoundError,
    MultiplePackagesFoundError,
    PackageNotFoundError,
)
from batuta.models.apk import PackageInfo, PulledAPK
from batuta.models.device import Device, DeviceList, DeviceState
from batuta.utils.process import run_tool


class ADBWrapper:
    """Wrapper for ADB commands."""

    def __init__(self, device_id: str | None = None):
        """Initialize ADB wrapper.

        Args:
            device_id: Optional device ID to target. If None, uses default device.
        """
        self.device_id = device_id

    def _adb(self, *args: str, check: bool = True) -> list[str]:
        """Run an ADB command and return output lines.

        Args:
            *args: ADB command arguments.
            check: If True, raise on non-zero exit.

        Returns:
            List of output lines.
        """
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)

        result = run_tool(cmd, check=check)
        return result.lines

    def list_devices(self) -> DeviceList:
        """List all connected ADB devices.

        Returns:
            DeviceList containing all connected devices.
        """
        # Run without device selector
        result = run_tool(["adb", "devices", "-l"])
        devices = []

        for line in result.lines[1:]:  # Skip header line
            if not line.strip():
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            device_id = parts[0]
            state_str = parts[1]

            # Parse state
            try:
                state = DeviceState(state_str)
            except ValueError:
                state = DeviceState.UNKNOWN

            # Parse additional properties
            model = None
            product = None
            transport_id = None

            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
                elif part.startswith("product:"):
                    product = part.split(":", 1)[1]
                elif part.startswith("transport_id:"):
                    transport_id = part.split(":", 1)[1]

            devices.append(
                Device(
                    id=device_id,
                    state=state,
                    model=model,
                    product=product,
                    transport_id=transport_id,
                )
            )

        return DeviceList(devices=devices)

    def ensure_device(self) -> Device:
        """Ensure a device is available and return it.

        Returns:
            The target device.

        Raises:
            DeviceNotFoundError: If no device is connected or device not found.
        """
        devices = self.list_devices()

        if self.device_id:
            device = devices.get_by_id(self.device_id)
            if not device:
                raise DeviceNotFoundError(f"Device not found: {self.device_id}")
            if not device.is_available:
                raise DeviceNotFoundError(
                    f"Device {self.device_id} is {device.state.value}"
                )
            return device

        available = devices.available
        if not available:
            if devices.devices:
                states = [f"{d.id}: {d.state.value}" for d in devices.devices]
                raise DeviceNotFoundError(
                    f"No available devices. Found: {', '.join(states)}"
                )
            raise DeviceNotFoundError("No devices connected")

        if len(available) > 1:
            ids = [d.id for d in available]
            raise DeviceNotFoundError(
                f"Multiple devices connected: {', '.join(ids)}. "
                "Use --device to specify which one."
            )

        return available[0]

    def list_packages(
        self, include_system: bool = False, filter: str | None = None
    ) -> list[str]:
        """List all installed packages.

        Args:
            include_system: If True, include system packages.

        Returns:
            List of package names.
        """
        self.ensure_device()

        cmd = ["shell", "pm", "list", "packages"]

        if not include_system:
            cmd.append("-3")

        if filter:
            cmd.append(filter)

        lines = self._adb(*cmd)

        packages = []
        for line in lines:
            if line.startswith("package:"):
                packages.append(line.split(":", 1)[1])

        return sorted(packages)

    def search_packages(
        self,
        query: str,
        include_system: bool = False,
        search_names: bool = False,
        detailed: bool = False,
    ) -> list[PackageInfo]:
        """Search for packages matching a query.

        By default, searches package names only using ADB's native filter.
        Use search_names=True to also search app display names (slower).
        Use detailed=True to fetch full package metadata (slower).

        Args:
            query: Search query (substring match against package names).
            include_system: If True, include system packages.
            search_names: If True, also search app display names (slower).
            detailed: If True, fetch full package metadata (slower).

        Returns:
            List of matching PackageInfo objects.
        """
        self.ensure_device()
        query_lower = query.lower()

        # Fast path: use ADB's native package name filter
        matches = self.list_packages(include_system=include_system, filter=query)

        # Optionally search app labels (expensive - requires dumpsys per package)
        if search_names and not matches:
            all_packages = self.list_packages(include_system=include_system)
            for pkg in all_packages:
                try:
                    info = self.get_package_info(pkg)
                    if info.app_name and query_lower in info.app_name.lower():
                        matches.append(pkg)
                except Exception:
                    continue

        # Build results - only fetch full info if detailed=True
        results = []
        for pkg in matches:
            if detailed:
                try:
                    results.append(self.get_package_info(pkg))
                except Exception:
                    results.append(PackageInfo(package_name=pkg))
            else:
                results.append(PackageInfo(package_name=pkg))

        return results

    def get_package_info(self, package_name: str) -> PackageInfo:
        """Get detailed information about a package.

        Args:
            package_name: Full package name.

        Returns:
            PackageInfo with package details.

        Raises:
            PackageNotFoundError: If package is not installed.
        """
        self.ensure_device()

        try:
            lines = self._adb("shell", "pm", "path", package_name)
        except Exception as exc:
            raise PackageNotFoundError(package_name) from exc

        if not lines:
            raise PackageNotFoundError(package_name)

        apk_paths = []
        for line in lines:
            if line.startswith("package:"):
                apk_paths.append(line.split(":", 1)[1])

        if not apk_paths:
            raise PackageNotFoundError(package_name)

        # Separate base APK and splits
        base_apk = None
        split_apks = []

        for path in apk_paths:
            if "split_" in path or "/split_" in path:
                split_apks.append(path)
            elif base_apk is None:
                base_apk = path
            else:
                # Multiple non-split APKs - treat first as base
                split_apks.append(path)

        # Get app label using dumpsys
        app_name = self._get_app_label(package_name)

        # Get version info
        version_name = None
        version_code = None

        try:
            dumpsys = self._adb("shell", "dumpsys", "package", package_name)
            for line in dumpsys:
                line = line.strip()
                if line.startswith("versionName="):
                    version_name = line.split("=", 1)[1]
                elif line.startswith("versionCode="):
                    # Format: versionCode=123 minSdk=...
                    version_str = line.split("=", 1)[1].split()[0]
                    with contextlib.suppress(ValueError):
                        version_code = int(version_str)
                if version_name and version_code:
                    break
        except Exception:
            pass

        return PackageInfo(
            package_name=package_name,
            app_name=app_name,
            version_name=version_name,
            version_code=version_code,
            apk_path=base_apk,
            split_apks=split_apks if split_apks else None,
        )

    def _get_app_label(self, package_name: str) -> str | None:
        """Get the app label (display name) for a package.

        Args:
            package_name: Full package name.

        Returns:
            App label or None if not found.
        """
        try:
            # Try using cmd package which gives cleaner output
            self._adb(
                "shell",
                "cmd",
                "package",
                "resolve-activity",
                "--brief",
                package_name,
            )
            # Fallback to dumpsys for app label
            dumpsys = self._adb("shell", "dumpsys", "package", package_name)

            for line in dumpsys:
                # Look for the application label in various formats
                if "applicationInfo" in line.lower():
                    continue
                match = re.search(r'label[=:]"?([^"}\n]+)"?', line, re.IGNORECASE)
                if match:
                    label = match.group(1).strip()
                    if label and label != package_name:
                        return label
        except Exception:
            pass

        return None

    def pull_apk(
        self,
        package_name: str,
        output_dir: Path | None = None,
    ) -> PulledAPK:
        """Pull APK(s) from a device.

        Args:
            package_name: Package name to pull.
            output_dir: Directory to save APKs. Defaults to current directory.

        Returns:
            PulledAPK with paths to pulled files.

        Raises:
            PackageNotFoundError: If package is not found.
            APKPullError: If pull fails.
        """
        info = self.get_package_info(package_name)
        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        if info.is_split:
            return self._pull_split_apk(info, output_dir)
        else:
            return self._pull_single_apk(info, output_dir)

    def _pull_single_apk(self, info: PackageInfo, output_dir: Path) -> PulledAPK:
        """Pull a single APK."""
        if not info.apk_path:
            raise APKPullError(f"No APK path for {info.package_name}")

        # Determine output filename
        filename = f"{info.package_name}.apk"
        if info.version_name:
            filename = f"{info.package_name}-{info.version_name}.apk"

        output_path = output_dir / filename

        try:
            self._adb("pull", info.apk_path, str(output_path))
        except Exception as e:
            raise APKPullError(f"Failed to pull {info.package_name}: {e}") from e

        if not output_path.exists():
            raise APKPullError(f"Pull succeeded but file not found: {output_path}")

        return PulledAPK(
            package_name=info.package_name,
            local_path=output_path,
            is_split=False,
        )

    def _pull_split_apk(self, info: PackageInfo, output_dir: Path) -> PulledAPK:
        """Pull a split APK (base + splits)."""
        # Create a directory for this package's APKs
        pkg_dir = output_dir / info.package_name
        if info.version_name:
            pkg_dir = output_dir / f"{info.package_name}-{info.version_name}"

        pkg_dir.mkdir(parents=True, exist_ok=True)

        pulled_paths = []

        for apk_path in info.all_apk_paths:
            # Extract filename from device path
            filename = Path(apk_path).name
            output_path = pkg_dir / filename

            try:
                self._adb("pull", apk_path, str(output_path))
                pulled_paths.append(output_path)
            except Exception as e:
                # Clean up on failure
                shutil.rmtree(pkg_dir, ignore_errors=True)
                raise APKPullError(
                    f"Failed to pull {filename} for {info.package_name}: {e}"
                ) from e

        return PulledAPK(
            package_name=info.package_name,
            local_path=pkg_dir,
            is_split=True,
            split_paths=pulled_paths,
        )

    def find_package(
        self,
        query: str,
        include_system: bool = False,
        search_names: bool = False,
        detailed: bool = False,
    ) -> PackageInfo:
        """Find a single package matching query.

        Args:
            query: Package name or filter (substring match).
            include_system: If True, include system packages.
            search_names: If True, also search app display names (slower).
            detailed: If True, fetch full package metadata (slower).

        Returns:
            PackageInfo for the matching package.

        Raises:
            PackageNotFoundError: If no package matches.
            MultiplePackagesFoundError: If multiple matches and not allow_multiple.
        """
        matches = self.search_packages(
            query,
            include_system=include_system,
            search_names=search_names,
            detailed=detailed,
        )

        if not matches:
            raise PackageNotFoundError(query)

        if len(matches) == 1:
            return matches[0]

        raise MultiplePackagesFoundError(query, [m.package_name for m in matches])
