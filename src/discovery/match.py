from __future__ import annotations
from pathlib import Path
import yaml
from .model import Topology, RigDevice
from .enumerate import enumerate_esp32, enumerate_capture_cards


def load_device_configs(devices_dir: Path) -> list[dict]:
    configs = []
    devices_dir = Path(devices_dir)
    if not devices_dir.is_dir():
        return configs
    files = sorted(devices_dir.glob("*.yaml")) + sorted(devices_dir.glob("*.yml"))
    for f in files:
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            continue
        data.setdefault("name", f.stem)
        configs.append(data)
    return configs


def build_topology(devices_dir: Path) -> Topology:
    esp32s = enumerate_esp32()
    captures = enumerate_capture_cards()
    configs = load_device_configs(devices_dir)

    esp_by_serial = {e.serial: e for e in esp32s}
    cap_by_key = {c.phys_key: c for c in captures}

    devices = []
    for cfg in configs:
        esp = esp_by_serial.get(str(cfg.get("esp32_serial", "")))
        cap = cap_by_key.get(str(cfg.get("capture_port", "")))
        devices.append(RigDevice(name=cfg.get("name", "?"), config=cfg,
                                 esp32=esp, capture=cap))
    return Topology(esp32s=esp32s, captures=captures, devices=devices)