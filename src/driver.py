"""Low-level drivers: reset-free ESP32 serial + HDMI capture card."""
from __future__ import annotations
import time
import serial
import cv2
import numpy as np


def open_esp32_no_reset(port, baud=115200, timeout=1):
    """Open the ESP32 serial port without triggering auto-reset.
    De-assert RTS first, then DTR, so the line sequence never hits the
    EN-reset state."""
    ser = serial.Serial(port, baud, timeout=timeout)
    ser.rts = False
    ser.dtr = False
    return ser


def is_color_bars(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    if float(np.mean(sat > 150)) < 0.35:
        return False
    small = cv2.resize(frame, (64, 36)).astype(np.float32)
    return small.var(axis=0).mean() < 500


class CaptureCard:
    """Opens a capture card, finds the phone's active area, yields cropped frames."""

    def __init__(self, video_dev, settle_s=1.5):
        self.video_dev = video_dev
        self.cap = cv2.VideoCapture(video_dev, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open {video_dev}")
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        time.sleep(settle_s)
        for _ in range(12):
            self.cap.read()
        self.area = self._find_active_area()

    def _find_active_area(self):
        for _ in range(20):
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.2); continue
            if is_color_bars(frame):
                time.sleep(0.4); continue
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            H, W = g.shape
            corners = [g[:40, :40], g[:40, -40:], g[-40:, :40], g[-40:, -40:]]
            bg = min(int(np.median(c)) for c in corners)
            thr = bg + 25
            cols = np.where(g.mean(axis=0) > thr)[0]
            if len(cols) == 0 or len(cols) > 0.6 * W:
                time.sleep(0.3); continue
            x0, x1 = cols[0], cols[-1]
            rows = np.where(g[:, x0:x1 + 1].mean(axis=1) > thr)[0]
            if len(rows) == 0:
                time.sleep(0.3); continue
            return (x0, rows[0], x1, rows[-1])
        return None                       # no phone signal (off or missing)

    @property
    def has_phone(self):
        return self.area is not None

    def grab_gray(self):
        if not self.has_phone:
            return None
        ret, f = self.cap.read()
        if not ret:
            return None
        x0, y0, x1, y1 = self.area
        return cv2.cvtColor(f[y0:y1 + 1, x0:x1 + 1], cv2.COLOR_BGR2GRAY)

    def grab_color(self):
        if not self.has_phone:
            return None
        ret, f = self.cap.read()
        if not ret:
            return None
        x0, y0, x1, y1 = self.area
        return f[y0:y1 + 1, x0:x1 + 1]

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None


# ---- serial helpers ----
def handshake(ser, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ser.write(b"PING\n")
        time.sleep(0.4)
        while ser.in_waiting:
            if ser.readline().decode('utf-8', errors='ignore').strip() == "READY":
                return True
    return False


def sync_res(ser, w, h, timeout=5):
    ser.write(f"RES {w} {h}\n".encode())
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            if ser.readline().decode('utf-8', errors='ignore').strip() == "OK":
                return True
        time.sleep(0.03)
    return False


def drain_until_done(ser, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line == "DONE":
                return True
            if line.startswith("ERR"):
                return False
        time.sleep(0.02)
    return False