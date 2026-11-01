"""Model profiles (shared per phone model) and slot configs (per-device wiring)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

MODELS_DIR = Path("models")
DEVICES_DIR = Path("devices")


@dataclass
class ModelProfile:
    name: str
    screen_w: int
    screen_h: int
    capture_w: int
    capture_h: int
    home: tuple | None
    pair_swipe: tuple          # (x1, y1, x2, y2, ms) in capture coords
    motion_threshold: float = 5.0


@dataclass
class SlotConfig:
    slot: str
    model: str
    esp32_serial: str
    capture_port: str


def load_model(name, models_dir=MODELS_DIR) -> ModelProfile:
    path = Path(models_dir) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Model '{name}' not found at {path}")
    d = yaml.safe_load(path.read_text()) or {}
    screen = d.get("screen", {})
    cap = d.get("capture", {})
    pairing = d.get("pairing", {})
    swipe = pairing.get("swipe", {})
    home = d.get("home")
    return ModelProfile(
        name=name,
        screen_w=int(screen.get("width", 0)),
        screen_h=int(screen.get("height", 0)),
        capture_w=int(cap.get("width", 0)),
        capture_h=int(cap.get("height", 0)),
        home=tuple(home) if home else None,
        pair_swipe=(int(swipe.get("x1", 0)), int(swipe.get("y1", 0)),
                    int(swipe.get("x2", 0)), int(swipe.get("y2", 0)),
                    int(swipe.get("ms", 400))),
        motion_threshold=float(pairing.get("motion_threshold", 5.0)),
    )


def load_slots(devices_dir=DEVICES_DIR) -> list[SlotConfig]:
    slots = []
    d = Path(devices_dir)
    if not d.is_dir():
        return slots
    for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            continue
        if not all(k in data for k in ("model", "esp32_serial", "capture_port")):
            continue                       # not a slot file (e.g. legacy) -> skip
        slots.append(SlotConfig(
            slot=str(data.get("slot", f.stem)),
            model=str(data["model"]),
            esp32_serial=str(data["esp32_serial"]),
            capture_port=str(data["capture_port"]),
        ))
    return slots


def write_slot(slot: SlotConfig, devices_dir=DEVICES_DIR):
    d = Path(devices_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slot.slot}.yaml").write_text(
        f"slot: {slot.slot}\n"
        f"model: {slot.model}\n"
        f'esp32_serial: "{slot.esp32_serial}"\n'
        f'capture_port: "{slot.capture_port}"\n'
    )