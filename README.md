```markdown
# HIL-Rig

**Closed-loop Hardware-in-the-Loop testing for Android devices — no ADB, no root, no app instrumentation.**

HIL-Rig drives an Android phone exactly like a human would and watches the result. An
**ESP32-S3** emulates a native USB multi-touch screen to tap and swipe, while an **HDMI
capture card** streams the phone's display back to the host so tests can visually verify
what happened. Everything is orchestrated by `pytest` on the host PC.

```
┌────────────────────────────────────────────────────────────────┐
│  HOST PC (pytest)                                              │
│    send gestures ──────────────────────► assert on screen      │
└───────────────┬────────────────────────────────────▲───────────┘
                │ USB-Serial (commands)              │ USB Video (UVC)
                ▼                                    │
         ┌────────────┐                       ┌──────────────┐
         │  ESP32-S3  │                       │ HDMI capture │
         └─────┬──────┘                       └──────▲───────┘
       USB HID │ touch/swipe                         │ HDMI
               ▼                                     │
         ┌───────────────────────────────────────────┴───┐
         │               ANDROID PHONE                   │
         └───────────────────────────────────────────────┘
```

Because the phone only ever sees a standard USB touch screen and a standard HDMI output,
this works on **any** Android device with zero software changes, and it can test
third-party apps that you cannot instrument.

---

## Features

- **True multi-touch HID** — ESP32-S3 presents itself as a USB HID touch digitizer
  (taps, swipes, multi-finger gestures), not a mouse or ADB shell.
- **No ADB / no root** — pure hardware emulation; the phone is unaware it is being tested.
- **Closed-loop vision** — HDMI capture + OpenCV template matching and element finding
  to verify the screen state after each gesture.
- **Multi-device topology discovery** — automatically maps ESP32 boards and capture
  cards to specific phones using stable `/dev/.../by-id` and `by-path` identifiers.
- **Reset-free serial** — opens the ESP32 serial port without triggering the board's
  auto-reset circuit, keeping the USB HID connection alive across the whole session.
- **pytest-native** — tests are plain Python functions with automatic setup, teardown,
  and diagnostic screenshots on failure.

---

## Hardware

| Component | Role | Notes |
|-----------|------|-------|
| ESP32-S3 (N16R8) | USB HID touch device | Native USB port → phone; UART/serial → host |
| Android phone | Device under test | Must output its screen over HDMI |
| HDMI capture card | Screen feedback | UVC class (e.g. MACROSILICON MS21xx) |
| USB-C → HDMI adapter | Phone → capture card | Phone must support video-out |
| Powered USB hub | Connects everything | Recommended for stability with multiple devices |

> **Wiring rule:** each capture card must stay in the **same physical USB port**. The
> rig identifies capture cards by physical port path (`by-path`), not by name.

---

## Repository layout

```
hil-rig/
├── firmware/
│   └── hil_touch/          # ESP32-S3 sketch (USB HID multitouch + serial protocol)
├── src/
│   ├── discovery/          # hardware topology discovery (ESP32 + capture cards)
│   ├── driver.py           # low-level ESP32 serial + HDMI capture drivers
│   ├── device.py           # per-device config model
│   ├── rig.py              # high-level control API (tap/swipe/go_home/capture)
│   ├── vision.py           # template matching + element finding
│   └── exceptions.py
├── tests/
│   ├── conftest.py         # pytest fixtures (multi-device)
│   └── test_*.py
├── devices/                # per-phone YAML config
├── assets/templates/       # reference images for vision checks
├── reports/                # generated artifacts (gitignored)
└── docs/
    └── protocol.md         # ESP32 <-> host serial protocol
```

---

## Installation

### 1. Host dependencies

```bash
cd hil-rig
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

System packages (Ubuntu/Debian):

```bash
sudo apt install python3-venv v4l-utils
```

### 2. ESP32 firmware

Open `firmware/hil_touch/hil_touch.ino` in the Arduino IDE (or flash with your preferred
toolchain) and upload it to the ESP32-S3. The board's **native USB port** connects to the
phone; its **serial port** connects to the host.

---

## Device configuration

Each phone gets a YAML file in `devices/`:

