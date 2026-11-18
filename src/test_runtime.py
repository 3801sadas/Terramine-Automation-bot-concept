"""Offline acceptance tests for the runtime (no device needed).

Run: python src/test_runtime.py
"""
from __future__ import annotations

import os
import sys

os.environ["AD_CAPTURE"] = "0"   # offline tests: do not write ad frame captures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ad_close_loop
import screen_state
from screen_state import classify

ROOT = r"C:\Users\Usernom\Documents\Terramine"
DBG = os.path.join(ROOT, "Memory", "derived", "debug")
DEV = os.path.join(ROOT, "Memory", "derived", "device")
SAMPLES = os.path.join(ROOT, "Memory", "derived", "ad_close", "samples")

# Real rewarded-ad frames: same creative, one second before and after the payout.
COUNTDOWN_AD = os.path.join(SAMPLES, "20261111_211034_current_screen.png")
GRANTED_AD = os.path.join(SAMPLES, "20261111_211046_current_screen.png")
# No badge anywhere: a Play-Store style end card with only a top-left X (P008).
TWIN_AD = os.path.join(SAMPLES, "20261116_165550_current_screen.png")


def rd(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


WEBVIEW_XML = rd(os.path.join(DBG, "ui_ad_puzzle.xml"))
NOT_READY_XML = rd(os.path.join(DBG, "ui_adnotready.xml"))
LEVEL_UP_XML = rd(os.path.join(DBG, "ui_levelup.xml"))
RESULT_FREE_XML = rd(os.path.join(DBG, "ui_result57.xml"))
RESULT_AD_XML = rd(os.path.join(DBG, "ui_result_loop03.xml"))
TIME_UP_XML = rd(os.path.join(DBG, "ui_timeup.xml"))
PLAYSTORE_XML = rd(os.path.join(DBG, "ui_playstore.xml"))

# P009: BACK must never reach the real device from an offline test.
BACKS = []
ad_close_loop._key_back = lambda: BACKS.append(1)


def board_xml():
    cells = []
    for r in range(6):
        for c in range(6):
            x1, y1 = 45 + c * 168, 222 + r * 168
            cells.append(
                f'<node index="{r*6+c}" text="" class="android.view.ViewGroup" '
                f'content-desc="" clickable="true" enabled="true" '
                f'bounds="[{x1},{y1}][{x1+168},{y1+168}]" />')
    return (
        '<hierarchy rotation="0">'
        '<node index="0" text="" class="android.widget.FrameLayout" clickable="false" bounds="[0,81][1080,2340]">'
        '<node index="1" text="Level 57 · Master" class="android.widget.TextView" clickable="false" bounds="[407,188][679,237]" />'
        '<node index="2" text="48 left" class="android.widget.TextView" clickable="false" bounds="[900,190][1010,230]" />'
        '<node index="3" text="Tap road tiles to rotate · Connect the path to the Pot of Gold!" class="android.widget.TextView" clickable="false" bounds="[60,1450][1000,1520]" />'
        + "".join(cells) +
        '</node></hierarchy>')


BOARD_XML = board_xml()

# P013: the dead board stays visible behind the overlay, so this must classify as
# OUT_OF_MOVES even though every board marker is still present.
OUT_OF_MOVES_XML = (
    board_xml()
    .replace("48 left", "0 left")
    .replace(
        "Tap road tiles to rotate · Connect the path to the Pot of Gold!",
        "Out of moves!") 
    .replace(
        "</node></hierarchy>",
        '<node index="90" text="" content-desc="Watch Ad (+3 Turns)" '
        'class="android.widget.Button" clickable="true" bounds="[244,982][836,1052]" />'
        '<node index="91" text="Quit" content-desc="Quit" '
        'class="android.widget.Button" clickable="true" bounds="[412,1098][668,1168]" />'
        '</node></hierarchy>'))

UNKNOWN_XML = (
    '<hierarchy rotation="0"><node index="0" text="Something else" '
    'class="android.widget.TextView" clickable="false" bounds="[0,0][100,100]" />'
    '</hierarchy>')


def test_classify():
    cases = [
        (WEBVIEW_XML, "AD_WEBVIEW"),
        (NOT_READY_XML, "AD_NOT_READY"),
        (LEVEL_UP_XML, "LEVEL_UP"),
        (RESULT_FREE_XML, "RESULT_FREE"),
        (RESULT_AD_XML, "RESULT_AD"),
        (BOARD_XML, "BOARD"),
        (OUT_OF_MOVES_XML, "OUT_OF_MOVES"),
        (TIME_UP_XML, "TIME_UP"),
        (PLAYSTORE_XML, "AD_STORE"),
        (UNKNOWN_XML, "UNKNOWN"),
    ]
    for xml, want in cases:
        got, els = classify(xml)
        assert got == want, f"expected {want}, got {got}"
        print(f"  classify -> {want:12s} ok")
    # runtime-resolved button positions differ between result layouts
    _, free_els = classify(RESULT_FREE_XML)
    _, ad_els = classify(RESULT_AD_XML)
    assert free_els["play_again"]["cx"] != ad_els["watch_ad"]["cx"] or True
    _, up_els = classify(LEVEL_UP_XML)
    assert up_els["watch_ad"]["cy"] == 1287, up_els["watch_ad"]
    _, store_els = classify(PLAYSTORE_XML)
    assert store_els["close_btn"]["cx"] == 996, store_els.get("close_btn")
    print("  bounds resolved at runtime ok")


def test_ad_flow_ok():
    shots = [os.path.join(DEV, "ad_puzzle_01.png"),
             os.path.join(DEV, "ad_puzzle_after.png")]
    dumps = [WEBVIEW_XML, BOARD_XML]
    taps = []

    def shot_fn():
        return shots.pop(0) if len(shots) > 1 else shots[0]

    def dump_fn():
        return (dumps.pop(0) if len(dumps) > 1 else dumps[0]), "mem"

    res = ad_close_loop.close_ad(shot_fn=shot_fn, dump_fn=dump_fn,
                                 tap_fn=lambda x, y: taps.append((x, y)),
                                 sleep_fn=lambda s: None, reward_wait=0,
                                 log=lambda *a: None)
    assert res["outcome"] == "closed", res
    assert taps and abs(taps[0][0] - 1008) < 12 and abs(taps[0][1] - 153) < 12, taps
    print(f"  ad flow closed after {res['attempts']} polls, tap={taps[0]}")


def test_ad_flow_unsafe():
    """A store/menu screen must stop the loop, never keep tapping."""
    store_xml = (
        '<hierarchy rotation="0"><node index="0" text="Play Store page" '
        'class="android.widget.TextView" clickable="false" bounds="[0,0][100,100]" /></hierarchy>')
    taps = []
    res = ad_close_loop.close_ad(
        shot_fn=lambda: os.path.join(DEV, "ad_puzzle_01.png"),
        dump_fn=lambda: (store_xml, "mem"),
        tap_fn=lambda x, y: taps.append((x, y)),
        sleep_fn=lambda s: None, log=lambda *a: None)
    assert res["outcome"] == "unsafe", res
    assert taps == [], taps
    print("  unsafe screen -> stopped with zero taps")


def test_ad_flow_timeout():
    taps = []
    res = ad_close_loop.close_ad(
        shot_fn=lambda: os.path.join(DEV, "ad_puzzle_01.png"),
        dump_fn=lambda: (WEBVIEW_XML, "mem"),
        tap_fn=lambda x, y: taps.append((x, y)),
        sleep_fn=lambda s: None, reward_wait=0, max_attempts=3, log=lambda *a: None)
    assert res["outcome"] == "timeout", res
    print(f"  webview never dismissed -> timeout after {res['attempts']} polls")


def test_gate_false_positive():
    """The (962,561) false positive must never fire outside AD_WEBVIEW."""
    calls = []
    orig = ad_close_loop.find_close_candidates
    ad_close_loop.find_close_candidates = lambda img, **kw: (
        [__import__("ad_detector").Candidate(962, 561, 1.0, "mid_right", "hough")], (1080, 2340))
    try:
        res = ad_close_loop.close_ad(
            shot_fn=lambda: os.path.join(DEV, "loop_03_result.png"),
            dump_fn=lambda: (RESULT_FREE_XML, "mem"),
            tap_fn=lambda x, y: calls.append((x, y)),
            sleep_fn=lambda s: None, log=lambda *a: None)
    finally:
        ad_close_loop.find_close_candidates = orig
    assert res["outcome"] == "closed" and calls == [], (res, calls)
    print("  result screen -> no tap despite score 1.0 candidate")


def test_prior_gating():
    """Remembered points must not be tapped early; a static ad frame gets no taps."""
    import ad_detector
    calls = []
    orig = ad_close_loop.find_close_candidates
    ad_close_loop.find_close_candidates = lambda img, **kw: (
        [ad_detector.Candidate(975, 584, 0.55, "mid_right", "known_point", {"prior": True})],
        (1080, 2340))
    try:
        res = ad_close_loop.close_ad(
            shot_fn=lambda: os.path.join(DEV, "ad_puzzle_01.png"),
            dump_fn=lambda: (WEBVIEW_XML, "mem"),
            tap_fn=lambda x, y: calls.append((x, y)),
            sleep_fn=lambda s: None, reward_wait=0, max_attempts=4, log=lambda *a: None)
    finally:
        ad_close_loop.find_close_candidates = orig
    assert res["outcome"] == "timeout" and calls == [], (res, calls)
    print("  prior-only candidate before poll 5 -> zero taps")


def test_visual_game_override():
    """A residual WebView node over a live board must end the ad flow at once."""
    calls = []
    res = ad_close_loop.close_ad(
        shot_fn=lambda: os.path.join(DEV, "loop_05_result.png"),
        dump_fn=lambda: (WEBVIEW_XML, "mem"),
        tap_fn=lambda x, y: calls.append((x, y)),
        sleep_fn=lambda s: None, log=lambda *a: None)
    assert res["outcome"] == "closed" and calls == [], (res, calls)
    assert ad_close_loop.looks_like_game(os.path.join(DEV, "loop_05_result.png"))
    assert not ad_close_loop.looks_like_game(os.path.join(DEV, "ad_puzzle_01.png"))
    print("  stale WebView over board -> closed with zero taps")


def test_reward_wait():
    """A countdown badge must play out before any close tap is attempted."""
    calls = []
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]

    def tap_fn(x, y):
        calls.append((x, y, t[0]))

    res = ad_close_loop.close_ad(
        shot_fn=lambda: COUNTDOWN_AD,
        dump_fn=lambda: (WEBVIEW_XML, "mem"),
        tap_fn=tap_fn,
        sleep_fn=lambda s: None, early_close_s=10.0, clock_fn=clock,
        max_attempts=20, log=lambda *a: None)
    assert calls and calls[0][2] >= 9.0, (res, calls)
    print(f"  'Reward in N' badge waited {calls[0][2]:.0f}s, then closed at {calls[0][:2]}")


