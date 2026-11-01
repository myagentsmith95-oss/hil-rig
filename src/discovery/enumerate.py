from __future__ import annotations
import os
import re
import fcntl
import struct
from pathlib import Path
from .model import Esp32Device, CaptureDevice

SERIAL_BY_ID = Path("/dev/serial/by-id")
V4L_BY_PATH = Path("/dev/v4l/by-path")
V4L_BY_ID = Path("/dev/v4l/by-id")

QINHENG_VENDOR = "1a86"                       # ESP32's USB-serial chip vendor
WEBCAM_KEYWORDS = ("webcam", "camera", "facetime", "isight")

# V4L2 constants for detecting video-capture vs metadata nodes
_VIDIOC_QUERYCAP = 0x80685600
_V4L2_CAP_VIDEO_CAPTURE = 0x00000001
_V4L2_CAP_DEVICE_CAPS = 0x80000000

_NODE_RE = re.compile(r"^(?P<phys>.+)-video-index\d+$")


# ---------- ESP32 boards ----------

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


# ---------- Capture cards ----------

def enumerate_capture_cards() -> list[CaptureDevice]:
    """Find HDMI capture cards by stable physical USB port (by-path).

    Each card exposes several /dev/videoN nodes (one video-capture, one
    metadata). The kernel does NOT guarantee the capture node is index0, so
    for every physical card we probe its nodes and keep the one that actually
    reports Video Capture capability.
    """
    cards = []
    if not V4L_BY_PATH.is_dir():
        return cards

    # Group every video node by its physical USB port.
    phys_nodes: dict[str, list[str]] = {}
    for entry in V4L_BY_PATH.iterdir():
        name = entry.name
        if "-usbv2-" in name:                 # duplicate of the -usb- entry
            continue
        m = _NODE_RE.match(name)
        if not m:
            continue
        try:
            video_dev = os.path.basename(os.readlink(entry))
        except OSError:
            continue
        phys_nodes.setdefault(m.group("phys"), []).append(video_dev)

    for phys_key, video_devs in sorted(phys_nodes.items()):
        picked = None
        picked_name = ""
        for video_dev in sorted(video_devs):
            cname = _v4l_card_name(video_dev)
            if _is_webcam(cname):
                continue                       # skip built-in webcam
            if _can_capture(video_dev):
                picked = video_dev
                picked_name = cname
                break
        if picked is None:
            continue
        cards.append(CaptureDevice(
            phys_key=phys_key,
            video_dev=f"/dev/{picked}",
            chipset=_detect_chipset(picked) or picked_name or "unknown",
            card_name=picked_name,
        ))
    return cards


def _can_capture(video_dev: str) -> bool:
    """True if /dev/videoN is a video-capture node (not the metadata node)."""
    result = _can_capture_ioctl(video_dev)
    if result is not None:
        return result
    # Fallback: metadata nodes fail to open in OpenCV, capture nodes open fine.
    import cv2
    cap = cv2.VideoCapture(f"/dev/{video_dev}", cv2.CAP_V4L2)
    try:
        return cap.isOpened()
    finally:
        cap.release()


def _can_capture_ioctl(video_dev: str):
    """Use VIDIOC_QUERYCAP to check for Video Capture. Returns None on error."""
    try:
        fd = os.open(f"/dev/{video_dev}", os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        buf = bytearray(104)                  # struct v4l2_capability
        fcntl.ioctl(fd, _VIDIOC_QUERYCAP, buf)
        fields = struct.unpack_from("=16s32s32sIII3I", buf, 0)
        capabilities, device_caps = fields[4], fields[5]
        effective = device_caps if (capabilities & _V4L2_CAP_DEVICE_CAPS) else capabilities
        return bool(effective & _V4L2_CAP_VIDEO_CAPTURE)
    except OSError:
        return None
    finally:
        os.close(fd)


def _v4l_card_name(video_dev: str) -> str:
    try:
        return Path(f"/sys/class/video4linux/{video_dev}/name").read_text().strip()
    except OSError:
        return ""


def _is_webcam(card_name: str) -> bool:
    return any(k in card_name.lower() for k in WEBCAM_KEYWORDS)


def _detect_chipset(video_dev: str) -> str | None:
    """Best-effort chipset label (reads USB manufacturer from sysfs, then by-id)."""
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
    return None