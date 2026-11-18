"""Thin ADB wrapper for the TerraMine Gold Rush loop.

No LLM, no MCP, no external service: only adb + local Python.
"""
from __future__ import annotations

import os
import subprocess
import time
import xml.etree.ElementTree as ET

ADB = r"C:\adb\adb.exe"
SERIAL = "R5CT63BQTTH"
PACKAGE = "com.terramine.app"
SCREEN = (1080, 2340)

ROOT = r"C:\Users\Usernom\Documents\Terramine"
DEVICE_DIR = os.path.join(ROOT, "Memory", "derived", "device")
DEBUG_DIR = os.path.join(ROOT, "Memory", "derived", "debug")

os.makedirs(DEVICE_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)


class AdbError(RuntimeError):
    pass


def adb(*args, binary=False, timeout=45):
    cmd = [ADB, "-s", SERIAL, *args]
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "ignore").strip()
        raise AdbError(f"adb {' '.join(args)} failed rc={p.returncode}: {err}")
    return p.stdout if binary else p.stdout.decode("utf-8", "ignore")


def _adb_recover():
    """Re-establish the ADB connection after the device vanishes.

    `device 'R5CT63BQTTH' not found` means adb cannot see the phone at all
    (cable/unlock/reboot). Retrying the same command only fails again, so we
    restart the adb server and wait for the device to reappear.
    """
    try:
        subprocess.run([ADB, "kill-server"], capture_output=True, timeout=10)
    except Exception:
        pass
    try:
        subprocess.run([ADB, "start-server"], capture_output=True, timeout=15)
    except Exception:
        pass
    for _ in range(6):
        try:
            out = subprocess.run([ADB, "-s", SERIAL, "wait-for-device"],
                                 capture_output=True, timeout=15)
            if out.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def screenshot(path=None, retries=4):
    """Capture a screenshot, guarding against blank/truncated frames.

    A transient black frame is common right after an ad closes or the display
    wakes: `screencap -p` can return a truncated PNG or an all-black buffer.
    Those must not kill the run loop (run 012 lost a live 40 s board this way),
    so we retry with a growing backoff and only raise after the last attempt.

    A vanished device (`device not found`) is handled the same way: restart the
    adb server, wait for the phone, and retry, instead of crashing the loop
    (run 017 died this way at board 18).
    """
    from PIL import Image
    import numpy as np

    path = path or os.path.join(DEVICE_DIR, "current_screen.png")
    recovered = False
    for attempt in range(retries + 1):
        try:
            raw = adb("exec-out", "screencap", "-p", binary=True, timeout=30)
            if not raw:
                raise ValueError("empty capture")
            with open(path, "wb") as f:
                f.write(raw)
            im = Image.open(path)
            im.load()
            if im.size != SCREEN:
                raise ValueError(f"bad size {im.size}")
            arr = np.asarray(im.convert("RGB")).astype("float32")
            if arr.mean() < 5:
                raise ValueError("black frame")
            return path
        except AdbError as exc:
            if "not found" in str(exc) and not recovered:
                recovered = True
                _adb_recover()
                time.sleep(3)
                continue
            if attempt >= retries:
                raise
            time.sleep(0.8 * (attempt + 1))
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(0.8 * (attempt + 1))
    return path


def tap(x, y):
    adb("shell", "input", "tap", str(int(x)), str(int(y)))


def taps(points, delay=0.13):
    """Fire a sequence of taps; one adb call per point (input tap has no batch mode)."""
    for (x, y, *_) in points:
        adb("shell", "input", "tap", str(int(x)), str(int(y)))
        if delay:
            time.sleep(delay)


def swipe(x1, y1, x2, y2, ms=200):
    adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms))