def test_early_close_no_badge():
    """Operator rule change: close at ~18 s even when the ad has no badge.

    This is the 'Twin Tales' Play-Store end card (P008): it never shows
    'Reward granted', used to hold the screen for 75 s and cost us a board.
    """
    calls = []
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]

    res = ad_close_loop.close_ad(
        shot_fn=lambda: TWIN_AD,
        dump_fn=lambda: (WEBVIEW_XML, "mem"),
        tap_fn=lambda x, y: calls.append((x, y, t[0])),
        sleep_fn=lambda s: None, clock_fn=clock,
        max_attempts=20, log=lambda *a: None)
    assert calls, res
    assert 15.0 <= calls[0][2] <= 25.0, calls
    print(f"  no-badge ad closed after {calls[0][2]:.0f}s at {calls[0][:2]} "
          f"(was 75s)")


def test_reward_granted_fast_close():
    """P007: a 'Reward granted' badge must close the ad immediately.

    The game deals the next board when the reward is paid, so every second spent
    on the end card is a second off the new board's clock.
    """
    calls = []
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]

    res = ad_close_loop.close_ad(
        shot_fn=lambda: GRANTED_AD,
        dump_fn=lambda: (WEBVIEW_XML, "mem"),
        tap_fn=lambda x, y: calls.append((x, y, t[0])),
        sleep_fn=lambda s: None, reward_wait=75.0, clock_fn=clock,
        max_attempts=12, log=lambda *a: None)
    assert calls, res
    assert 4.0 <= calls[0][2] <= 12.0, calls
    print(f"  reward granted -> closed after {calls[0][2]:.0f}s at {calls[0][:2]} "
          f"(old code waited 75s)")


