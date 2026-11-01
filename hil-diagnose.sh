#!/usr/bin/env bash
#
# ============================================================================
# hil-diagnose.sh
#
# Hardware diagnostic for the HIL rig.
#
# This script:
#   1. Automatically finds all HDMI capture-card video nodes.
#   2. Finds processes holding those nodes busy.
#   3. Kills those processes automatically, without interaction.
#   4. Verifies the capture devices are free.
#   5. Continues with full hardware diagnostics.
#
# Usage:
#   cd ~/Documents/work/hil-rig
#   bash hil-diagnose.sh
#
# WARNING:
#   This script will automatically kill processes that are using HDMI
#   capture-card video devices, for example ffplay, ffmpeg, OBS, VLC,
#   guvcview, browser camera previews, etc.
# ============================================================================

# Do not use set -e. We want the diagnostic to continue even if one step fails.

# ----------------------------------------------------------------------------
# Run from the directory containing this script.
# The Python checks import src.*, so we must be in the project root.
# ----------------------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

# ----------------------------------------------------------------------------
# Make src.* imports work.
# ${PYTHONPATH:+...} avoids a trailing ':' when PYTHONPATH is unset.
# ----------------------------------------------------------------------------
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"

# Unmatched globs expand to nothing instead of a literal pattern.
shopt -s nullglob

# ----------------------------------------------------------------------------
# Prefer the project virtualenv Python if it exists.
# ----------------------------------------------------------------------------
PYTHON="python3"
if   [ -x ".venv/bin/python" ]; then PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python"  ]; then PYTHON="venv/bin/python"
fi

# ----------------------------------------------------------------------------
# We need either fuser or lsof to find which process holds /dev/videoX.
# ----------------------------------------------------------------------------
FUSER="$(command -v fuser || true)"
LSOF="$(command -v lsof || true)"

if [ -z "$FUSER" ] && [ -z "$LSOF" ]; then
    echo "ERROR: Neither fuser nor lsof is installed."
    echo "Install one of them, for example:"
    echo "  sudo apt install psmisc   # provides fuser"
    echo "  sudo apt install lsof     # provides lsof"
    exit 1
fi

# ----------------------------------------------------------------------------
# Helper: print a section header.
# ----------------------------------------------------------------------------
section() {
    echo
    echo "=============================================================================="
    echo "  $1"
    echo "=============================================================================="
}

# ----------------------------------------------------------------------------
# Helper: print PIDs holding a given /dev/videoX device.
# Uses fuser if available, otherwise lsof.
# ----------------------------------------------------------------------------
get_holder_pids() {
    local dev="$1"

    if [ -n "$FUSER" ]; then
        # fuser may print a device prefix like:
        #   /dev/video2: 1234 5678
        # Strip everything before the first colon, then extract leading PIDs.
        fuser "$dev" 2>/dev/null \
            | sed 's/^[^:]*://' \
            | tr ' \t' '\n' \
            | sed -n 's/^\([0-9][0-9]*\).*/\1/p' \
            | sort -u
    elif [ -n "$LSOF" ]; then
        lsof -t "$dev" 2>/dev/null \
            | sed -n 's/^\([0-9][0-9]*\).*/\1/p' \
            | sort -u
    fi
}

echo "HIL rig diagnostic - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Project dir : $(pwd)"
echo "Python used : $PYTHON"

# ============================================================================
section "1/6  Automatic capture-card cleanup - find and kill busy processes"
# ----------------------------------------------------------------------------
# This uses the project's own discovery code to find real capture-card video
# nodes only. It skips:
#   - laptop webcam
#   - metadata nodes
#   - non-capture V4L nodes
# ============================================================================

CAPTURE_DEVS=()

# Ask Python for the list of capture-card video devices.
while IFS= read -r line; do
    [[ -n "$line" ]] && CAPTURE_DEVS+=("$line")
done < <("$PYTHON" - <<'PY'
from src.discovery.enumerate import enumerate_capture_cards

for c in enumerate_capture_cards():
    print(c.video_dev)
PY
)

