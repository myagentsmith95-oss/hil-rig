#!/usr/bin/env bash
#
# ============================================================================
#  hil-diagnose.sh
#
#  Hardware diagnostic for the HIL rig.
#  Shows which devices are physically PRESENT and HEALTHY right now.
#
#  Usage:
#      cd ~/Documents/work/hil-rig
#      bash hil-diagnose.sh
#
#  What it checks:
#      1. ESP32 boards     - plugged in? (unique serial numbers)
#      2. Capture cards    - plugged in? (stable physical USB ports)
#      3. V4L device list  - the kernel's view of all video devices
#      4. USB overview     - what the USB bus enumerates
#      5. Signal health    - is each phone actually mirroring video?
# ============================================================================

# No 'set -e': if one check fails we still run the rest, so you get the full
# picture in a single run.

# --- Run from the project root (the Python checks import 'src.*') -----------
cd "$(dirname "$0")" || exit 1

# Prepend the project dir to PYTHONPATH so 'src' is importable.
# ${PYTHONPATH:+...} only appends ":<old>" when PYTHONPATH is already set and
# non-empty, so we never produce a trailing ':' (an empty entry means cwd).
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"

# Unmatched globs expand to nothing instead of a literal pattern string.
shopt -s nullglob

# --- Pick a Python interpreter (prefer the project's virtualenv) -----------
# Using .venv/bin/python directly gives us cv2/numpy without 'source activate'.
PYTHON="python3"
if   [ -x ".venv/bin/python" ]; then PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python"  ]; then PYTHON="venv/bin/python"
fi

# --- Helper: print a clear section header ----------------------------------
section() {
    echo
    echo "=============================================================================="
    echo "  $1"
    echo "=============================================================================="
}

echo "HIL rig diagnostic - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Project dir : $(pwd)"
echo "Python used : $PYTHON"

# ============================================================================
section "1/5  ESP32 boards (serial + port)"
# ----------------------------------------------------------------------------
# Each ESP32 has a unique serial number in its USB-serial chip (vendor '1a86'
# = QinHeng). We match with a glob instead of parsing 'ls' output.
# ============================================================================
esp32s=(/dev/serial/by-id/*1a86*)
if (( ${#esp32s[@]} )); then
    for f in "${esp32s[@]}"; do
        printf '  %s -> %s\n' "$(basename "$f")" "$(basename "$(readlink "$f")")"
    done
    echo
    echo "  -> ${#esp32s[@]} ESP32 board(s) found"
else
    echo "  (no ESP32 boards found)"
fi

# ============================================================================
section "2/5  Capture cards (physical USB port -> video node)"
# ----------------------------------------------------------------------------
# '/dev/v4l/by-path' names each device by the PHYSICAL USB port it sits in,
# which stays stable even when the kernel renumbers /dev/videoN. We skip the
# duplicate 'usbv2' symlinks. (The built-in webcam also appears here - ignore
# it; the rig's capture cards are the MACROSILICON / 'USB Video' ones.)
# ============================================================================
cards=()
for f in /dev/v4l/by-path/*; do
    [[ "$f" == *usbv2* ]] && continue        # skip the duplicated usbv2 links
    cards+=("$f")
done
if (( ${#cards[@]} )); then
    for f in "${cards[@]}"; do
        printf '  %s -> %s\n' "$(basename "$f")" "$(basename "$(readlink "$f")")"
    done
else
    echo "  (no V4L by-path devices found)"
fi

# ============================================================================
section "3/5  All video devices (v4l2-ctl)"
# ----------------------------------------------------------------------------
# The kernel's full list of video devices and their nodes, grouped by device.
# Useful to cross-check the capture cards and see their /dev/videoN nodes.
# ============================================================================
if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices
else
    echo "  (v4l2-ctl not installed - run: sudo apt install v4l-utils)"
fi

# ============================================================================
section "4/5  USB overview (lsusb)"
# ----------------------------------------------------------------------------
# Confirms the USB bus itself enumerates the ESP32s (1a86) and capture cards.
# If a device is missing here, it's a cable/port/power problem, not software.
# ============================================================================
lsusb

# ============================================================================
section "5/5  Signal health - is each phone mirroring?"
# ----------------------------------------------------------------------------
# A capture card can be PRESENT but still show NO SIGNAL if its phone is
# asleep or its HDMI cable is loose. This opens each capture card using the
# rig's own driver code and reports whether it sees a live phone image.
# (Takes a few seconds per card while it waits for the picture to lock.)
# ============================================================================
"$PYTHON" - <<'PY'
from src.discovery.enumerate import enumerate_capture_cards
from src.driver import CaptureCard

cards = enumerate_capture_cards()
if not cards:
    print("  (no capture cards detected)")
else:
    ok = 0
    for c in cards:
        try:
            cc = CaptureCard(c.video_dev)
            if cc.has_phone:
                status = "SIGNAL OK   (phone is mirroring)"
                ok += 1
            else:
                status = "NO SIGNAL   (phone asleep / HDMI loose)"
            print(f"  {c.video_dev:<14} phys={c.phys_key}   {status}")
            cc.close()
        except Exception as e:
            print(f"  {c.video_dev:<14} phys={c.phys_key}   ERROR: {e}")
    print()
    print(f"  -> {ok}/{len(cards)} capture card(s) have a live phone signal")
PY

# ============================================================================
section "Done"
# ----------------------------------------------------------------------------
# Paste everything above back into the chat. A healthy rig shows:
#   - one ESP32 line per board, each with a unique serial
#   - one capture-card line per card, each at a unique physical port
#   - 'SIGNAL OK' for every phone that is awake and mirroring
# ============================================================================
echo "Diagnostic complete."