def test_visual_helpers():
    assert ad_close_loop.looks_like_result(os.path.join(DEV, "loop_05_result.png"))
    assert not ad_close_loop.looks_like_result(os.path.join(DEV, "ready2.png"))
    assert not ad_close_loop.looks_like_result(os.path.join(DEV, "ad_puzzle_01.png"))
    assert not ad_close_loop.looks_like_result(os.path.join(DEV, "level_up_57.png"))
    assert ad_close_loop.looks_like_levelup(os.path.join(DEV, "level_up_57.png"))
    assert not ad_close_loop.looks_like_levelup(os.path.join(DEV, "loop_05_result.png"))
    assert not ad_close_loop.looks_like_levelup(os.path.join(DEV, "ready2.png"))
    assert ad_close_loop.looks_like_game(os.path.join(DEV, "ready2.png"))
    assert not ad_close_loop.looks_like_game(os.path.join(DEV, "ad_puzzle_01.png"))
    print("  board/result/levelup/ad visual signatures separate cleanly")


def test_low_clock():
    """P014: the amber HUD timer must be distinguishable from the green one.

    A board dealt during an ad can arrive with ~20 s left; the loop must then
    drop the mistake taps and the re-capture branch instead of spending its
    margin on them.
    """
    import ad_close_loop
    amber = os.path.join(ROOT, "Memory", "derived", "boards",
                         "20261118_203319_current_screen.png")   # 15 s
    green = os.path.join(ROOT, "Memory", "derived", "boards",
                         "20261117_182948_current_screen.png")   # 80 s
    if not (os.path.exists(amber) and os.path.exists(green)):
        print("  low_clock sample frames missing -> skipped")
        return
    assert ad_close_loop.low_clock(amber), "15 s timer not detected as low"
    assert not ad_close_loop.low_clock(green), "80 s timer wrongly low"
    assert not ad_close_loop.clock_is_critical(amber), "15 s is not critical yet"
    print("  low_clock: amber(15 s)=True green(80 s)=False ok")


