from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class DeviceStatus(str, Enum):
    READY = "READY"
    ESP32_MISSING = "ESP32_MISSING"
    CAPTURE_MISSING = "CAPTURE_MISSING"
    ALL_MISSING = "ALL_MISSING"


@dataclass
class Esp32Device:
    serial: str
    port: str            # stable /dev/serial/by-id/... path
    by_id_name: str


@dataclass
class CaptureDevice:
    phys_key: str        # stable by-path key (physical USB port)
    video_dev: str       # e.g. /dev/video3
    chipset: str = "unknown"
    card_name: str = ""


@dataclass
class RigDevice:
    name: str                       # slot name, e.g. "rig-0"
    model_name: str = ""            # reference to models/<name>.yaml
    esp32: Esp32Device | None = None
    capture: CaptureDevice | None = None

    @property
    def status(self) -> DeviceStatus:
        if self.esp32 and self.capture:
            return DeviceStatus.READY
        if self.esp32:
            return DeviceStatus.CAPTURE_MISSING
        if self.capture:
            return DeviceStatus.ESP32_MISSING
        return DeviceStatus.ALL_MISSING

    @property
    def is_ready(self) -> bool:
        return self.status == DeviceStatus.READY


@dataclass
class Topology:
    esp32s: list[Esp32Device] = field(default_factory=list)
    captures: list[CaptureDevice] = field(default_factory=list)
    devices: list[RigDevice] = field(default_factory=list)

    def ready_devices(self) -> list[RigDevice]:
        return [d for d in self.devices if d.is_ready]