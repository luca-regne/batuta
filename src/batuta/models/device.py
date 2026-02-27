"""Pydantic models for Android devices."""

from enum import StrEnum

from pydantic import BaseModel


class DeviceState(StrEnum):
    """ADB device connection state."""

    DEVICE = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    NO_PERMISSIONS = "no permissions"
    UNKNOWN = "unknown"


class Device(BaseModel):
    """Represents a connected Android device."""

    id: str
    """Device serial number or identifier."""

    state: DeviceState
    """Current connection state."""

    model: str | None = None
    """Device model name (ro.product.model)."""

    product: str | None = None
    """Product name (ro.product.name)."""

    transport_id: str | None = None
    """ADB transport ID."""

    @property
    def is_available(self) -> bool:
        """Check if device is available for commands."""
        return self.state == DeviceState.DEVICE

    @property
    def display_name(self) -> str:
        """Human-readable device name."""
        if self.model:
            return f"{self.model} ({self.id})"
        return self.id


class DeviceList(BaseModel):
    """List of connected devices."""

    devices: list[Device]

    def __len__(self) -> int:
        return len(self.devices)

    @property
    def available(self) -> list[Device]:
        """Get devices that are available for commands."""
        return [d for d in self.devices if d.is_available]

    def get_by_id(self, device_id: str) -> Device | None:
        """Find a device by its ID."""
        for device in self.devices:
            if device.id == device_id:
                return device
        return None
