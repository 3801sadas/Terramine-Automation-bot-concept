"""Rewarded-ad closer: poll -> detect X -> tap -> verify.

Rules learned live:
  * Only act while the UI tree says AD_WEBVIEW (the one state vision must handle),
    so the known false positive at ~(962,561) on game screens can never fire.
  * Prefer visually detected X over remembered coordinates; remembered points are
    a late fallback only.
  * Never tap the same spot more than twice: if the screen did not change, the ad
    is still counting down and tapping more just wastes the game clock.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from ad_detector import find_close_candidates, save_sample
from ad_reward import reward_state
from screen_state import classify
import device

SAFE_REGIONS = ("mid_right", "top_right", "top_left")
SUCCESS_STATES = {"BOARD", "RESULT_FREE", "RESULT_AD", "LEVEL_UP"}
MAX_TAPS = 8          # hard cap per ad
MAX_PER_POINT = 2     # then that coordinate is exhausted
MAX_BACKS = 3         # P009: BACK presses per ad, only after the close deadline

# P008: keep a small JPEG of every ad-poll frame so ad networks we have not seen
# yet can be analysed frame by frame offline. Derived data only; set
# AD_CAPTURE=0 in the environment to turn it off.
AD_CAPTURE = os.environ.get("AD_CAPTURE", "1") != "0"
AD_CAPTURE_DIR = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\runs"


def _capture(cap_dir, idx, img, extra):
    """Save one downscaled JPEG + a JSON line describing the poll."""
    if not cap_dir:
        return
    try:
        from PIL import Image
        im = Image.open(img).convert("RGB")
        im.thumbnail((540, 1170))
        im.save(os.path.join(cap_dir, "poll_%02d.jpg" % idx), quality=70)
        with open(os.path.join(cap_dir, "polls.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict({"poll": idx, **extra})) + "\n")
    except Exception:
        pass


def _max_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        if cur > best:
            best = cur
    return best


def looks_like_result(img_path):
    """True when the result panel's wide CTA button band is visible.

    Colour-agnostic on purpose: the CTA can be yellow ('Play Again'), green
    ('Exit') or the greyed `Loading ad...` variant. All are large solid blocks
    spanning >=30 contiguous rows in y 1840-1980, while a live board has only
    thin text strokes there (<= ~75 px/row). The band also has to sit on the
    game's dark green background (>30% dark) so a Play-Store end card, whose
    huge blue Install button sits on white (~2% dark), can never match (P006).
    """
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("RGB")).astype(int)
        band = a[1840:1980, :]
        bright = band.max(axis=2) > 140
        dark = (band.max(axis=2) < 100).mean()
        return _max_run(bright.sum(axis=1) > 250) >= 30 and dark >= 0.30
    except Exception:
        return False


def looks_like_levelup(img_path):
    """True when the level-up panel's big solid 'LEVEL UP!' banner is visible.

    That banner is the only large solid yellow block on any game screen
    (~693x198 px). The board's gold path is thin strips and the result panel has
    only outline tiles, so a connected-component size test separates them.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("RGB")).astype(int)
        R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        m = ((R > 190) & (G > 150) & (B < 110)).astype("uint8")
        m[:1000, :] = 0
        m[1700:, :] = 0
        n, _lab, stats, _cent = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, n):
            _x, _y, w, h, area = stats[i]
            if w >= 600 and h >= 150 and area >= 90000:
                return True
        return False
    except Exception:
        return False


def clock_is_critical(img_path):
    """True when the HUD timer is in its red low-time state.

    The clock icon/digits are green while there is time and turn red at the end
    (measured mean fractions over y 140-245, x 880-1060: 58 s -> red 0.000 /
    green 0.093; 3 s and 0 s -> red 0.062 / green 0.005). A board whose clock is
    already red cannot be finished, so it must never be tapped (P007).
    """
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("RGB")).astype(int)
        r = a[140:245, 880:1060]
        R, G, B = r[:, :, 0], r[:, :, 1], r[:, :, 2]
        red = ((R > 170) & (G < 110) & (B < 110)).mean()
        green = ((G > 140) & (R < 130)).mean()
        return bool(red >= 0.03 and red > green)
    except Exception:
        return False