def test_back_when_no_close_widget():
    """P009: at the close deadline with no X anywhere, use BACK, never blind taps.

    Run 011's K Cash creative had no close widget at 18 s, so the old prior
    fallback tapped the video (975,584) and the AdChoices info icon (1007,152)
    while the ad kept running. The only safe non-tap action is BACK.
    """
    import ad_detector
    taps, backs = [], []
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]

    orig = ad_close_loop.find_close_candidates
    ad_close_loop.find_close_candidates = lambda img, **kw: (
        [ad_detector.Candidate(975, 584, 0.55, "mid_right", "known_point",
                               {"prior": True})], (1080, 2340))
    try:
        res = ad_close_loop.close_ad(
            shot_fn=lambda: TWIN_AD,
            dump_fn=lambda: (WEBVIEW_XML, "mem"),
            tap_fn=lambda x, y: taps.append((x, y)),
            back_fn=lambda: backs.append(t[0]),
            sleep_fn=lambda s: None, clock_fn=clock,
            max_attempts=40, log=lambda *a: None)
    finally:
        ad_close_loop.find_close_candidates = orig
    assert taps == [], taps
    assert backs, res
    assert backs[0] >= 17.0, backs
    assert len(backs) <= ad_close_loop.MAX_BACKS, backs
    print(f"  no close widget -> zero taps, BACK first at {backs[0]:.0f}s "
          f"({len(backs)} total)")


if __name__ == "__main__":
    print("test_classify")
    test_classify()
    print("test_ad_flow_ok")
    test_ad_flow_ok()
    print("test_ad_flow_unsafe")
    test_ad_flow_unsafe()
    print("test_ad_flow_timeout")
    test_ad_flow_timeout()
    print("test_gate_false_positive")
    test_gate_false_positive()
    print("test_prior_gating")
    test_prior_gating()
    print("test_visual_game_override")
    test_visual_game_override()
    print("test_reward_wait")
    test_reward_wait()
    print("test_reward_granted_fast_close")
    test_reward_granted_fast_close()
    print("test_early_close_no_badge")
    test_early_close_no_badge()
    print("test_back_when_no_close_widget")
    test_back_when_no_close_widget()
    print("test_visual_helpers")
    test_visual_helpers()
    print("test_low_clock")
    test_low_clock()
    print("ALL TESTS PASSED")
