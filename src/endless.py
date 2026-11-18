"""Endless supervisor for run_loop.py.

Runs the unattended Gold Rush loop forever:
  * every run gets its own timestamped log in Memory/derived/endless_*.log
  * if run_loop crashes, hangs (watchdog kills it) or halts on a failure,
    stale adb clients are cleared and it is restarted a few seconds later
  * a normal finish (board cap reached) immediately starts a fresh run

Usage:
  python src/endless.py                # 500 boards per run, forever
  python src/endless.py --max 50       # smaller batches, still forever
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = r"C:\Users\Usernom\Documents\Terramine"
LOG_DIR = os.path.join(ROOT, "Memory", "derived")
ADB = r"C:\adb\adb.exe"
SERIAL = "R5CT63BQTTH"


def say(msg):
    print(f"[supervisor {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def kill_adb():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "adb.exe"],
                       capture_output=True, timeout=30)
    except Exception:
        pass


def wake():
    try:
        subprocess.run([ADB, "-s", SERIAL, "shell", "svc", "power", "stayon", "true"],
                       capture_output=True, timeout=30)
        subprocess.run([ADB, "-s", SERIAL, "shell", "input", "keyevent",
                        "KEYCODE_WAKEUP"], capture_output=True, timeout=30)
    except Exception:
        pass


def main():
    max_boards = 500
    if "--max" in sys.argv:
        max_boards = int(sys.argv[sys.argv.index("--max") + 1])

    os.makedirs(LOG_DIR, exist_ok=True)
    run = 0
    quick_failures = 0

    while True:
        run += 1
        log_path = os.path.join(
            LOG_DIR, f"endless_{time.strftime('%Y%m%d_%H%M%S')}_{run:03d}.log")
        say(f"starting run {run} -> {os.path.basename(log_path)}")
        t0 = time.time()
        args = [sys.executable, "-u", os.path.join(ROOT, "src", "run_loop.py"),
                "--max", str(max_boards), "--log", log_path]
        # Forward optional loop flags so the supervisor keeps the same behaviour
        # as a manual run (e.g. --wait 2 parks on a dead board instead of halting).
        for flag in ("--wait", "--mistakes"):
            if flag in sys.argv:
                args += [flag, sys.argv[sys.argv.index(flag) + 1]]
        if "--dry-run" in sys.argv:
            args.append("--dry-run")
        rc = subprocess.run(args).returncode
        dur = time.time() - t0

        if rc == 0:
            say(f"run {run} finished normally after {dur / 60:.1f} min")
            quick_failures = 0
            time.sleep(3)
            continue

        quick_failures = quick_failures + 1 if dur < 90 else 0
        say(f"run {run} exited rc={rc} after {dur:.0f}s "
            f"(quick failures: {quick_failures})")
        kill_adb()
        time.sleep(5)
        wake()
        if quick_failures >= 3:
            say("repeated quick failures -> backing off 60s")
            time.sleep(60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
