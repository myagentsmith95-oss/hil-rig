"""Auto-pair ESP32 boards to capture cards using a visible swipe probe."""
from __future__ import annotations
import time
import cv2
import numpy as np

from ..config import load_model, SlotConfig, write_slot
from ..driver import (CaptureCard, open_esp32_no_reset,
                      handshake, sync_res, drain_until_done)
from .enumerate import enumerate_esp32, enumerate_capture_cards


def _frame_diff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    return float(np.mean(cv2.absdiff(a, b)))


def auto_pair(model_name, devices_dir="devices"):
    model = load_model(model_name)
    esp32s = enumerate_esp32()
    cards = enumerate_capture_cards()

    if not esp32s:
        print("No ESP32 boards found."); return []
    if not cards:
        print("No capture cards found."); return []

    print("Wake & unlock all phones so their screens are mirroring.\n")

    # Open every capture card; keep only ones that actually show a phone.
    grabbers = {}
    for c in cards:
        try:
            cc = CaptureCard(c.video_dev)
        except RuntimeError as e:
            print(f"  ! cannot open {c.video_dev}: {e}"); continue
        if not cc.has_phone:
            print(f"  ! {c.video_dev}: no phone signal (screen off?) - skipping")
            cc.close(); continue
        grabbers[c.phys_key] = cc
        print(f"  opened {c.video_dev}  phys={c.phys_key}")

    if not grabbers:
        print("No capture card shows a phone. Wake the phones and retry.")
        return []

    baselines = {k: g.grab_gray() for k, g in grabbers.items()}
    x1, y1, x2, y2, ms = model.pair_swipe
    threshold = model.motion_threshold

    pairs, assigned = [], set()
    for esp in esp32s:
        print(f"\nProbing ESP32 {esp.serial} ...")
        ser = open_esp32_no_reset(esp.port)
        ser.reset_input_buffer()
        if not handshake(ser):
            print(f"  ! no READY, skipping"); ser.close(); continue
        sync_res(ser, model.capture_w, model.capture_h)

        # Fire the swipe, then sample every card while it animates.
        ser.write(f"SWIPE {x1} {y1} {x2} {y2} {ms}\n".encode())
        max_diff = {k: 0.0 for k in grabbers}
        sample_until = time.time() + (ms / 1000.0) + 0.4
        while time.time() < sample_until:
            for k, g in grabbers.items():
                d = _frame_diff(baselines[k], g.grab_gray())
                if d > max_diff[k]:
                    max_diff[k] = d
            time.sleep(0.015)
        drain_until_done(ser)
        ser.close()

        best_key, best_val = None, threshold
        for k, v in max_diff.items():
            if k in assigned:
                continue
            print(f"    motion on {k}: {v:.2f}")
            if v > best_val:
                best_val, best_key = v, k

        if best_key is None:
            print(f"  ! no card showed motion above threshold {threshold}")
            continue
        assigned.add(best_key)
        pairs.append((esp.serial, best_key))
        baselines[best_key] = grabbers[best_key].grab_gray()
        print(f"  paired  {esp.serial}  ->  {best_key}")

    for g in grabbers.values():
        g.close()

    for i, (serial, key) in enumerate(pairs):
        slot = SlotConfig(slot=f"rig-{i}", model=model_name,
                          esp32_serial=serial, capture_port=key)
        write_slot(slot, devices_dir)
        print(f"wrote {devices_dir}/rig-{i}.yaml")

    return pairs