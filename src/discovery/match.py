from __future__ import annotations
from pathlib import Path
from ..config import load_slots
from .model import Topology, RigDevice
from .enumerate import enumerate_esp32, enumerate_capture_cards


def build_topology(devices_dir):
    esp32s = enumerate_esp32()
    captures = enumerate_capture_cards()
    slots = load_slots(devices_dir)

    esp_by_serial = {e.serial: e for e in esp32s}
    cap_by_key = {c.phys_key: c for c in captures}

    devices = [
        RigDevice(name=s.slot, model_name=s.model,
                  esp32=esp_by_serial.get(s.esp32_serial),
                  capture=cap_by_key.get(s.capture_port))
        for s in slots
    ]
    return Topology(esp32s=esp32s, captures=captures, devices=devices)