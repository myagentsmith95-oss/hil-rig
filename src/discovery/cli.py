from __future__ import annotations
import argparse
import json
from pathlib import Path
from .match import build_topology
from .pair import auto_pair


def _print_text(topo):
    print("== ESP32 boards ==")
    for e in topo.esp32s or []:
        print(f"  serial={e.serial}  port={e.port}")
    if not topo.esp32s:
        print("  (none found)")

    print("\n== Capture cards ==")
    for c in topo.captures:
        print(f"  {c.chipset:<14} {c.video_dev}  phys_key={c.phys_key}")
    if not topo.captures:
        print("  (none found)")

    print("\n== Device slots ==")
    for d in topo.devices:
        print(f"  {d.name:<10} model={d.model_name:<8} {d.status.value}")
        print(f"      esp32  : {d.esp32.serial if d.esp32 else 'MISSING'}")
        print(f"      capture: {d.capture.video_dev if d.capture else 'MISSING'}")
    if not topo.devices:
        print("  (no slots in devices/ — run: python -m src.discovery.cli pair)")

    ready = topo.ready_devices()
    print(f"\n{len(ready)}/{len(topo.devices)} device(s) READY")


def _to_json(topo):
    return json.dumps({
        "esp32s": [{"serial": e.serial, "port": e.port} for e in topo.esp32s],
        "captures": [{"chipset": c.chipset, "video_dev": c.video_dev,
                      "phys_key": c.phys_key} for c in topo.captures],
        "devices": [{"name": d.name, "model": d.model_name,
                     "status": d.status.value,
                     "esp32": d.esp32.serial if d.esp32 else None,
                     "capture": d.capture.video_dev if d.capture else None}
                    for d in topo.devices],
    }, indent=2)


def main():
    ap = argparse.ArgumentParser(prog="hil-discover",
                                 description="Discover / pair HIL rig hardware.")
    ap.add_argument("command", nargs="?", default="discover",
                    choices=["discover", "pair"])
    ap.add_argument("--devices-dir", default="devices")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--model", default="pixel6", help="model profile for pairing")
    args = ap.parse_args()

    if args.command == "pair":
        auto_pair(args.model, devices_dir=args.devices_dir)
        return 0

    topo = build_topology(Path(args.devices_dir))
    print(_to_json(topo) if args.json else _print_text(topo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())