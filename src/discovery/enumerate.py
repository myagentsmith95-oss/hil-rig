from __future__ import annotations
import os
import re
from pathlib import Path
from .model import Esp32Device, CaptureDevice

SERIAL_BY_ID = Path("/dev/serial/by-id")
V4L_BY_PATH = Path("/dev/v4l/by-path")
V4L_BY_ID = Path("/dev/v4l/by-id")

QINHENG_VENDOR = "1a86"                       # ESP32's USB-serial chip vendor
WEBCAM_KEYWORDS = ("webcam", "camera", "facetime", "isight")


def enumerate_esp32() -> list[Esp32Device]:
    """Find all ESP32 boards by their stable serial by-id path."""
    devices = []
    if not SERIAL_BY_ID.is_dir():
        return devices
    for entry in sorted(SERIAL_BY_ID.iterdir()):
        if QINHENG_VENDOR not in entry.name:
            continue
        devices.append(Esp32Device(
            serial=_extract_serial(entry.name),
            port=str(entry),
            by_id_name=entry.name,
        ))
    return devices


def _extract_serial(by_id_name: str) -> str:
    # usb-1a86_USB_Single_Serial_5C63002523-if00 -> 5C63002523
    base = re.sub(r"-if\d+$", "", by_id_name)
    return base.rsplit("_", 1)[-1]


def enumerate_capture_cards() -> list[CaptureDevice]:
    """Find HDMI capture cards by their stable physical USB port (by-path)."""
    cards = []
    if not V4L_BY_PATH.is_dir():
        return cards
    seen = set()
    for entry in sorted(V4L_BY_PATH.iterdir()):
        name = entry.name
        if "-usbv2-" in name:                 # duplicate of the -usb- entry
            continue
        if not name.endswith("-video-index0"):  # index1 = metadata node
            continue
        try:
            video_dev = os.path.basename(os.readlink(entry))
        except OSError:
            continue
        if video_dev in seen:
            continue
        seen.add(video_dev)

        card_name = _v4l_card_name(video_dev)
        if _is_webcam(card_name):
            continue

        chipset = _detect_chipset(video_dev) or card_name or "unknown"
        cards.append(CaptureDevice(
            phys_key=name[: -len("-video-index0")],
            video_dev=f"/dev/{video_dev}",
            chipset=chipset,
            card_name=card_name,
        ))
    return cards


def _v4l_card_name(video_dev: str) -> str:
    try:
        return Path(f"/sys/class/video4linux/{video_dev}/name").read_text().strip()
    except OSError:
        return ""


def _is_webcam(card_name: str) -> bool:
    return any(k in card_name.lower() for k in WEBCAM_KEYWORDS)


def _detect_chipset(video_dev: str) -> str | None:
    """Best-effort chipset label.

    Reads the USB manufacturer string from sysfs first (robust even when two
    identical cards collide in /dev/v4l/by-id), then falls back to by-id.
    """
    manuf = _usb_manufacturer(video_dev)
    if manuf and "MACROSILICON" in manuf.upper():
        return "MACROSILICON"
    if V4L_BY_ID.is_dir():
        for entry in V4L_BY_ID.iterdir():
            try:
                target = os.path.basename(os.readlink(entry))
            except OSError:
                continue
            if target == video_dev and "MACROSILICON" in entry.name.upper():
                return "MACROSILICON"
    return None


def _usb_manufacturer(video_dev: str) -> str | None:
    """Walk up sysfs from the V4L device to its USB device; read manufacturer."""
    p = Path(f"/sys/class/video4linux/{video_dev}")
    try:
        p = p.resolve()
    except OSError:
        return None
    for parent in [p, *p.parents]:
        manuf = parent / "manufacturer"
        if manuf.exists():
            try:
                return manuf.read_text().strip()
            except OSError:
                return None
    return Nones