def low_clock(img_path):
    """True when the HUD timer has turned amber, i.e. roughly <=20 s left.

    Same pixel region as clock_is_critical. Measured on live frames:
      15 s -> orange 0.104, green 0.005
      37 s -> orange 0.028, green 0.092
      59 s -> orange 0.030, green 0.100
      80 s -> orange 0.028, green 0.106
    On a low clock the loop must stop spending margin on re-captures or on the
    decorative mistake taps, because a single dropped tap then costs the board
    (P014).
    """
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("RGB")).astype(int)
        r = a[140:245, 880:1060]
        R, G, B = r[:, :, 0], r[:, :, 1], r[:, :, 2]
        orange = ((R > 180) & (G > 120) & (G < 200) & (B < 90)).mean()
        green = ((G > 140) & (R < 130)).mean()
        return bool(orange >= 0.06 and orange > 2 * green)
    except Exception:
        return False


def _sha(path):
    try:
        return hashlib.md5(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


def looks_like_game(img_path):
    """True if the screenshot shows the Gold Rush board frame.

    The board's top border is a solid gold band spanning x=40..1040 at y~505.
    Ads never reproduce that, so this is a reliable 'we are back in game' cue.
    Used when a stale/ad-residual WebView makes the UI tree lie.
    """
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(img_path).convert("RGB")).astype(int)
        band = a[200:1700, 40:1040]
        R, G, B = band[:, :, 0], band[:, :, 1], band[:, :, 2]
        yellow = (R > 190) & (G > 150) & (B < 110)
        rows = yellow.mean(axis=1)
        cols = yellow.mean(axis=0)
        # the board frame needs BOTH long horizontal borders and vertical borders
        return bool((rows > 0.85).sum() >= 2 and (cols > 0.60).sum() >= 2)
    except Exception:
        return False


def looks_like_real_board(img_path):
    """Stricter check: visual frame + an actual tile grid (not a fallback).

    Panels like the 'Play Again' screen have the gold frame but no tile grid.
    Seams give the grid size directly; when both seam axes fail we try the
    candidate sizes and accept the board only if LEP and POT are both found
    on the borders (P005: real 4x4 boards must never be rejected).
    """
    if not looks_like_game(img_path):
        return False
    try:
        import tilegrid as TG
        import numpy as np
        from PIL import Image
        arr = np.asarray(Image.open(img_path).convert("RGB")).astype(np.float32)
        geom = TG.detect_geometry(arr)
        if geom.get("source") in ("seams", "seams_x", "seams_y"):
            return True
        # Last resort: pick a candidate N that yields a believable board.
        from perception_v2 import detect_lep_pot
        fl, ft, fr, fb = TG.load_frame()
        for n in (4, 5, 6):
            g = {"n": n, "left": fl, "top": ft,
                 "cell_x": (fr - fl) / n, "cell_y": (fb - ft) / n}
            lep, pot = detect_lep_pot(arr, g)
            if lep and pot:
                return True
        return False
    except Exception:
        return False