if (( ${#CAPTURE_DEVS[@]} == 0 )); then
    echo "No capture-card video nodes detected. Skipping cleanup."
else
    echo "Detected capture-card video nodes:"
    printf '  %s\n' "${CAPTURE_DEVS[@]}"

    ALL_PIDS=()

    echo
    echo "Checking for processes holding these devices busy..."

    for dev in "${CAPTURE_DEVS[@]}"; do
        echo
        echo "--- $dev ---"

        mapfile -t PIDS < <(get_holder_pids "$dev")

        if (( ${#PIDS[@]} == 0 )); then
            echo "  free"
            continue
        fi

        echo "  busy; held by:"

        for pid in "${PIDS[@]}"; do
            # Never kill this script, its parent, or PID 1.
            if [ "$pid" = "$$" ] || [ "$pid" = "$PPID" ] || [ "$pid" -le 1 ]; then
                echo "    PID $pid skipped"
                continue
            fi

            ps -p "$pid" -o pid=,ppid=,user=,comm=,args= 2>/dev/null \
                | sed 's/^/    /'

            ALL_PIDS+=("$pid")
        done
    done

    if (( ${#ALL_PIDS[@]} > 0 )); then
        # Deduplicate PID list.
        mapfile -t ALL_PIDS < <(printf '%s\n' "${ALL_PIDS[@]}" | sort -u)

        echo
        echo "Killing holder processes automatically..."

        for pid in "${ALL_PIDS[@]}"; do
            if kill -TERM "$pid" 2>/dev/null; then
                echo "  SIGTERM -> PID $pid"
            else
                echo "  SIGTERM failed -> PID $pid"
            fi
        done

        # Give processes a short chance to exit cleanly.
        sleep 2

        # Find PIDs that are still alive.
        REMAINING=()
        for pid in "${ALL_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                REMAINING+=("$pid")
            fi
        done

        if (( ${#REMAINING[@]} > 0 )); then
            echo
            echo "Some processes did not exit. Sending SIGKILL..."

            for pid in "${REMAINING[@]}"; do
                if kill -KILL "$pid" 2>/dev/null; then
                    echo "  SIGKILL -> PID $pid"
                else
                    echo "  SIGKILL failed -> PID $pid"
                fi
            done

            sleep 1
        fi
    else
        echo
        echo "No busy holder processes found."
    fi

    echo
    echo "Verifying capture devices are free..."

    BUSY_LEFT=0

    for dev in "${CAPTURE_DEVS[@]}"; do
        mapfile -t PIDS < <(get_holder_pids "$dev")

        if (( ${#PIDS[@]} == 0 )); then
            echo "  $dev: free"
        else
            echo "  $dev: STILL BUSY"
            BUSY_LEFT=1

            for pid in "${PIDS[@]}"; do
                ps -p "$pid" -o pid=,ppid=,user=,comm=,args= 2>/dev/null \
                    | sed 's/^/    /'
            done
        fi
    done

    if (( BUSY_LEFT == 0 )); then
        echo
        echo "All capture-card devices are now free."
    else
        echo
        echo "Some capture-card devices are still busy."
        echo "If the holder belongs to another user, you may need to run with sudo."
    fi
fi

# ============================================================================
section "2/6  ESP32 boards (serial + port)"
# ----------------------------------------------------------------------------
# Each ESP32 has a unique serial number in its USB-serial chip.
# Vendor id '1a86' is QinHeng.
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
section "3/6  Capture cards (physical USB port -> video node)"
# ----------------------------------------------------------------------------
# /dev/v4l/by-path names each device by the physical USB port it sits in.
# This stays stable even if the kernel renumbers /dev/videoN.
# We skip duplicate 'usbv2' symlinks.
# ============================================================================

cards=()

for f in /dev/v4l/by-path/*; do
    [[ "$f" == *usbv2* ]] && continue
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
section "4/6  All video devices (v4l2-ctl)"
# ----------------------------------------------------------------------------
# Kernel view of all V4L devices.
# Ignore the laptop webcam. The rig cards are the MACROSILICON / USB Video ones.
# ============================================================================

if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices
else
    echo "  (v4l2-ctl not installed - run: sudo apt install v4l-utils)"
fi

# ============================================================================
section "5/6  USB overview (lsusb)"
# ----------------------------------------------------------------------------
# Confirms the USB bus enumerates ESP32s and capture cards.
# ============================================================================

lsusb

# ============================================================================
section "6/6  Signal health - is each phone mirroring?"
# ----------------------------------------------------------------------------
# Now that busy holders have been killed, open each capture card with the
# rig's own driver code and check whether a live phone image is visible.
# ============================================================================

"$PYTHON" - <<'PY'
import subprocess
from src.discovery.enumerate import enumerate_capture_cards
from src.driver import CaptureCard


def is_busy(dev):
    """True if another process currently holds this video device."""
    try:
        r = subprocess.run(["fuser", dev], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


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

            cc.close()

        except Exception as e:
            msg = str(e)

            # OpenCV often reports a busy card as "Cannot open ..." without
            # the word busy, so also confirm with fuser.
            if "busy" in msg.lower() or is_busy(c.video_dev):
                status = (
                    f"BUSY (another process holds this device - "
                    f"check: fuser -v {c.video_dev})"
                )
            else:
                status = f"ERROR: {msg}"

        print(f"  {c.video_dev:<14} phys={c.phys_key}   {status}")

    print()
    print(f"  -> {ok}/{len(cards)} capture card(s) have a live phone signal")
PY

# ============================================================================
section "Done"
# ----------------------------------------------------------------------------
# A healthy rig shows:
#   - one ESP32 line per board, each with a unique serial
#   - one capture-card line per card, each at a unique physical port
#   - capture devices free after cleanup
#   - SIGNAL OK for every phone that is awake and mirroring
# ============================================================================

echo "Diagnostic complete."