```yaml
# devices/pixel6.yaml
name: pixel6

# Hardware identity (used by discovery)
esp32_serial: "5C63002523"                        # from /dev/serial/by-id
capture_port: "pci-0000:0a:00.0-usb-0:1.4:1.0"    # physical USB port of the capture card

# Screen geometry (as measured by the capture card)
screen:
  width: 1080
  height: 2400
  capture_w: 471
  capture_h: 960

home_coord: [540, 2280]    # the on-screen home button
```

### Discovering hardware

List what the rig currently sees and verify your config matches:

```bash
python -m src.discovery.cli            # human-readable
python -m src.discovery.cli --json     # machine-readable
```

Use these to find the stable identifiers for a new device:

```bash
ls -l /dev/serial/by-id/    # ESP32 serial -> esp32_serial
ls -l /dev/v4l/by-path/     # capture card physical port -> capture_port
```

---

## Usage

### Run the test suite

```bash
pytest -v
```

Run tests for a single device:

```bash
HIL_DEVICE=pixel6 pytest -v
```

### Writing a test

```python
def test_open_settings(rig):
    rig.go_home()
    rig.tap_at(540, 1200)
    assert rig.wait_for_template("assets/templates/settings_screen.png")
```

The `rig` fixture connects to the device, runs the test, and on failure saves a
diagnostic screenshot to `reports/`.

---

## Serial protocol (host <-> ESP32)

One text line per message, terminated by `\n`.

| Direction | Message | Description |
|-----------|---------|-------------|
| host → esp32 | `PING` | Are you alive? |
| esp32 → host | `READY` | Yes, ready for commands |
| host → esp32 | `RES <w> <h>` | Set logical screen size |
| esp32 → host | `OK` | Acknowledged |
| host → esp32 | `TAP <x> <y>` | Tap at (x, y) |
| host → esp32 | `SWIPE <x1> <y1> <x2> <y2> <ms>` | Swipe between points |
| esp32 → host | `DONE` | Last command finished |
| esp32 → host | `ERR <reason>` | Something went wrong |

Coordinates are in **capture active-area space** (origin = top-left of the phone screen
inside the capture frame), mapped linearly onto the HID digitizer range (0–32767).

---

## Design notes

### Why `/dev/.../by-path` for capture cards?
Identical capture cards report the same `by-id` name, so `by-id` collides when you have
more than one. `by-path` encodes the physical USB route (PCI controller → hub → port),
which is unique per socket and stable across reboots — provided each card stays in its
assigned port.

### Why the reset-free serial trick?
ESP32 dev boards have an auto-reset circuit driven by the USB-serial chip's DTR/RTS
lines. Opening the port normally pulses these lines and reboots the board, which drops
the USB HID connection to the phone. The driver de-asserts the lines in an order that
never pulls the EN pin low, so the board stays up. See `src/driver.py`.

### Coordinate spaces
1. **Capture frame** — full 1920x1080 (or similar) from the capture card.
2. **Active area** — the phone screen region inside the frame (auto-detected).
3. **HID range** — 0–32767 on each axis, sent to the phone's digitizer.

Tests use **active-area coordinates**; the firmware maps them to the HID range.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Capture shows color bars | No HDMI signal / phone screen off | Wake & unlock phone; check HDMI adapter |
| `CAPTURE_MISSING` in discovery | Card moved to a different USB port | Put it back in its assigned port; update `capture_port` |
| ESP32 reboots on connect | Serial port opened with reset | Ensure you're using `open_esp32_no_reset()` from `src/driver.py` |
| Touches land in the wrong place | Stale screen geometry | Re-measure the active area; update `capture_w`/`capture_h` |
| Template match fails | UI changed / wrong resolution | Re-grab the reference image at the current resolution |

---

## Roadmap

- [x] ESP32 USB HID multitouch firmware
- [x] Reset-free serial driver
- [x] HDMI capture + active-area detection
- [x] Closed-loop tap/swipe with proof screenshots
- [x] Multi-device topology discovery
- [ ] Vision API (template matching + element finding)
- [ ] pytest multi-device fixtures
- [ ] Go-home / known-state recovery
- [ ] HTML test reporting
```

A few notes so you can tailor it:

- **Serial number & paths** in the `devices/pixel6.yaml` example are placeholders from our earlier sessions — swap in your real `esp32_serial` and `capture_port`.
- The **Roadmap** reflects where we are: discovery is done, vision API + pytest fixtures are next.
- If you'd like, I can also write the companion **`docs/protocol.md`** (a fuller spec of the serial protocol) and a **`.gitignore`** to go with this. Just say the word.
