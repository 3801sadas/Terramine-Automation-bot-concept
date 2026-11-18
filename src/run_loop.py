"""Unattended Gold Rush loop. Pure adb + local solvers, no LLM in the path.

Usage:
  python src/run_loop.py                # run until halt/limit
  python src/run_loop.py --max 10       # stop after 10 boards
  python src/run_loop.py --dry-run      # classify + solve, never tap
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

import device
from ad_close_loop import (close_ad, looks_like_game, looks_like_result,
                           looks_like_levelup, looks_like_real_board,
                           clock_is_critical, low_clock)
from screen_state import classify, clean

ROOT = r"C:\Users\Usernom\Documents\Terramine"
SOLVER = os.path.join(ROOT, "src", "solve_from_image.py")
QUEUE_DIR = os.path.join(ROOT, "Memory", "derived", "queue")
RUN_LOG = os.path.join(ROOT, "Memory", "derived", "run_log.jsonl")
MAX_TAPS = 46
LOG_FILE = None
LAST_PROGRESS = [0.0]

os.makedirs(QUEUE_DIR, exist_ok=True)


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    if LOG_FILE is not None:
        try:
            LOG_FILE.write(line + "\n")
            LOG_FILE.flush()
        except Exception:
            pass


BOARDS_DIR = os.path.join(ROOT, "Memory", "derived", "boards")
WAIT_S = 0


def _clock_changed(p1, p2):
    """True when the header timer region differs between two frames."""
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(p1).convert("L")).astype(int)[140:245, 880:1060]
        b = np.asarray(Image.open(p2).convert("L")).astype(int)[140:245, 880:1060]
        return float(np.abs(a - b).mean()) >= 0.4
    except Exception:
        return False


def _shot_or_recover():
    """One screenshot, with display recovery on a transient failure.

    A blank `screencap` is common right after an ad closes or the display
    wakes; the caller must not die over it (run 012 lost a live 40 s board).
    Never raises: if the device is truly gone, return None so the caller can
    decide instead of crashing the whole loop (run 018 died this way).
    """
    try:
        return device.screenshot()
    except Exception:
        pass
    try:
        device.recover_display()
    except Exception:
        pass
    time.sleep(2)
    try:
        return device.screenshot()
    except Exception:
        return None


def wait_for_board(max_s):
    """Poll the screenshot (never tap) until a real, live board is visible.

    Used with `--wait` so the user can start a game at any time: on the
    Time's Up / menu screen we do nothing at all, we just watch.

    A candidate must also have a *running clock*: the Time's Up panel keeps the
    finished board on screen, and with a greyed CTA (`Loading ad...`) the visual
    result test used to miss it. A frozen timer is never playable (P006).
    """
    end = time.time() + max_s
    while time.time() < end:
        progress()
        img = _shot_or_recover()
        if too_dark(img):
            device.recover_display()
            img = _shot_or_recover()
        if (looks_like_real_board(img) and not looks_like_result(img)
                and not looks_like_levelup(img) and not clock_is_critical(img)):
            first = os.path.join(os.path.dirname(img), "wait_board_a.png")
            shutil.copy(img, first)
            time.sleep(2.2)
            img2 = _shot_or_recover()
            if (looks_like_real_board(img2) and not looks_like_result(img2)
                    and not looks_like_levelup(img2)
                    and not clock_is_critical(img2)
                    and _clock_changed(first, img2)):
                return img2
            log("  board-ish screen but the clock is frozen -> keep waiting")
            time.sleep(2)
            continue
        time.sleep(4)
    return None


def archive_board_image(img_path):
    """Copy a just-perceived board frame to a permanent per-board file.

    The live capture is a single overwritten PNG, so without this every board
    we never manage to label is lost. Returns the archived path (or the
    original if anything goes wrong).
    """
    try:
        os.makedirs(BOARDS_DIR, exist_ok=True)
        dst = os.path.join(
            BOARDS_DIR, time.strftime("%Y%m%d_%H%M%S_") +
            os.path.basename(img_path))
        shutil.copy(img_path, dst)
        return dst
    except Exception as exc:
        log(f"  (could not archive board image: {exc})")
        return img_path


def progress():
    LAST_PROGRESS[0] = time.time()

def start_watchdog(stall_s=240):
    """Hard-exit the process if a single step blocks for too long.

    adb/`uiautomator` can wedge on the device; without this the loop would sit
    there forever with the game clock dead. The supervisor restarts us.
    """
    def loop():
        while True:
            time.sleep(10)
            idle = time.time() - LAST_PROGRESS[0]
            if idle > stall_s:
                try:
                    print(f"WATCHDOG: no progress for {idle:.0f}s -> killing adb and exiting",
                          flush=True)
                    if LOG_FILE is not None:
                        LOG_FILE.write(f"WATCHDOG: no progress for {idle:.0f}s\n")
                        LOG_FILE.flush()
                except Exception:
                    pass
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "adb.exe"],
                                   capture_output=True, timeout=20)
                except Exception:
                    pass
                os._exit(3)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def solve_board(img_path, no_mistakes=False):
    args = [sys.executable, SOLVER, img_path, "--exclude"]
    if no_mistakes:
        args.append("--no-mistakes")
    p = subprocess.run(args, capture_output=True, text=True, timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0 or "TAPS_JSON=" not in out:
        return {"ok": False, "raw": out}
    lep = re.search(r"LEP=\((\d+),\s*(\d+)\)", out)
    pot = re.search(r"POT=\((\d+),\s*(\d+)\)", out)
    cost = re.search(r"COST (\d+)", out)
    total = re.search(r"TOTAL_TAPS=(\d+)", out)
    taps = re.search(r"TAPS_JSON=(\[.*?\])", out)
    return {
        "ok": True,
        "lep": [int(lep.group(1)), int(lep.group(2))] if lep else None,
        "pot": [int(pot.group(1)), int(pot.group(2))] if pot else None,
        "base_cost": int(cost.group(1)) if cost else None,
        "total": int(total.group(1)) if total else None,
        "taps": json.loads(taps.group(1)) if taps else [],
        "raw": out,
    }


def moves_left(nodes):
    for n in nodes:
        t = clean(n["text"])
        m = re.fullmatch(r"(\d+)\s+left", t)
        if m:
            return int(m.group(1))
    return None


def queue_failure(img, reason, extra=None):
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(QUEUE_DIR, f"{ts}_{reason}.png")
    try:
        device.adb("pull", img, dst, timeout=30)
    except Exception:
        import shutil
        shutil.copy2(img, dst)
    rec = {"ts": now(), "image": dst, "reason": reason, **(extra or {})}
    with open(os.path.join(QUEUE_DIR, "index.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return dst


def log_board(rec):
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def snapshot():
    img, (xml, _p) = device.snapshot_pair()
    nodes = device.parse_nodes(xml)
    if len(nodes) < 3:
        time.sleep(0.6)
        xml, _ = device.dump_ui()
        nodes = device.parse_nodes(xml)
    state, els = classify(xml)
    return img, state, els, nodes


def tap_element(els, name):
    el = els.get(name)
    if not el:
        return False
    device.tap(el["cx"], el["cy"])
    return True


def too_dark(img_path, threshold=55):
    """True when a stuck dim/lock overlay is darkening the whole screen."""
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("L"))
        return bool(a.mean() < threshold)
    except Exception:
        return False


def handle_ad_trigger(els, label):
    """Tap a rewarded-ad button, survive 'Ad Not Ready', then close the ad."""
    tap_element(els, "watch_ad")
    time.sleep(3)

    for _ in range(14):
        xml, _ = device.dump_ui()
        state, els2 = classify(xml)
        if state == "AD_NOT_READY":
            log("  [ad] not ready -> dismiss, wait 25s, retry once")
            tap_element(els2, "ok")
            time.sleep(25)
            # re-find the ad button (panel may have shifted)
            xml, _ = device.dump_ui()
            state, els2 = classify(xml)
            if not tap_element(els2, "watch_ad"):
                return {"triggered": False, "outcome": "no_button"}
            time.sleep(4)
            continue
        if state in ("AD_WEBVIEW", "AD_LOADING", "AD_STORE"):
            break
        time.sleep(1.5)

    res = close_ad(log=log, back_on_store=True)
    return {"triggered": True, **res}


def main():
    global LOG_FILE, WAIT_S
    max_boards = 200
    dry = "--dry-run" in sys.argv
    if "--wait" in sys.argv:
        WAIT_S = int(sys.argv[sys.argv.index("--wait") + 1]) * 60
    if "--max" in sys.argv:
        max_boards = int(sys.argv[sys.argv.index("--max") + 1])
    if "--log" in sys.argv:
        path = sys.argv[sys.argv.index("--log") + 1]
        LOG_FILE = open(path, "a", encoding="utf-8", buffering=1)

    progress()
    start_watchdog()
    log(f"run_loop start {now()} max_boards={max_boards} dry_run={dry}")
    device.ensure_awake()
    boards = 0
    wins = 0
    last_plan_sig = None
    last_img_sig = None
    iterations = 0
    stall_state = None
    stall_count = 0
    ad_triggers = 0

    while boards < max_boards and iterations < max(400, max_boards * 8):
        iterations += 1
        progress()
        t_iter = time.time()

        # Screenshot first. Board-only iterations never need uiautomator (which
        # can hang for 30 s+ while the game animates), so the hot path stays fast.
        try:
            img = device.screenshot()
        except Exception as exc:
            log(f"  screenshot failed repeatedly -> {exc}; recovering display")
            device.recover_display()
            time.sleep(2)
            try:
                img = device.screenshot()
            except Exception as exc2:
                log(f"  screenshot still failing -> halting: {exc2}")
                return 1
        if too_dark(img):
            log("  screen dim/locked -> recovering display")
            device.recover_display()
            img = device.screenshot()
        if looks_like_levelup(img):
            state, els, nodes = "LEVEL_UP", {}, []
        elif looks_like_result(img):
            state, els, nodes = "RESULT_PANEL", {}, []
        elif looks_like_real_board(img):
            state, els, nodes = "BOARD", {}, []
        else:
            state = None

        if state == "BOARD":
            log(f"[{iterations}] state=BOARD (visual) ({time.time()-t_iter:.1f}s)")
        elif state in ("RESULT_PANEL", "LEVEL_UP"):
            # Button bounds are resolved from the live UI tree (never hardcoded).
            img, state, els, nodes = snapshot()
            log(f"[{iterations}] state={state} ({time.time()-t_iter:.1f}s)")
        else:
            img, state, els, nodes = snapshot()
            log(f"[{iterations}] state={state} ({time.time()-t_iter:.1f}s)")

        # A residual WebView node can survive after the ad is dismissed, and a
        # dump taken mid-animation can be stale. Trust the screenshot -- but only
        # when it shows a board and NOT a result/level-up panel on top of it.
        if state in ("AD_WEBVIEW", "UNKNOWN") and looks_like_game(img):
            if looks_like_result(img) or looks_like_levelup(img):
                log("  panel visible but UI tree stale -> re-dumping")
                img, state, els, nodes = snapshot()
                if state in ("UNKNOWN", "AD_WEBVIEW"):
                    log("  still stale -> halting (no blind taps)")
                    queue_failure(img, "stale_panel")
                    log_board({"ts": now(), "image": img, "state": state,
                               "result": "aborted"})
                    return 1
            else:
                log("  stale UI tree over a live board -> treating as BOARD")
                state = "BOARD"

        # Stall guard: an actionable screen that refuses to change after repeated
        # taps means the tap is not registering. Stop instead of burning the clock.
        if state == stall_state and state in ("RESULT_FREE", "RESULT_AD", "LEVEL_UP"):
            stall_count += 1
        else:
            stall_state, stall_count = state, 0
        if stall_count >= 4:
            log(f"  stall: {state} unchanged after {stall_count} taps -> halting")
            queue_failure(img, "stall", {"state": state})
            log_board({"ts": now(), "image": img, "state": state, "result": "aborted"})
            return 1

        if state == "TIME_UP":
            log("  Time's Up -> doing nothing (hard user rule)")
            if WAIT_S > 0:
                log(f"  waiting up to {WAIT_S}s for a new board (zero taps)")
                img2 = wait_for_board(WAIT_S)
                if img2 is None:
                    log("  wait expired -> halting")
                    log_board({"ts": now(), "image": img, "state": state,
                               "result": "timeout"})
                    return 0
                log("  new board appeared -> playing it")
                img, state, els, nodes = img2, "BOARD", {}, []
            else:
                log_board({"ts": now(), "image": img, "state": state, "result": "timeout"})
                return 0

        if state == "BOARD":
            # A board whose clock is already red cannot be finished: it is the
            # leftover of an ad end card that let the timer run (P007). Do not
            # waste taps on it and do not count it as a win.
            if clock_is_critical(img):
                log("  board clock already critical (red timer) -> not tapping")
                log_board({"ts": now(), "image": img, "state": "BOARD",
                           "result": "expired", "reason": "clock_critical"})
                if WAIT_S > 0:
                    log(f"  waiting up to {WAIT_S}s for a fresh board")
                    img2 = wait_for_board(WAIT_S)
                    if img2 is None:
                        log("  wait expired -> halting")
                        return 0
                    log("  fresh board appeared -> playing it")
                    img, state, els, nodes = img2, "BOARD", {}, []
                else:
                    return 0
            img = archive_board_image(img)
            board_rec = {"ts": now(), "image": img, "state": state}
            before = moves_left(nodes)
            # P014: a board dealt during an ad can arrive with only ~20 s left.
            # On a low clock every non-tap second matters, so plan without the
            # decorative mistake taps and never pay for the re-capture branch.
            tight = low_clock(img)
            if tight:
                log("  low clock (amber timer) -> no mistakes, no re-capture")
            plan = solve_board(img, no_mistakes=tight)
            if not plan.get("ok"):
                board_rec.update({"result": "queued", "reason": "no_solution"})
                queue_failure(img, "no_solution", {"raw": plan.get("raw", "")[:2000]})
                log_board(board_rec)
                log("  no solution -> queued, halting")
                return 1
            # P012: a mid-animation frame can make perception misread LEP/POT and
            # produce a degenerate plan (board 37: lep=(0,0) instead of (3,0), 24 taps
            # on a 4x4 with 22 moves). Re-capture and re-solve once before trusting it.
            if not tight and (plan["base_cost"] == 0
                              or plan["total"] > MAX_TAPS * 0.5):
                log(f"  suspicious plan (base={plan['base_cost']} "
                    f"total={plan['total']}) -> re-capturing")
                try:
                    time.sleep(2.0)
                    img_r = _shot_or_recover()
                    if img_r and looks_like_real_board(img_r):
                        plan2 = solve_board(img_r)
                        if plan2.get("ok") and 0 < plan2["total"] <= MAX_TAPS:
                            img = archive_board_image(img_r)
                            board_rec = {"ts": now(), "image": img, "state": state}
                            plan = plan2
                            log(f"  re-solve ok: lep={plan['lep']} pot={plan['pot']} "
                                f"total={plan['total']}")
                except Exception as exc:
                    log(f"  re-solve failed: {exc}")
            if plan["total"] > MAX_TAPS:
                board_rec.update({"result": "queued", "reason": "over_46"})
                queue_failure(img, "over_46", {"total": plan["total"]})
                log_board(board_rec)
                log(f"  plan {plan['total']} > {MAX_TAPS} -> refusing, halting")
                return 1

            # P013: the intentional mistake taps are real moves. A plan whose total
            # equals the whole budget burns the last move, the "Out of moves!"
            # overlay eats the final fix tap and the board dies unwon (run 021
            # boards 41/42: base=12 +8 mistakes = 20 with exactly 20 left). Re-solve
            # without mistakes whenever the plan cannot leave headroom.
            if before is not None and plan["total"] >= before:
                log(f"  plan {plan['total']} >= moves left {before} -> "
                    f"re-solve without mistakes")
                plan_nm = solve_board(img, no_mistakes=True)
                if plan_nm.get("ok"):
                    plan = plan_nm
                    log(f"  clean plan: base={plan['base_cost']} total={plan['total']}")
            if before is not None and plan["total"] >= before:
                log(f"  plan {plan['total']} still >= moves left {before} -> "
                    f"not tapping, waiting for a fresh board")
                log_board({"ts": now(), "image": img, "state": "BOARD",
                           "result": "expired", "reason": "no_move_headroom"})
                if WAIT_S > 0:
                    img2 = wait_for_board(WAIT_S)
                    if img2 is None:
                        return 0
                    img, state, els, nodes = img2, "BOARD", {}, []
                    continue
                return 0

            sig = hashlib.md5(json.dumps(plan["taps"], sort_keys=True).encode()).hexdigest()
            img_sig = hashlib.md5(open(img, "rb").read()).hexdigest()
            if sig == last_plan_sig and img_sig == last_img_sig:
                log("  stuck detector: identical plan + screenshot -> halting")
                return 1

            log(f"  plan: lep={plan['lep']} pot={plan['pot']} "
                f"base={plan['base_cost']} total={plan['total']}")

            if dry:
                log("  dry-run: not tapping")
                return 0

            device.tap_batch([(t["x"], t["y"]) for t in plan["taps"]])
            time.sleep(2.6)
            repairs = 0
            repair_taps = []

            # Screenshot-only win check (uiautomator hangs during the animation),
            # but a result panel must be confirmed: the Time's Up panel also has a
            # CTA band, and a dead board must never be credited as a win (P007).
            img2 = _shot_or_recover()
            won = looks_like_result(img2) or looks_like_levelup(img2)
            if won and not looks_like_levelup(img2):
                try:
                    xml2, _ = device.dump_ui()
                    st_check, _ = classify(xml2)
                except Exception:
                    st_check = None
                if st_check == "TIME_UP":
                    log("  clock expired mid-plan -> Time's Up, NOT a win")
                    log_board({"ts": now(), "image": img2, "state": "TIME_UP",
                               "result": "timeout", "reason": "expired_mid_plan",
                               "lep": plan["lep"], "pot": plan["pot"],
                               "total_taps": plan["total"]})
                    if WAIT_S > 0:
                        log(f"  waiting up to {WAIT_S}s for a new board (zero taps)")
                        img3 = wait_for_board(WAIT_S)
                        if img3 is not None:
                            log("  new board appeared -> playing it")
                            last_plan_sig, last_img_sig = None, None
                            continue
                    return 0
            state2, nodes2, after = ("RESULT_FREE", [], None) if won else (None, [], None)

            # Self-repair: still on the board -> a tap was dropped. Re-solve from
            # the new screenshot and apply the (small) residual plan, max twice.
            if not won and looks_like_game(img2) and not clock_is_critical(img2):
                for _ in range(2):
                    residual = solve_board(img2, no_mistakes=True)
                    if not residual.get("ok"):
                        log("  residual repair skipped: no solution on the live frame")
                        break
                    n = residual["total"]
                    if n <= 0 or n > 8:
                        log(f"  residual repair skipped: {n} taps is not a dropped tap")
                        break
                    if repairs == 0:
                        # Keep the two frames so the misread tile can be labelled.
                        try:
                            ts = time.strftime("%Y%m%d_%H%M%S")
                            for tag, src in (("before", img), ("after", img2)):
                                dst = os.path.join(
                                    QUEUE_DIR, f"{ts}_repair_{tag}.png")
                                shutil.copy(src, dst)
                            log(f"  repair frames -> {os.path.basename(dst)}")
                        except Exception as exc:
                            log(f"  (could not save repair frames: {exc})")
                    repairs += 1
                    log(f"  residual repair: {n} taps")
                    repair_taps.extend(residual["taps"])
                    device.tap_batch([(t["x"], t["y"]) for t in residual["taps"]])
                    time.sleep(2.4)
                    img2 = device.screenshot()
                    if looks_like_result(img2) or looks_like_levelup(img2):
                        won, state2 = True, "RESULT_FREE"
                        break
            elif not won and looks_like_game(img2):
                log("  residual repair skipped: clock critical")

            if not won:
                img2, state2, els2, nodes2 = snapshot()
                after = moves_left(nodes2)
            if state2 == "BOARD" and before is not None and after == before:
                queue_failure(img2, "moves_not_decremented",
                              {"before": before, "after": after})
                log("  unit did not decrement -> halting (no blind re-tap)")
                return 1

            board_rec.update({
                "lep": plan["lep"], "pot": plan["pot"],
                "base_cost": plan["base_cost"], "total_taps": plan["total"],
                "plan": plan["taps"],
                "repairs": repairs,
                "repair_taps": repair_taps,
                "result": "win" if state2 in ("RESULT_FREE", "RESULT_AD", "LEVEL_UP")
                          else "unknown",
            })
            log_board(board_rec)
            if board_rec["result"] == "win":
                wins += 1
            boards += 1
            ad_triggers = 0
            last_plan_sig, last_img_sig = sig, img_sig
            log(f"  -> {board_rec['result']} (boards={boards} wins={wins})")
            continue

        if state == "RESULT_FREE":
            log("  tap Play Again")
            tap_element(els, "play_again")
            time.sleep(2.6)
            continue

        if state in ("RESULT_AD", "LEVEL_UP"):
            if ad_triggers >= 3:
                log("  ad already triggered 3x with no board -> halting (no ad loop)")
                queue_failure(img, "ad_loop", {"state": state})
                log_board({"ts": now(), "image": img, "state": state,
                           "result": "aborted"})
                return 1
            ad_triggers += 1
            log(f"  tap Watch Ad ({state})")
            rec = handle_ad_trigger(els, state)
            log_board({"ts": now(), "image": img, "state": state,
                       "result": "ad", "ad": rec})
            if rec.get("triggered") and rec.get("outcome") not in (None, "closed"):
                log(f"  ad not closed ({rec.get('outcome')}) -> halting")
                queue_failure(img, f"ad_{rec.get('outcome')}")
                return 1
            for _ in range(3):
                time.sleep(1.8)
                _, st2, els2, _ = snapshot()
                if st2 == "RESULT_FREE":
                    log("  post-ad panel RESULT_FREE -> tap Play Again")
                    tap_element(els2, "play_again")
                    time.sleep(2.6)
                else:
                    break
            continue

        if state == "AD_WEBVIEW":
            rec = close_ad(log=log, back_on_store=True)
            log_board({"ts": now(), "image": img, "state": state,
                       "result": "ad", "ad": rec})
            if rec["outcome"] != "closed":
                log(f"  ad not closed ({rec['outcome']}) -> halting")
                queue_failure(img, f"ad_{rec['outcome']}")
                return 1
            continue

        if state == "AD_LOADING":
            time.sleep(3)
            continue

        if state == "AD_STORE":
            log("  Play Store ad -> closing")
            if tap_element(els, "close_btn"):
                time.sleep(1.6)
            else:
                device.adb("shell", "input", "keyevent", "KEYCODE_BACK")
                time.sleep(1.6)
            continue

        if state == "AD_NOT_READY":
            log("  dismiss Ad Not Ready")
            tap_element(els, "ok")
            time.sleep(2)
            continue

        if state == "OUT_OF_MOVES":
            log("  out of moves -> Quit")
            tap_element(els, "quit")
            time.sleep(2.5)
            continue

        # UNKNOWN / MENU: never act blindly. With --wait, poll for a board.
        if WAIT_S > 0:
            log(f"  state {state} not actionable -> waiting up to {WAIT_S}s for a board")
            img2 = wait_for_board(WAIT_S)
            if img2 is not None:
                img, state, els, nodes = img2, "BOARD", {}, []
                log("  board appeared -> playing it")
            else:
                log("  wait expired -> halting (no taps)")
                queue_failure(img, f"state_{str(state).lower()}")
                log_board({"ts": now(), "image": img, "state": state, "result": "aborted"})
                return 1
        else:
            log(f"  state {state} is not actionable -> halting (no taps)")
            queue_failure(img, f"state_{str(state).lower()}")
            log_board({"ts": now(), "image": img, "state": state, "result": "aborted"})
            return 1

    log(f"done: boards={boards} wins={wins}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