def _pick(cands, tapped, attempt):
    """Return a visually confirmed close glyph, or None.

    P009: remembered/prior coordinates are NEVER tapped. They are emitted with a
    fixed score of 0.55 and, on an unfamiliar creative, land inside the video or
    on the AdChoices info icon (run 011 tapped (975,584) and (1007,152) blindly
    and the ad was unaffected). Only a real template/Hough hit in a corner region
    is allowed to trigger a tap.
    """
    visual = [c for c in cands
              if c.method != "known_point" and c.score >= 0.70
              and c.region in SAFE_REGIONS]
    for c in sorted(visual, key=lambda z: -z.score):
        if tapped.get((c.x // 30, c.y // 30), 0) < MAX_PER_POINT:
            return c
    return None


def _key_back():
    """Dismiss the ad with the system BACK key.

    Ads run in their own activity, so BACK leaves the ad without tapping any ad
    content (P009). It is only used after the reward is considered confirmed.
    """
    device.adb("shell", "input", "keyevent", "KEYCODE_BACK")


def close_ad(shot_fn=device.screenshot, dump_fn=device.dump_ui,
             tap_fn=device.tap, sleep_fn=time.sleep,
             max_attempts=50, poll_s=1.2, reward_wait=75.0,
             early_close_s=18.0, clock_fn=time.time, log=print, back_fn=None,
             back_on_store=False):
    """Poll the ad, then close it as soon as the payout is expected.

    `early_close_s` is the operator-defined point at which we stop waiting and
    close (default 18 s, i.e. just after the measured ~15 s payout). `reward_wait`
    is only the absolute safety cap kept for backwards compatibility.
    """
    states = []
    tapped = {}
    taps_made = 0
    backs = 0
    back_fn = back_fn or _key_back
    store_seen = False          # P011: have we seen a Play Store sheet yet?
    back_tried = False          # and did we already try BACK on one?
    prev_hash = None
    last_state = None
    static_polls = 0
    start = clock_fn()
    cap_dir = None
    if AD_CAPTURE:
        try:
            cap_dir = os.path.join(AD_CAPTURE_DIR, time.strftime("%Y%m%d_%H%M%S"))
            os.makedirs(cap_dir, exist_ok=True)
        except Exception:
            cap_dir = None

    for attempt in range(1, max_attempts + 1):
        img = shot_fn()

        # Fast path: the board frame is visible -> the ad is already gone.
        if looks_like_game(img):
            log(f"  [ad] board visible at poll {attempt} -> closed")
            return {"outcome": "closed", "attempts": attempt,
                    "close_point": None, "states": states, "taps": taps_made}

        img_hash = _sha(img)
        if prev_hash is not None and img_hash == prev_hash:
            static_polls += 1
        else:
            static_polls = 0
        prev_hash = img_hash

        # P007 fast path: the ad SDK's top-right badge switches from
        # "Reward in N second(s)" to "Reward granted" the moment the reward is
        # paid - and the game deals the next board at that instant, so its 60 s
        # clock is already running behind the end card. Close NOW instead of
        # waiting out `reward_wait` (75 s), which used to hand us dead boards.
        # Screenshot-only (edge-template match), no uiautomator dump.
        rs = reward_state(img)
        _capture(cap_dir, attempt, img, {"t": round(clock_fn() - start, 1),
                                         "badge": rs["score"], "static": static_polls})
        if rs["granted"] and clock_fn() - start >= 4.0:
            cands, _size = find_close_candidates(img)
            best = _pick(cands, tapped, attempt)
            if best is not None and taps_made < MAX_TAPS:
                log(f"  [ad] reward granted (badge {rs['score']:.2f}) -> "
                    f"close now at ({best.x},{best.y})")
                try:
                    save_sample(img, best.x, best.y, label="close",
                                note=f"reward_granted/{best.region}/{best.method}")
                except Exception:
                    pass
                tap_fn(best.x, best.y)
                taps_made += 1
                key = (best.x // 30, best.y // 30)
                tapped[key] = tapped.get(key, 0) + 1
                sleep_fn(1.5)
                continue
            if backs < MAX_BACKS:
                log(f"  [ad] reward granted (badge {rs['score']:.2f}) -> "
                    f"no close widget, BACK ({backs + 1}/{MAX_BACKS})")
                back_fn()
                backs += 1
                sleep_fn(1.5)
                continue
            log(f"  [ad] reward granted (badge {rs['score']:.2f}) "
                f"but no safe close point -> keep polling")

        xml, _ = dump_fn()
        state, _els = classify(xml)
        states.append(state)
        if cap_dir:
            try:
                with open(os.path.join(cap_dir, "poll_%02d.xml" % attempt),
                          "w", encoding="utf-8") as f:
                    f.write(xml or "")
            except Exception:
                pass
        log(f"  [ad] poll {attempt}: state={state}")

        if state in SUCCESS_STATES:
            log("  [ad] ad gone -> back in game")
            return {"outcome": "closed", "attempts": attempt,
                    "close_point": None, "states": states, "taps": taps_made}

        if state == "AD_LOADING":
            sleep_fn(poll_s)
            continue
        last_state = state

        if state == "AD_STORE":
            # P011: the multi-ad chain only yields at the end, so tapping the
            # sheet's Close just returns to the next ad. BACK on the sheet does
            # not exit the stack directly either, but pressing it early and
            # repeatedly (run 016: 3 BACKs from the first sheet at ~13 s) closed
            # the ad at poll 6 (~18 s) with the board at 46 s, versus poll 14
            # (~65 s) with the board at 5 s when we only pressed Close. So BACK
            # is the better exit signal on every sheet.
            if back_on_store and not store_seen and not back_tried:
                store_seen = True
                back_tried = True
                log("  [ad] Play Store sheet -> BACK (accelerates the exit)")
                back_fn()
                backs += 1
                sleep_fn(2.0)
                continue
            store_seen = True
            el = _els.get("close_btn")
            if el and taps_made < MAX_TAPS:
                log("  [ad] Play Store sheet -> tap Close")
                tap_fn(el["cx"], el["cy"])
                taps_made += 1
            else:
                log("  [ad] Play Store sheet -> BACK")
                back_fn()
                backs += 1
            sleep_fn(2.0)
            continue

        if state != "AD_WEBVIEW":
            log(f"  [ad] unexpected state {state} -> stop (no blind taps)")
            return {"outcome": "unsafe", "attempts": attempt,
                    "close_point": None, "states": states, "taps": taps_made}

        # Let the creative play, then close as soon as the payout is expected.
        # Rule change (2026-11-16, operator): the reward is considered already
        # paid, so we no longer wait for the SDK badge / a 75 s timer. Measured
        # payout time on the creatives we have seen is ~15 s (the game deals the
        # next board at that moment), so `early_close_s` defaults to 18 s: the
        # board still gets ~50 s of its 60 s clock. A frozen frame (end card) or
        # an explicit "Reward granted" badge closes it even earlier.
        elapsed = clock_fn() - start
        frozen_end = static_polls >= 3 and elapsed >= 15
        due = frozen_end or elapsed >= early_close_s or elapsed >= reward_wait
        if not due:
            log(f"  [ad] creative playing -> waiting ({elapsed:.0f}s, "
                f"close at {early_close_s:.0f}s, badge {rs['score']:.2f})")
            sleep_fn(poll_s)
            continue
        if frozen_end and elapsed < early_close_s:
            log("  [ad] creative ended (frame frozen) -> looking for X")

        cands, _size = find_close_candidates(img)
        best = _pick(cands, tapped, attempt)
        if best is None or taps_made >= MAX_TAPS:
            # P009: no confirmed close glyph on this creative - do not guess at
            # ad content. The ad is its own activity, so leave it with BACK.
            if backs < MAX_BACKS:
                log(f"  [ad] no confirmed close widget -> BACK "
                    f"({backs + 1}/{MAX_BACKS})")
                back_fn()
                backs += 1
                sleep_fn(1.5)
                continue
            sleep_fn(poll_s)
            continue

        log(f"  [ad] tap close ({best.x},{best.y}) score={best.score:.2f} "
            f"region={best.region} method={best.method}")
        try:
            save_sample(img, best.x, best.y, label="close",
                        note=f"{state}/{best.region}/{best.method}")
        except Exception:
            pass
        tap_fn(best.x, best.y)
        taps_made += 1
        key = (best.x // 30, best.y // 30)
        tapped[key] = tapped.get(key, 0) + 1
        sleep_fn(1.5)

    log("  [ad] attempts exhausted -> timeout")
    return {"outcome": "timeout", "attempts": max_attempts,
            "close_point": None, "states": states, "taps": taps_made}


if __name__ == "__main__":
    print(close_ad())