def dump_ui(path=None, retries=5, budget=14):
    """Dump the UI hierarchy with a hard time budget, returning (xml_text, path).

    uiautomator refuses to dump while the screen animates (it waits for an idle
    state and can hang). We delete the remote file first so a failure can never
    return the previous dump, and we stop after `budget` seconds instead of
    stalling the game clock.
    """
    path = path or os.path.join(DEBUG_DIR, "ui_current.xml")
    text = ""
    deadline = time.time() + budget
    while time.time() < deadline:
        try:
            adb("shell", "rm", "-f", "/sdcard/ui_dump.xml", timeout=6)
            adb("shell", "uiautomator", "dump", "/sdcard/ui_dump.xml",
                timeout=10)
        except (AdbError, subprocess.TimeoutExpired):
            time.sleep(0.6)
            continue
        try:
            raw = adb("exec-out", "cat", "/sdcard/ui_dump.xml",
                      binary=True, timeout=10)
        except (AdbError, subprocess.TimeoutExpired):
            time.sleep(0.6)
            continue
        text = raw.decode("utf-8", "ignore")
        if "<hierarchy" in text and len(text) > 200:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return text, path
        time.sleep(0.6)
    return text, path


def launch():
    adb("shell", "monkey", "-p", PACKAGE, "-c",
        "android.intent.category.LAUNCHER", "1", timeout=30)


def ensure_awake():
    """Keep the screen on and clear a lock screen before an unattended run."""
    try:
        adb("shell", "svc", "power", "stayon", "true", timeout=15)
        adb("shell", "settings", "put", "system", "screen_off_timeout",
            "2147483647", timeout=15)
    except AdbError:
        pass
    try:
        out = adb("shell", "dumpsys", "power", timeout=20)
        if "mWakefulness=Awake" not in out:
            adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
            time.sleep(0.8)
            adb("shell", "input", "swipe", "540", "1900", "540", "800", "250")
            time.sleep(1.2)
            return True
    except AdbError:
        pass
    return False


def recover_display():
    """Clear a stuck dim/lock overlay by bouncing the app to the foreground."""
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(1.5)
    launch()
    time.sleep(3.0)


def snapshot_pair(path=None):
    """Screenshot + UI dump concurrently (two adb clients); saves ~1.5 s/iteration."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_img = ex.submit(screenshot, path)
        f_xml = ex.submit(dump_ui)
        return f_img.result(), f_xml.result()


def tap_batch(points, delay=0.12):
    """All taps in one adb shell call, paced so the game never drops an event.

    Taps fired back-to-back can be discarded by the game's touch handler, which
    is how the final tile of a plan gets 'missed'. A short sleep between taps
    (default 120 ms) keeps the whole batch fast but reliable.
    """
    cmds = [f"input tap {int(x)} {int(y)}" for (x, y, *_) in points]
    if not cmds:
        return
    parts = []
    for c in cmds:
        parts.append(c)
        parts.append(f"sleep {delay}")
    for i in range(0, len(parts), 60):
        adb("shell", "; ".join(parts[i:i + 60]), timeout=120)


def parse_nodes(xml_text):
    """Return list of dicts for every node with useful attributes."""
    nodes = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return nodes
    for n in root.iter("node"):
        bounds = n.get("bounds") or ""
        nodes.append({
            "text": n.get("text") or "",
            "desc": n.get("content-desc") or "",
            "cls": n.get("class") or "",
            "rid": n.get("resource-id") or "",
            "clickable": n.get("clickable") == "true",
            "enabled": n.get("enabled") == "true",
            "bounds": bounds,
            "rect": parse_bounds(bounds),
        })
    return nodes


def parse_bounds(bounds):
    """'[x1,y1][x2,y2]' -> (x1, y1, x2, y2) or None."""
    if not bounds:
        return None
    try:
        a, b = bounds.strip().split("][")
        x1, y1 = [int(v) for v in a.strip("[").split(",")]
        x2, y2 = [int(v) for v in b.strip("]").split(",")]
        return (x1, y1, x2, y2)
    except Exception:
        return None


def center(rect):
    x1, y1, x2, y2 = rect
    return ((x1 + x2) // 2, (y1 + y2) // 2)


if __name__ == "__main__":
    print(screenshot())
    xml, p = dump_ui()
    print("ui nodes:", len(parse_nodes(xml)), p)
