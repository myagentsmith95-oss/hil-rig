from __future__ import annotations
import argparse
import json
from pathlib import Path
from .match import build_topology


def main() -> int:
    ap = argparse.ArgumentParser(prog="hil-discover",
                                 description="Discover HIL rig hardware topology.")
    ap.add_argument("--devices-dir", default="devices",
                    help="directory with device YAML configs")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    topo = build_topology(Path(args.devices_dir))
    if args.json:
        print(_to_json(topo))
        return 0

    print("== ESP32 boards ==")
    for e in topo.esp32s or []:
        print(f"  serial={e.serial}  port={e.port}")
    if not topo.esp32s:
        print("  (none found)")

    print("\n== Capture cards ==")
    for c in topo.captures:
        print(f"  {c.chipset:<14} {c.video_dev}  phys_key={c.phys_key}")
        if c.card_name:
            print(f"  {'':14} name: {c.card_name}")
    if not topo.captures:
        print("  (none found)")

    print("\n== Configured devices ==")
    for d in topo.devices:
        print(f"  {d.name:<14} {d.status.value}")
        print(f"      esp32  : {d.esp32.serial if d.esp32 else 'MISSING'}")
        print(f"      capture: {d.capture.video_dev if d.capture else 'MISSING'}")
    if not topo.devices:
        print("  (no device configs in devices/)")

    ready = topo.ready_devices()
    print(f"\n{len(ready)}/{len(topo.devices)} device(s) READY")
    return 0


def _to_json(topo) -> str:
    return json.dumps({
        "esp32s": [{"serial": e.serial, "port": e.port} for e in topo.esp32s],
        "captures": [{"chipset": c.chipset, "video_dev": c.video_dev,
                      "phys_key": c.phys_key, "card_name": c.card_name}
                     for c in topo.captures],
        "devices": [{"name": d.name, "status": d.status.value,
                     "esp32": d.esp32.serial if d.esp32 else None,
                     "capture": d.capture.video_dev if d.capture else None}
                    for d in topo.devices],
    }, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())